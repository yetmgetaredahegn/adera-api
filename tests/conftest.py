"""Shared test fixtures.

The engine in app/core/db.py is module-level with a connection pool — correct for
a long-lived API process, wrong for tests. pytest-asyncio gives each test its own
event loop, so a connection pooled during test A is bound to A's loop; when test B
borrows it from the pool, asyncpg raises "Event loop is closed". The failure is
ordering-dependent, which makes it look flaky rather than deterministic.

Disposing the pool after each test keeps the production engine configuration
honest (no test-only NullPool special-casing in app code) while giving each loop
its own connections.
"""

from collections.abc import AsyncIterator, Iterator

import pytest
from app.core.config import settings
from app.core.db import engine


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests() -> AsyncIterator[None]:
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def _disable_rate_limiting() -> Iterator[None]:
    """The suite shares one client identity ("testclient"), so a global limiter
    would count every test's requests into the same bucket and eventually turn an
    unrelated assertion into a flaky 429. The limiter's own behavior is asserted
    explicitly in tests/test_ratelimit.py, which re-enables it deliberately."""
    original = settings.rate_limit_enabled
    settings.rate_limit_enabled = False
    yield
    settings.rate_limit_enabled = original
