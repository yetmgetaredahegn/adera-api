"""qualify_tender must update the existing row on re-run, never duplicate —
the same idempotency guarantee ingestion has, needed here for FR-5.3
(re-qualification on revision) to have somewhere to land later without a
schema change."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.qualification.models import Qualification, QualificationMethod
from app.modules.qualification.service import qualify_tender
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete, select


@pytest.mark.integration
async def test_qualify_tender_updates_in_place_on_rerun() -> None:
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
        group = TenderGroup()
        session.add(group)
        await session.flush()

        tender = Tender(
            source_id=source.id,
            source_tender_id=ref,
            url="https://example.test/t",
            title="Contract Award for a bridge",
            region="Ethiopia",
            raw_data={"notice_type": "Contract Award"},
            bidding_track=BiddingTrack.ICB,
            group_id=group.id,
        )
        session.add(tender)
        await session.flush()

        # No kernel needed — the rule stage rejects this before any LLM call.
        q1 = await qualify_tender(session, tender, kernel=None)
        q2 = await qualify_tender(session, tender, kernel=None)

        assert q1.id == q2.id  # same row, not a duplicate
        assert q1.method == QualificationMethod.RULE

        rows = (
            (
                await session.execute(
                    select(Qualification).where(Qualification.tender_id == tender.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1  # two calls, one row

        await session.execute(delete(Qualification).where(Qualification.tender_id == tender.id))
        await session.execute(delete(Tender).where(Tender.id == tender.id))
        await session.execute(delete(Source).where(Source.id == source.id))
        await session.commit()
