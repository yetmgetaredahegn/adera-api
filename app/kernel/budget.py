"""Spend budget + circuit breaker (NFR-COST-1).

A per-UTC-day counter in Redis. Before any paid model call the kernel checks it;
past the cap it raises BudgetExceeded and the pipeline pauses instead of running
up the bill. "A hard daily cap with a breaker, not a hope" (05 §config).
"""

from datetime import UTC, datetime

import redis.asyncio as aioredis


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, redis: aioredis.Redis, daily_cap_usd: float) -> None:
        self._redis = redis
        self._cap = daily_cap_usd

    @staticmethod
    def _key() -> str:
        return f"kernel:spend:{datetime.now(UTC):%Y-%m-%d}"

    async def check(self) -> None:
        spent = await self._redis.get(self._key())
        if spent is not None and float(spent) >= self._cap:
            raise BudgetExceeded(
                f"daily LLM budget ${self._cap} reached (spent ${float(spent):.2f})"
            )

    async def record(self, usd: float) -> None:
        key = self._key()
        await self._redis.incrbyfloat(key, usd)
        await self._redis.expire(key, 60 * 60 * 48)  # keep two days for inspection

    async def spent_today(self) -> float:
        v = await self._redis.get(self._key())
        return float(v) if v else 0.0
