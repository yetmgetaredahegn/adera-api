"""Sources service (M2, FR-2.1).

The public surface other modules import (never `sources.models` directly). Owns
the registry: which sites we look at, on what schedule, and whether they're enabled.
"""

from datetime import UTC, datetime

import httpx
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.models import (
    Source as Source,
)
from app.modules.sources.models import (
    SourceType as SourceType,
)
from app.modules.sources.models import (
    ToSStatus as ToSStatus,
)


async def get_by_key(session: AsyncSession, key: str) -> Source | None:
    return (await session.execute(select(Source).where(Source.key == key))).scalar_one_or_none()


async def list_enabled(session: AsyncSession) -> list[Source]:
    rows = await session.execute(select(Source).where(Source.enabled.is_(True)))
    return list(rows.scalars().all())


async def list_due(session: AsyncSession, now: datetime | None = None) -> list[Source]:
    """Enabled sources whose cron says "fetch now".

    Beat calls this hourly; a source with cron '0 * * * *' fires each hour. We use
    the previous fire time <= now within the last interval as "due". Kept simple on
    purpose — the run ledger records what actually ran.
    """
    now = now or datetime.now(UTC)
    due: list[Source] = []
    for source in await list_enabled(session):
        itr = croniter(source.cron, now)
        prev_fire = itr.get_prev(datetime)
        # due if the most recent scheduled fire is within the last hour
        if (now - prev_fire).total_seconds() <= 3600:
            due.append(source)
    return due


async def seed_sources(session: AsyncSession) -> None:
    """Idempotent seed of the Phase-1 registry. Safe to run repeatedly.

    - worldbank: enabled — public donor-portal JSON API, our live Phase-1 source.
    - egp: enabled — egp.gov.et's own public tender-listing API, same risk tier
      as worldbank under ADR-027 (docs/ADRs/027-source-access-legality.md,
      Proposed): a public, unauthenticated JSON endpoint, never a credentialed
      session. Discovered by loading the public `/bids/all` page in a headless
      browser with NO credentials and reading its network calls (never touched
      a login field); the endpoint was then confirmed with a bare `curl` --
      zero cookies, zero auth headers, real data (220 tenders at discovery).
      It backs e-GP's own public "Total Active Tenders" dashboard shown to
      every anonymous visitor. `app/modules/ingestion/adapters/egp.py` carries
      the full detail and the hard rule: this adapter must NEVER gain a login
      step. ADR-027 is still Proposed -- this is built ahead of Eyasu's formal
      review per explicit founder direction, same as the qualification
      prefilter; his review lands on this real implementation, not a stub.
    """
    wanted = [
        {
            "key": "worldbank",
            "name": "World Bank Procurement Notices (Ethiopia)",
            "type": SourceType.API,
            "base_url": "https://search.worldbank.org/api/v2/procnotices",
            "fetch_config": {"rows": 60, "country": "Ethiopia"},
            "cron": "0 * * * *",
            "tos_status": ToSStatus.ALLOWED,  # public open-data API
            "enabled": True,
        },
        {
            "key": "egp",
            "name": "Ethiopia e-GP (egp.gov.et) — public listing API",
            "type": SourceType.API,
            "base_url": "https://egp.gov.et/po-gw/cms-v2/api/sourcing/get-grouped-sourcing",
            "fetch_config": {"page_size": 50, "max_pages": 10},
            "cron": "0 * * * *",
            "tos_status": ToSStatus.ALLOWED,  # public, unauthenticated -- see docstring
            "enabled": True,
        },
    ]
    for spec in wanted:
        existing = await get_by_key(session, str(spec["key"]))
        if existing is None:
            session.add(Source(**spec))
    await session.commit()


async def dry_run_source(session: AsyncSession, source_key: str) -> list[object]:
    """Admin dry-run operation (FR-11.3 / 05 §4).

    Executes a source's adapter, fetches raw payloads, and parses them without
    writing anything to the tenders or matches database tables.
    """
    from app.modules.ingestion.adapters import get_adapter

    source = await get_by_key(session, source_key)
    if source is None:
        raise KeyError(f"unknown source '{source_key}' — seed it first")

    adapter = get_adapter(source_key)
    async with httpx.AsyncClient() as client:
        raws = await adapter.fetch(client, source)
        return list(raws)
