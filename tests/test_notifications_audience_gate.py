"""ADR-029: the digest sweep must silently skip local orgs -- unlike the
synchronous matching/eligibility gates, this is a bulk background job over
every user, so "not this user" is an ordinary outcome, not a 403 (see the
docstring on `notifications.service.get_user_digest_items`)."""

import uuid
from dataclasses import dataclass

import pytest
from app.core.db import async_session_factory
from app.modules.identity.models import Org, OrgMember, OrgRole, OrgType, User
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import Match, MatchState
from app.modules.notifications.service import get_user_digest_items
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete


@dataclass
class _Seeded:
    user_id: uuid.UUID
    org_id: uuid.UUID
    source_id: uuid.UUID
    group_id: uuid.UUID
    tender_id: uuid.UUID


async def _seed_user_org_with_match(org_type: OrgType) -> _Seeded:
    async with async_session_factory() as session:
        user = User(
            email=f"test-{uuid.uuid4()}@example.com",
            password_hash="not-a-real-hash",  # noqa: S106 -- test fixture, never authenticated
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        org = Org(
            name="Test Org", org_type=org_type, country="ET" if org_type == OrgType.LOCAL else "US"
        )
        session.add(org)
        await session.flush()

        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.OWNER))

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
            source_tender_id=f"T-{uuid.uuid4()}",
            url="https://example.test/t",
            title="Test tender",
            region="Ethiopia",
            bidding_track=BiddingTrack.UNKNOWN,
            group_id=group.id,
        )
        session.add(tender)
        await session.flush()

        session.add(Match(tender_id=tender.id, org_id=org.id, score=0.9, state=MatchState.NEW))
        await session.commit()
        return _Seeded(
            user_id=user.id,
            org_id=org.id,
            source_id=source.id,
            group_id=group.id,
            tender_id=tender.id,
        )


async def _cleanup(seeded: _Seeded) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(Match).where(Match.org_id == seeded.org_id))
        await session.execute(delete(Tender).where(Tender.id == seeded.tender_id))
        await session.execute(delete(TenderGroup).where(TenderGroup.id == seeded.group_id))
        await session.execute(delete(Source).where(Source.id == seeded.source_id))
        await session.execute(delete(OrgMember).where(OrgMember.org_id == seeded.org_id))
        await session.execute(delete(Org).where(Org.id == seeded.org_id))
        await session.execute(delete(User).where(User.id == seeded.user_id))
        await session.commit()


@pytest.mark.integration
async def test_local_org_gets_no_digest_items() -> None:
    seeded = await _seed_user_org_with_match(OrgType.LOCAL)
    try:
        async with async_session_factory() as session:
            items = await get_user_digest_items(session, seeded.user_id)
        assert items == []
    finally:
        await _cleanup(seeded)


@pytest.mark.integration
async def test_diaspora_org_gets_digest_items() -> None:
    seeded = await _seed_user_org_with_match(OrgType.DIASPORA)
    try:
        async with async_session_factory() as session:
            items = await get_user_digest_items(session, seeded.user_id)
        assert len(items) == 1
        assert items[0].title == "Test tender"
        assert items[0].group_id is not None
    finally:
        await _cleanup(seeded)
