"""MAT-2/MAT-3 (docs/11_API_REFERENCE.md): save/dismiss a match. FR-7.3:
dismissed never resurfaces. Mirrors test_matches_tenant_isolation.py's
seeding + cleanup pattern."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import Match, MatchState
from app.modules.sources.models import Source, SourceType, ToSStatus
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


async def _register(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "org_name": f"Org {email}",
            "org_type": "diaspora",
            "country": "US",
            "timezone": "America/Los_Angeles",
        },
    )
    assert r.status_code == 201, r.text


async def _seed_match(
    org_id: uuid.UUID, closing_at: datetime | None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (match_id, source_id) for cleanup."""
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
            source_tender_id=f"T-{uuid.uuid4()}",
            url="https://example.test/t",
            title="Save/dismiss test tender",
            region="Ethiopia",
            bidding_track=BiddingTrack.UNKNOWN,
            group_id=group.id,
            closing_at=closing_at,
        )
        session.add(tender)
        await session.flush()

        match = Match(tender_id=tender.id, org_id=org_id, score=0.9, state=MatchState.NEW)
        session.add(match)
        await session.commit()
        return match.id, source.id


async def _cleanup(email: str, source_ids: list[uuid.UUID]) -> None:
    async with async_session_factory() as session:
        if source_ids:
            await session.execute(delete(Tender).where(Tender.source_id.in_(source_ids)))
            await session.execute(delete(Source).where(Source.id.in_(source_ids)))
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            await session.commit()
            return
        memberships = (
            (await session.execute(select(OrgMember).where(OrgMember.user_id == user.id)))
            .scalars()
            .all()
        )
        for m in memberships:
            await session.execute(delete(Match).where(Match.org_id == m.org_id))
            await session.execute(delete(Org).where(Org.id == m.org_id))
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.execute(delete(OrgMember).where(OrgMember.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_save_then_appears_in_state_saved_filter() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    source_ids: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            me = (await client.get("/api/v1/auth/me")).json()
            org_id = uuid.UUID(me["org"]["id"])
            match_id, source_id = await _seed_match(org_id, closing_at=None)
            source_ids.append(source_id)

            r = await client.post(f"/api/v1/matches/{match_id}/save")
            assert r.status_code == 200, r.text
            assert r.json() == {"state": "saved"}

            saved = await client.get("/api/v1/matches?state=saved")
            assert [m["id"] for m in saved.json()] == [str(match_id)]

            default_feed = await client.get("/api/v1/matches")
            assert [m["id"] for m in default_feed.json()] == [str(match_id)]
    finally:
        await _cleanup(email, source_ids)


@pytest.mark.integration
async def test_dismiss_never_resurfaces_in_default_feed() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    source_ids: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            me = (await client.get("/api/v1/auth/me")).json()
            org_id = uuid.UUID(me["org"]["id"])
            match_id, source_id = await _seed_match(org_id, closing_at=None)
            source_ids.append(source_id)

            r = await client.post(f"/api/v1/matches/{match_id}/dismiss")
            assert r.status_code == 200, r.text
            assert r.json() == {"state": "dismissed"}

            default_feed = await client.get("/api/v1/matches")
            assert default_feed.json() == []

            explicit = await client.get("/api/v1/matches?state=dismissed")
            assert [m["id"] for m in explicit.json()] == [str(match_id)]
    finally:
        await _cleanup(email, source_ids)


@pytest.mark.integration
async def test_save_expired_tender_is_409() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    source_ids: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            me = (await client.get("/api/v1/auth/me")).json()
            org_id = uuid.UUID(me["org"]["id"])
            past = datetime.now(UTC) - timedelta(days=1)
            match_id, source_id = await _seed_match(org_id, closing_at=past)
            source_ids.append(source_id)

            r = await client.post(f"/api/v1/matches/{match_id}/save")
            assert r.status_code == 409, r.text
            assert r.json()["type"].endswith("/expired")

            # Dismiss has no expiry rule -- must still succeed on the same match.
            r = await client.post(f"/api/v1/matches/{match_id}/dismiss")
            assert r.status_code == 200, r.text
    finally:
        await _cleanup(email, source_ids)


@pytest.mark.integration
async def test_save_dismiss_404_for_another_orgs_match() -> None:
    email_a = f"test-a-{uuid.uuid4()}@example.com"
    email_b = f"test-b-{uuid.uuid4()}@example.com"
    source_ids: list[uuid.UUID] = []
    try:
        async with (
            AsyncClient(
                transport=ASGITransport(app=app), base_url="https://example.com"
            ) as client_a,
            AsyncClient(
                transport=ASGITransport(app=app), base_url="https://example.com"
            ) as client_b,
        ):
            await _register(client_a, email_a)
            await _register(client_b, email_b)
            me_a = (await client_a.get("/api/v1/auth/me")).json()
            org_a_id = uuid.UUID(me_a["org"]["id"])
            match_id, source_id = await _seed_match(org_a_id, closing_at=None)
            source_ids.append(source_id)

            # B must not be able to save or dismiss A's match, and the 404
            # must not distinguish "wrong org" from "doesn't exist" (rule 9).
            r = await client_b.post(f"/api/v1/matches/{match_id}/save")
            assert r.status_code == 404, r.text
            r = await client_b.post(f"/api/v1/matches/{match_id}/dismiss")
            assert r.status_code == 404, r.text
    finally:
        await _cleanup(email_a, source_ids)
        await _cleanup(email_b, [])
