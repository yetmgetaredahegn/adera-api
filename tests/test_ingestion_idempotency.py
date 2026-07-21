"""FR-2.3 — the guarantee that lets the pipeline crash and be re-run safely.

Upserting the same tender twice must create once, then report UNCHANGED, and never
duplicate. This is the technical heart of Week 2's DoD, so it gets a test that runs
against a real Postgres.
"""

import uuid

import pytest
from app.core.db import async_session_factory
from app.modules.ingestion.adapters.base import RawTender
from app.modules.ingestion.models import Tender
from app.modules.ingestion.service import UpsertResult, upsert_tender
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete, select


def _raw(ref: str, title: str = "Original title") -> RawTender:
    return RawTender(
        source_tender_id=ref,
        url="https://example.test/t",
        title=title,
        region="Ethiopia",
        raw={"ref": ref, "title": title},
    )


@pytest.mark.integration
async def test_upsert_is_idempotent() -> None:
    ref = f"TEST-{uuid.uuid4()}"
    async with async_session_factory() as session:
        source = Source(
            key=f"test-{uuid.uuid4()}",
            name="test source",
            type=SourceType.API,
            base_url="https://example.test",
            tos_status=ToSStatus.ALLOWED,
            enabled=False,
        )
        session.add(source)
        await session.flush()

        # 1st time -> CREATED
        _, r1 = await upsert_tender(session, source, _raw(ref))
        # 2nd time, identical -> UNCHANGED (this is the idempotency guarantee)
        _, r2 = await upsert_tender(session, source, _raw(ref))
        # 3rd time, a field changed -> UPDATED, still no new row
        _, r3 = await upsert_tender(session, source, _raw(ref, title="Deadline moved"))

        assert r1 == UpsertResult.CREATED
        assert r2 == UpsertResult.UNCHANGED
        assert r3 == UpsertResult.UPDATED

        count = (
            (
                await session.execute(
                    select(Tender).where(
                        Tender.source_id == source.id, Tender.source_tender_id == ref
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(count) == 1  # three upserts, one row

        # cleanup
        await session.execute(delete(Tender).where(Tender.source_id == source.id))
        await session.execute(delete(Source).where(Source.id == source.id))
        await session.commit()
