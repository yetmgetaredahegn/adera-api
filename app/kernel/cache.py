"""Response cache (06 §8, point 3).

A model result keyed by the content hash of (task, prompt version, model, input).
A tender analyzed once is free for every later viewer — on popular tenders this is
the highest-ROI line in the cost model. Keyed by hash so identical inputs collide
by design and different inputs never do.
"""

import hashlib

import redis.asyncio as aioredis


def cache_key(task: str, prompt_version: str, model: str, payload: str) -> str:
    digest = hashlib.sha256(f"{task}|{prompt_version}|{model}|{payload}".encode()).hexdigest()
    return f"kernel:cache:{digest}"


class ResponseCache:
    def __init__(self, redis: aioredis.Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def get(self, key: str) -> str | None:
        val = await self._redis.get(key)
        return val.decode() if isinstance(val, bytes) else val

    async def set(self, key: str, value: str) -> None:
        await self._redis.set(key, value, ex=self._ttl)
