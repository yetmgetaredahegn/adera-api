"""The AI Kernel — the ONLY door to any model (ADR-014).

`kernel.complete(...)` and `kernel.embed(...)` are the sole entry points for LLM
and embedding calls. No module imports litellm or an SDK directly. This one rule
is what makes cost control (budget), reproducibility (prompt versions + traces),
caching, and provider swaps possible without touching callers.

Model routing (which task -> which tier) lives here so that "use a cheaper model
for extraction" is a config change measured by evals, not a hunt through the code
(06 §8: tier the models; nothing defaults to a frontier model).
"""

from typing import TypeVar

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.core.config import settings
from app.kernel.budget import Budget
from app.kernel.cache import ResponseCache, cache_key

TModel = TypeVar("TModel", bound=BaseModel)

# Task -> model tier. Cheapest capable model per task; edit here, measure with evals.
MODEL_ROUTES: dict[str, str] = {
    "extract": "anthropic/claude-haiku-4-5-20251001",
    "qualify": "anthropic/claude-haiku-4-5-20251001",
    "explain": "anthropic/claude-sonnet-5",
    "eligibility": "anthropic/claude-sonnet-5",
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
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
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
