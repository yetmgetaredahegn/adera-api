"""ADR-028 — cross-source tender identity. The behavior this whole design
exists for: the SAME real-world opportunity published on two different
sources collapses into one `TenderGroup`, while a re-advertisement of the
SAME bid from the SAME source with a pushed-back deadline never does (the
founder's binding constraint) -- both proven against a real Postgres, not
mocked, since the grouping query itself is the thing under test.

Every test wraps its assertions in try/finally: a failure mid-test must not
leave orphaned Source/Tender/TenderGroup rows in a shared dev database (a real
gap this file had before a bug in upsert_tender was fixed -- see AGENTS.md)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.db import async_session_factory
from app.modules.ingestion.adapters.base import RawTender
from app.modules.ingestion.models import Tender, TenderGroup
from app.modules.ingestion.service import upsert_tender
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete


async def _make_source(session, key: str) -> Source:  # type: ignore[no-untyped-def]
    source = Source(
        key=key,
        name=key,
        type=SourceType.API,
        base_url="https://example.test",
        tos_status=ToSStatus.ALLOWED,
        enabled=False,
    )
    session.add(source)
    await session.flush()
    return source


def _raw(ref: str, title: str, buyer: str, closing_at: datetime | None) -> RawTender:
    return RawTender(
        source_tender_id=ref,
        url="https://example.test/t",
        title=title,
        buyer=buyer,
        region="Ethiopia",
        closing_at=closing_at,
        raw={"ref": ref},
    )


@pytest.mark.integration
async def test_same_opportunity_two_sources_collapses_to_one_group() -> None:
    """The core ADR-028 case: e-GP and a donor portal both publish the same
    tender (same buyer, same closing date) -> one group, not two."""
    closing = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    async with async_session_factory() as session:
        source_a = await _make_source(session, f"egp-{uuid.uuid4()}")
        source_b = await _make_source(session, f"wb-{uuid.uuid4()}")
        try:
            tender_a, _ = await upsert_tender(
                session,
                source_a,
                _raw(f"A-{uuid.uuid4()}", "Supply of laptops", "Ministry of Education", closing),
            )
            tender_b, _ = await upsert_tender(
                session,
                source_b,
                _raw(f"B-{uuid.uuid4()}", "Supply of Laptops", "MINISTRY OF EDUCATION", closing),
            )

            assert tender_a.group_id == tender_b.group_id

            group = await session.get(TenderGroup, tender_a.group_id)
            assert group is not None
            assert group.has_conflict is False
        finally:
            await session.execute(
                delete(Tender).where(Tender.source_id.in_([source_a.id, source_b.id]))
            )
            await session.execute(delete(Source).where(Source.id.in_([source_a.id, source_b.id])))
            await session.commit()


@pytest.mark.integration
async def test_same_source_readvertised_with_new_deadline_stays_separate() -> None:
    """The founder's binding constraint: a re-advertised bid from the SAME
    source with a DIFFERENT (pushed-back) deadline is a distinct opportunity,
    never merged into the original -- even though title and buyer are
    identical, the deadline sits outside the grouping window."""
    original_closing = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    readvertised_closing = original_closing + timedelta(days=21)

    async with async_session_factory() as session:
        source = await _make_source(session, f"egp-{uuid.uuid4()}")
        try:
            original, _ = await upsert_tender(
                session,
                source,
                _raw(
                    f"ORIG-{uuid.uuid4()}",
                    "Construction of a health post",
                    "Regional Health Bureau",
                    original_closing,
                ),
            )
            readvertised, _ = await upsert_tender(
                session,
                source,
                _raw(
                    f"READV-{uuid.uuid4()}",
                    "Construction of a health post",
                    "Regional Health Bureau",
                    readvertised_closing,
                ),
            )

            assert original.group_id != readvertised.group_id
        finally:
            await session.execute(delete(Tender).where(Tender.source_id == source.id))
            await session.execute(delete(Source).where(Source.id == source.id))
            await session.commit()


@pytest.mark.integration
async def test_conflicting_deadline_within_window_flags_group_not_merges_silently() -> None:
    """Two sources agree it's the same opportunity (buyer matches, deadlines
    within the window) but disagree on the EXACT closing time -- grouped, but
    flagged, never silently reconciled (ADR-028 §3; extends FR-4.4)."""
    closing_a = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    closing_b = closing_a + timedelta(hours=6)  # same day, different hour

    async with async_session_factory() as session:
        source_a = await _make_source(session, f"egp-{uuid.uuid4()}")
        source_b = await _make_source(session, f"wb-{uuid.uuid4()}")
        try:
            tender_a, _ = await upsert_tender(
                session,
                source_a,
                _raw(
                    f"A-{uuid.uuid4()}",
                    "Bridge rehabilitation",
                    "Regional Roads Authority",
                    closing_a,
                ),
            )
            tender_b, _ = await upsert_tender(
                session,
                source_b,
                _raw(
                    f"B-{uuid.uuid4()}",
                    "Bridge Rehabilitation",
                    "regional roads authority",
                    closing_b,
                ),
            )

            assert tender_a.group_id == tender_b.group_id
            group = await session.get(TenderGroup, tender_a.group_id)
            assert group is not None
            assert group.has_conflict is True
        finally:
            await session.execute(
                delete(Tender).where(Tender.source_id.in_([source_a.id, source_b.id]))
            )
            await session.execute(delete(Source).where(Source.id.in_([source_a.id, source_b.id])))
            await session.commit()


@pytest.mark.integration
async def test_no_buyer_or_deadline_never_guesses_a_merge() -> None:
    """Nothing to block on safely -> always a new group, never a similarity
    guess (ADR-028 step 1: a wrong merge is worse than a duplicate)."""
    async with async_session_factory() as session:
        source = await _make_source(session, f"src-{uuid.uuid4()}")
        try:
            t1, _ = await upsert_tender(
                session, source, _raw(f"X-{uuid.uuid4()}", "General notice", "Unknown Buyer", None)
            )
            t2, _ = await upsert_tender(
                session, source, _raw(f"Y-{uuid.uuid4()}", "General notice", "Unknown Buyer", None)
            )

            assert t1.group_id != t2.group_id
        finally:
            await session.execute(delete(Tender).where(Tender.source_id == source.id))
            await session.execute(delete(Source).where(Source.id == source.id))
            await session.commit()
