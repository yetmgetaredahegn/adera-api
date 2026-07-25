"""HTTP rate limiting (docs/11 §0: 429 `rate_limited` with Retry-After).

A fixed-window counter in Redis. Fixed window, not a sliding log, because the
counter must be one atomic INCR per request -- the limiter has to be cheaper
than the work it protects, or it becomes the bottleneck it was added to prevent.

**Fails OPEN.** If Redis is unreachable the request is allowed through. A rate
limiter is a protection, not a dependency: an outage in the counter must not
take the whole API down with it (that would convert a Redis blip into a total
outage, which is strictly worse than briefly unmetered traffic).
"""

import time

import redis.asyncio as aioredis
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# Liveness and the docs are exempt: an uptime probe hammering /healthz must never
# be throttled into a false alarm, and throttling /docs only annoys developers.
EXEMPT_PATHS = frozenset({"/healthz", "/docs", "/redoc", "/openapi.json"})


def client_identity(request: Request) -> str:
    """Who to count against. `X-Forwarded-For` is only consulted when a proxy is
    declared trusted (settings.trust_proxy_headers) -- otherwise any client could
    forge a fresh identity per request and bypass the limit entirely."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First entry is the original client; the rest are proxy hops.
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, redis: aioredis.Redis | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._redis = redis if redis is not None else aioredis.from_url(str(settings.redis_url))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        limit = settings.rate_limit_per_min
        window = int(time.time() // 60)
        key = f"ratelimit:{client_identity(request)}:{window}"

        try:
            count = await self._redis.incr(key)
            if count == 1:
                # Only the first request in a window needs to set the TTL. 119s,
                # not 60s: without slack, a key created at :59.9 can expire before
                # the window it guards is over.
                await self._redis.expire(key, 119)
        except Exception:
            return await call_next(request)

        if count > limit:
            retry_after = 60 - int(time.time() % 60)
            return JSONResponse(
                status_code=429,
                media_type="application/problem+json",
                headers={"Retry-After": str(retry_after)},
                content={
                    "type": "https://adera.bid/errors/rate_limited",
                    "title": "Rate Limited",
                    "status": 429,
                    "detail": f"more than {limit} requests in one minute; retry in {retry_after}s",
                    "instance": request.url.path,
                },
            )

        return await call_next(request)
