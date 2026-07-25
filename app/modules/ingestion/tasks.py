"""Ingestion orchestration (M2).

`run_source` is a plain async function so it can be driven three ways from one
implementation: the Celery task (production), the CLI (dev), and tests. Every run
is wrapped in the run ledger, so "what happened last night and what did it cost"
is always a row — success or crash (FR-11.1).
"""

from dataclasses import dataclass

from app.core.db import async_session_factory
from app.modules.ingestion.adapters import get_adapter
from app.modules.ingestion.politeness import build_polite_client
from app.modules.ingestion.service import UpsertResult, upsert_tender
from app.modules.runledger.service import run
from app.modules.sources.service import get_by_key
from app.workers.celery_app import celery_app


@dataclass
class IngestReport:
    source: str
    seen: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0


async def run_source(source_key: str) -> IngestReport:
    report = IngestReport(source=source_key)
    async with async_session_factory() as session:
        source = await get_by_key(session, source_key)
        if source is None:
            raise KeyError(f"unknown source '{source_key}' — seed it first")
        adapter = get_adapter(source_key)

        async with run(session, kind="fetch_source", ref=source_key) as ledger:
            # FR-2.5: robots.txt + this source's rate_limit_per_min are enforced by
            # the client's transport, so no adapter can opt out by forgetting to.
            async with build_polite_client(source) as client:
                raws = await adapter.fetch(client, source)

            for raw in raws:
                ledger.seen()
                _, result = await upsert_tender(session, source, raw)
                match result:
                    case UpsertResult.CREATED:
                        ledger.created()
                        report.created += 1
                    case UpsertResult.UPDATED:
                        ledger.updated()
                        report.updated += 1
                    case UpsertResult.UNCHANGED:
                        ledger.unchanged()
                        report.unchanged += 1
            report.seen = ledger.items_seen
            # run() commits the ledger row and the upserted tenders together on exit.

    return report


@celery_app.task(name="ingestion.fetch_source", queue="io")  # type: ignore[untyped-decorator]
def fetch_source(source_key: str) -> dict[str, int | str]:
    """Celery entry point. Runs the async orchestration to completion."""
    import asyncio

    report = asyncio.run(run_source(source_key))
    return {
        "source": report.source,
        "seen": report.seen,
        "created": report.created,
        "updated": report.updated,
        "unchanged": report.unchanged,
    }
