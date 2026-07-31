"""The AI Kernel — the ONLY door to any model (ADR-014).

`kernel.complete(...)` and `kernel.embed(...)` are the sole entry points for LLM
and embedding calls. No module imports litellm or an SDK directly. This one rule
is what makes cost control (budget), reproducibility (prompt versions + traces),
caching, and provider swaps possible without touching callers.

Model routing (which task -> which tier) lives here so that "use a cheaper model
for extraction" is a config change measured by evals, not a hunt through the code
(06 §8: tier the models; nothing defaults to a frontier model).
"""

import re
from typing import TypeVar

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.core.config import settings
from app.kernel.budget import Budget
from app.kernel.cache import ResponseCache, cache_key

TModel = TypeVar("TModel", bound=BaseModel)

# Matches a ```json ... ``` or ``` ... ``` fenced block anywhere in the string.
_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)


def _strip_code_fence(content: str) -> str:
    """Some providers (Claude via OpenRouter, observed) wrap JSON in a ```json
    fence even when response_format={"type": "json_object"} is requested — the
    direct Anthropic API does not do this. Some responses ALSO append trailing
    commentary after the closing fence despite "return ONLY a JSON object"
    instructions (observed live: a qualification response that added a
    "**Note on confidence:**" paragraph after valid, fenced JSON, which broke
    strict parsing — the fix that motivated searching for the fence rather
    than assuming the whole string is exactly its contents).

    Extracts just the fenced block if one exists anywhere in the string
    (before/after content is discarded); if there's no fence at all, assumes
    the whole reply is already bare JSON and returns it unchanged."""
    match = _FENCE_RE.search(content)
    if match is None:
        return content.strip()
    return match.group(1).strip()


# Task -> model tier. Cheapest capable model per task; edit here, measure with evals.
# Routed via OpenRouter (OPENROUTER_API_KEY) rather than a direct Anthropic key —
# litellm dispatches on the "openrouter/" prefix and reads that env var itself.
MODEL_ROUTES: dict[str, str] = {
    "extract": "openrouter/anthropic/claude-haiku-4.5",
    "qualify": "openrouter/anthropic/claude-haiku-4.5",
    "explain": "openrouter/anthropic/claude-sonnet-5",
    "eligibility": "openrouter/anthropic/claude-sonnet-5",
    "qa": "openrouter/anthropic/claude-haiku-4.5",
}

# Hard output cap per task (NFR-COST-1: without this, litellm defaults to the
# model's max context — e.g. 64k tokens — which both wastes budget on runaway
# completions and can exceed what a metered API key can afford in one call).
MAX_TOKENS: dict[str, int] = {
    "extract": 2000,
    "qualify": 500,
    "explain": 1000,
    "eligibility": 1500,
    "qa": 800,
}


class Kernel:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._budget = Budget(redis, settings.kernel_daily_budget_usd)
        self._cache = ResponseCache(redis, settings.kernel_cache_ttl_seconds)

    async def complete(
        self,
        task: str,
        prompt: str,
        schema: type[TModel],
        prompt_version: str,
    ) -> TModel:
        """Run a structured completion and validate it into `schema`.

        Cache hit -> free and instant. Cache miss -> budget check -> model call ->
        validate -> record spend -> cache. Validation failure is the caller's cue
        to route to human review (FR-4.4); the kernel does not silently accept junk.
        """
        model = MODEL_ROUTES.get(task, MODEL_ROUTES["extract"])
        key = cache_key(task, prompt_version, model, prompt)

        cached = await self._cache.get(key)
        if cached is not None:
            return schema.model_validate_json(cached)

        await self._budget.check()

        # Imported lazily so the kernel (and everything importing it) does not pull
        # litellm unless a real model call happens.
        import litellm

        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=MAX_TOKENS.get(task, MAX_TOKENS["extract"]),
            response_format={"type": "json_object"},
        )
        content = _strip_code_fence(resp.choices[0].message.content or "{}")
        usd = float(getattr(resp, "_hidden_params", {}).get("response_cost", 0.0) or 0.0)
        await self._budget.record(usd)

        obj = schema.model_validate_json(content)
        await self._cache.set(key, obj.model_dump_json())
        return obj

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Local BGE-M3 embeddings (ADR-009) — $0, no budget check needed.

        Encoding is blocking CPU work, so it runs in a thread to keep the event
        loop responsive; in production it belongs on the Celery `cpu` queue.
        """
        import asyncio

        from app.kernel.embeddings import embed_texts

        return await asyncio.to_thread(embed_texts, texts)


def build_kernel() -> Kernel:
    redis = aioredis.from_url(str(settings.redis_url))
    return Kernel(redis)
