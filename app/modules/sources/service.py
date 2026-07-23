"""Sources service (M2, FR-2.1).

The public surface other modules import (never `sources.models` directly). Owns
the registry: which sites we look at, on what schedule, and whether they're enabled.
"""

from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.models import Source, SourceType, ToSStatus


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
    - egp: registered but DISABLED — egp.gov.et is a JS-rendered Angular SPA with
      no public robots.txt. Its data is reachable only via a *logged-in* session,
      and ADR-027 (docs/ADRs/027-source-access-legality.md, Proposed) holds that
      automating a credentialed session to extract data may exceed account
      authorization under Ethiopia's Computer Crime Proclamation 958/2016 — so
      this source stays disabled pending that ADR's resolution (security review
      or an official data-sharing agreement with PPA), not pending Playwright
      engineering time. Registering it now documents intent and reserves the key.
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
            "name": "Ethiopia e-GP (egp.gov.et)",
            "type": SourceType.HTML_DYNAMIC,
            "base_url": "https://egp.gov.et/egp/",
            "fetch_config": {
                "note": (
                    "JS-rendered, no robots.txt. Tender data needs a login session "
                    "-- see ADR-027 (Proposed): access basis unresolved, not an "
                    "engineering blocker."
                )
            },
            "cron": "0 * * * *",
            "tos_status": ToSStatus.UNREVIEWED,
            "enabled": False,
        },
    ]
    for spec in wanted:
        existing = await get_by_key(session, str(spec["key"]))
        if existing is None:
            session.add(Source(**spec))
    await session.commit()
