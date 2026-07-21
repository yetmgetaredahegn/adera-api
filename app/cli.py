"""Developer CLI — run pipeline steps by hand without Celery.

    uv run python -m app.cli seed             # seed the source registry
    uv run python -m app.cli ingest worldbank # fetch + upsert; print a report
    uv run python -m app.cli tenders          # show what's in the DB

This is the "admin dry-run" surface (FR-11.3) until the real admin UI exists.
"""

import asyncio
import sys

from sqlalchemy import func, select

from app.core.db import async_session_factory
from app.modules.ingestion.models import Tender
from app.modules.ingestion.tasks import run_source
from app.modules.sources.service import seed_sources


async def _seed() -> None:
    async with async_session_factory() as session:
        await seed_sources(session)
    print("seeded source registry")


async def _ingest(source_key: str) -> None:
    report = await run_source(source_key)
    print(
        f"[{report.source}] seen={report.seen} "
        f"created={report.created} updated={report.updated} unchanged={report.unchanged}"
    )


async def _tenders() -> None:
    async with async_session_factory() as session:
        total = (await session.execute(select(func.count()).select_from(Tender))).scalar_one()
        rows = (
            (await session.execute(select(Tender).order_by(Tender.created_at.desc()).limit(10)))
            .scalars()
            .all()
        )
        print(f"{total} tenders in db. latest 10:")
        for t in rows:
            deadline = t.closing_at.date().isoformat() if t.closing_at else "—"
            print(f"  [{deadline}] {t.title[:70]}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, *rest = args
    match cmd:
        case "seed":
            asyncio.run(_seed())
        case "ingest":
            asyncio.run(_ingest(rest[0] if rest else "worldbank"))
        case "tenders":
            asyncio.run(_tenders())
        case _:
            print(f"unknown command: {cmd}")
            print(__doc__)


if __name__ == "__main__":
    main()
