"""FR-2.5 outbound conduct: robots.txt is honoured and per-source rate limits
are actually enforced.

No network: the inner transport is a MockTransport and robots.txt bodies are
injected, so these are pure-logic tests (SKILLS.md R6).
"""

import time

import httpx
import pytest
from app.modules.ingestion.politeness import (
    PoliteTransport,
    RateGate,
    RobotsCache,
    RobotsDisallowed,
    build_polite_client,
)
from app.modules.sources.models import Source, SourceType


def _source(rate_limit_per_min: int = 0) -> Source:
    return Source(
        key="fake",
        name="Fake",
        type=SourceType.API,
        base_url="https://example.test/api",
        fetch_config={},
        rate_limit_per_min=rate_limit_per_min,
    )


def _counting_transport(counter: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        counter.append(request)
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(handler)


async def test_robots_disallow_blocks_the_request() -> None:
    async def robots(_url: str) -> str:
        return "User-agent: *\nDisallow: /private\n"

    seen: list[httpx.Request] = []
    client = build_polite_client(_source(), robots_fetcher=robots, inner=_counting_transport(seen))
    async with client:
        with pytest.raises(RobotsDisallowed):
            await client.get("https://example.test/private/tenders")

    # The point: it never reached the network, it wasn't merely discarded after.
    assert seen == []


async def test_robots_allows_paths_outside_the_disallow_rule() -> None:
    async def robots(_url: str) -> str:
        return "User-agent: *\nDisallow: /private\n"

    seen: list[httpx.Request] = []
    client = build_polite_client(_source(), robots_fetcher=robots, inner=_counting_transport(seen))
    async with client:
        resp = await client.get("https://example.test/public/tenders")

    assert resp.status_code == 200
    assert len(seen) == 1


async def test_missing_robots_txt_means_allowed() -> None:
    """No published rules = no restrictions. That is the standard, not a
    fail-open shortcut -- most APIs we ingest serve no robots.txt at all."""

    async def robots(_url: str) -> None:
        return None

    seen: list[httpx.Request] = []
    client = build_polite_client(_source(), robots_fetcher=robots, inner=_counting_transport(seen))
    async with client:
        resp = await client.get("https://example.test/anything")

    assert resp.status_code == 200
    assert len(seen) == 1


async def test_robots_txt_is_fetched_once_per_host() -> None:
    calls: list[str] = []

    async def robots(url: str) -> str:
        calls.append(url)
        return "User-agent: *\n"

    client = build_polite_client(_source(), robots_fetcher=robots, inner=_counting_transport([]))
    async with client:
        for _ in range(3):
            await client.get("https://example.test/page")

    assert calls == ["https://example.test/robots.txt"]


async def test_rate_gate_spaces_consecutive_requests() -> None:
    """600/min => 100ms minimum spacing. Three acquires must therefore take at
    least two intervals; the first is free."""
    gate = RateGate(per_min=600)
    started = time.monotonic()
    for _ in range(3):
        await gate.acquire()
    elapsed = time.monotonic() - started

    assert elapsed >= 0.2


async def test_rate_gate_disabled_when_limit_is_zero() -> None:
    gate = RateGate(per_min=0)
    started = time.monotonic()
    for _ in range(5):
        await gate.acquire()
    assert time.monotonic() - started < 0.05


async def test_source_rate_limit_column_is_what_drives_the_gate() -> None:
    """`sources.rate_limit_per_min` was a decorative column before FR-2.5 was
    enforced; this pins that the value on the row is the value used."""
    transport = PoliteTransport(
        RobotsCache("ADERA-test", fetcher=lambda _url: _none()),
        RateGate(_source(rate_limit_per_min=600).rate_limit_per_min),
        inner=_counting_transport([]),
    )
    assert transport._gate._min_interval == pytest.approx(0.1)


async def _none() -> None:
    return None
