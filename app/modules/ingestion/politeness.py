"""Outbound scraping conduct (FR-2.5): robots.txt + per-source rate limits.

Implemented as an httpx **transport** rather than a helper each adapter must
remember to call. That is the whole point: politeness that an adapter can forget
is politeness the project does not actually have. Every request any adapter makes
through the client built here is gated, including the e-GP adapter's 10 paginated
calls, without a single line changing inside `adapters/`.

`sources.rate_limit_per_min` existed as a column for weeks and nothing read it;
this is what finally enforces it.
"""

import asyncio
import time
import urllib.robotparser
from collections.abc import Awaitable, Callable

import httpx

from app.core.config import settings
from app.modules.sources.models import Source


class RobotsDisallowed(Exception):
    """Raised instead of silently skipping. A source we are not allowed to fetch
    must fail loudly into the run ledger (FR-2.4) -- a run that quietly returns
    zero tenders looks identical to a source that simply had no new notices."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"robots.txt disallows fetching {url}")


RobotsFetcher = Callable[[str], Awaitable[str | None]]


async def _default_robots_fetcher(robots_url: str) -> str | None:
    """Fetched with a plain client, deliberately NOT the polite one: routing this
    through PoliteTransport would recurse (robots check -> fetch robots -> check)."""
    try:
        async with httpx.AsyncClient(timeout=settings.fetch_timeout_seconds) as client:
            resp = await client.get(robots_url, headers={"User-Agent": settings.fetch_user_agent})
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    return resp.text


class RobotsCache:
    """One robots.txt per host, fetched once per process run.

    Absent or unreadable robots.txt means ALLOWED -- that is what the standard
    says (no rules published = no restrictions), not a fail-open shortcut. An
    explicit `Disallow` is honoured.
    """

    def __init__(self, user_agent: str, fetcher: RobotsFetcher | None = None) -> None:
        self._user_agent = user_agent
        self._fetcher = fetcher if fetcher is not None else _default_robots_fetcher
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = asyncio.Lock()

    async def _parser_for(self, url: httpx.URL) -> urllib.robotparser.RobotFileParser | None:
        host_key = f"{url.scheme}://{url.netloc.decode('ascii')}"
        async with self._lock:
            if host_key in self._parsers:
                return self._parsers[host_key]
            body = await self._fetcher(f"{host_key}/robots.txt")
            parser: urllib.robotparser.RobotFileParser | None = None
            if body is not None:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(body.splitlines())
            self._parsers[host_key] = parser
            return parser

    async def allowed(self, url: httpx.URL) -> bool:
        parser = await self._parser_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self._user_agent, str(url))


class RateGate:
    """Spaces requests to at most `per_min` per minute, per source.

    A minimum interval between consecutive requests rather than a burst bucket:
    for a polite crawler, evenly spaced requests are the point. A burst of 20
    followed by 59s of silence averages the same rate while hitting the source
    exactly as hard as having no limit at all for that first second.
    """

    def __init__(self, per_min: int) -> None:
        self._min_interval = 60.0 / per_min if per_min > 0 else 0.0
        self._last: float | None = None
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            if self._last is not None:
                wait = self._min_interval - (now - self._last)
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
            self._last = now


class PoliteTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        robots: RobotsCache,
        gate: RateGate,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._robots = robots
        self._gate = gate
        self._inner = inner if inner is not None else httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not await self._robots.allowed(request.url):
            raise RobotsDisallowed(str(request.url))
        await self._gate.acquire()
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def build_polite_client(
    source: Source,
    robots_fetcher: RobotsFetcher | None = None,
    inner: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """The only client ingestion should use. Identifies itself (FR-2.5), carries
    the configured timeout, and enforces this source's own rate limit."""
    robots = RobotsCache(settings.fetch_user_agent, fetcher=robots_fetcher)
    gate = RateGate(source.rate_limit_per_min)
    return httpx.AsyncClient(
        transport=PoliteTransport(robots, gate, inner=inner),
        headers={"User-Agent": settings.fetch_user_agent},
        timeout=settings.fetch_timeout_seconds,
    )
