"""HTTP rate limiting (docs/11 §0: 429 `rate_limited` + Retry-After).

The limiter is disabled for the suite at large (see the fixture below) so it
can't turn an unrelated test into a flaky 429; it is switched ON explicitly here,
which is the only place its behavior is asserted.
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from app.core.config import settings
from app.core.ratelimit import EXEMPT_PATHS, RateLimitMiddleware, client_identity
from fastapi import FastAPI
from starlette.requests import Request


class _FakeRedis:
    """Counts like Redis does. Not a mock of the API surface -- INCR/EXPIRE are
    the only two calls the limiter makes, and they are trivially real here."""

    def __init__(self, fail: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.expiries: dict[str, int] = {}
        self._fail = fail

    async def incr(self, key: str) -> int:
        if self._fail:
            raise ConnectionError("redis is down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds


@pytest.fixture
def limited_app() -> Iterator[tuple[FastAPI, _FakeRedis]]:
    redis = _FakeRedis()
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, redis=redis)

    original_enabled = settings.rate_limit_enabled
    original_limit = settings.rate_limit_per_min
    settings.rate_limit_enabled = True
    settings.rate_limit_per_min = 3
    try:
        yield app, redis
    finally:
        settings.rate_limit_enabled = original_enabled
        settings.rate_limit_per_min = original_limit


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as client:
        yield client


async def test_requests_over_the_limit_get_429_with_retry_after(
    limited_app: tuple[FastAPI, _FakeRedis],
) -> None:
    app, _redis = limited_app
    async for client in _client(app):
        for i in range(3):
            ok = await client.get("/ping")
            assert ok.status_code == 200, f"request {i} should be allowed"

        blocked = await client.get("/ping")
        assert blocked.status_code == 429
        assert blocked.headers["content-type"].startswith("application/problem+json")
        assert "Retry-After" in blocked.headers
        assert 0 < int(blocked.headers["Retry-After"]) <= 60

        body = blocked.json()
        assert body["type"] == "https://adera.bid/errors/rate_limited"
        assert body["status"] == 429


async def test_healthz_is_exempt(limited_app: tuple[FastAPI, _FakeRedis]) -> None:
    """An uptime probe must never be throttled into a false alarm."""
    app, _redis = limited_app
    assert "/healthz" in EXEMPT_PATHS
    async for client in _client(app):
        for _ in range(10):
            res = await client.get("/healthz")
            assert res.status_code == 200


async def test_window_ttl_is_set_once_with_slack() -> None:
    """119s, not 60s: a key created at :59.9 would otherwise expire before the
    window it guards is over."""
    redis = _FakeRedis()
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, redis=redis)

    original_enabled = settings.rate_limit_enabled
    settings.rate_limit_enabled = True
    try:
        async for client in _client(app):
            await client.get("/ping")
            await client.get("/ping")
    finally:
        settings.rate_limit_enabled = original_enabled

    assert len(redis.expiries) == 1
    assert next(iter(redis.expiries.values())) == 119


async def test_limiter_fails_open_when_redis_is_down() -> None:
    """A limiter outage must not become an API outage -- briefly unmetered
    traffic is strictly better than a total 500."""
    redis = _FakeRedis(fail=True)
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, redis=redis)

    original_enabled = settings.rate_limit_enabled
    original_limit = settings.rate_limit_per_min
    settings.rate_limit_enabled = True
    settings.rate_limit_per_min = 1
    try:
        async for client in _client(app):
            for _ in range(5):
                res = await client.get("/ping")
                assert res.status_code == 200
    finally:
        settings.rate_limit_enabled = original_enabled
        settings.rate_limit_per_min = original_limit


def _request_with(headers: dict[str, str], client_host: str | None) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/ping",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    if client_host is not None:
        scope["client"] = (client_host, 1234)
    return Request(scope)


def test_forwarded_for_is_ignored_unless_a_proxy_is_trusted() -> None:
    """Otherwise any client forges a fresh identity per request and walks around
    the limiter one fake header at a time."""
    request = _request_with({"X-Forwarded-For": "9.9.9.9"}, client_host="10.0.0.1")

    original = settings.trust_proxy_headers
    try:
        settings.trust_proxy_headers = False
        assert client_identity(request) == "10.0.0.1"

        settings.trust_proxy_headers = True
        assert client_identity(request) == "9.9.9.9"
    finally:
        settings.trust_proxy_headers = original


def test_forwarded_for_takes_the_original_client_not_a_proxy_hop() -> None:
    request = _request_with({"X-Forwarded-For": "9.9.9.9, 10.0.0.5"}, client_host="10.0.0.1")
    original = settings.trust_proxy_headers
    try:
        settings.trust_proxy_headers = True
        assert client_identity(request) == "9.9.9.9"
    finally:
        settings.trust_proxy_headers = original
