"""The fatal bug class (AGENTS.md rule 9): org A must never see org B's
matches. Every tenant endpoint ships with this test alongside it, not later."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.ingestion.models import BiddingTrack, Tender
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
            "org_type": "local",
            "country": "ET",
            "timezone": "Africa/Addis_Ababa",
        },
    )
    assert r.status_code == 201, r.text


async def _seed_match_for_org(org_id: uuid.UUID, title: str) -> uuid.UUID:
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

        tender = Tender(
            source_id=source.id,
            source_tender_id=f"T-{uuid.uuid4()}",
            url="https://example.test/t",
            title=title,
            region="Ethiopia",
            bidding_track=BiddingTrack.UNKNOWN,
        )
        session.add(tender)
        await session.flush()

        session.add(Match(tender_id=tender.id, org_id=org_id, score=0.9, state=MatchState.NEW))
        await session.commit()
        return tender.id


async def _cleanup(email: str) -> None:
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
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
async def test_org_a_never_sees_org_b_matches() -> None:
    email_a = f"test-a-{uuid.uuid4()}@example.com"
    email_b = f"test-b-{uuid.uuid4()}@example.com"
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
            me_b = (await client_b.get("/api/v1/auth/me")).json()
            org_a_id = uuid.UUID(me_a["org"]["id"])
            org_b_id = uuid.UUID(me_b["org"]["id"])
            assert org_a_id != org_b_id

            await _seed_match_for_org(org_a_id, "Org A's tender")
            await _seed_match_for_org(org_b_id, "Org B's tender")

            # 1. Default (no ?org_id=) scoping: A sees only A's own match.
            resp_a = await client_a.get("/api/v1/matches")
            assert resp_a.status_code == 200, resp_a.text
            titles_a = {m["tender"]["title"] for m in resp_a.json()}
            assert titles_a == {"Org A's tender"}

            resp_b = await client_b.get("/api/v1/matches")
            titles_b = {m["tender"]["title"] for m in resp_b.json()}
            assert titles_b == {"Org B's tender"}

            # 2. Explicit cross-org request: A asking for B's org_id must NOT
            # succeed and must NOT even confirm B's org exists (404, not 403 —
            # docs/11_API_REFERENCE.md §0).
            leak_attempt = await client_a.get(f"/api/v1/matches?org_id={org_b_id}")
            assert leak_attempt.status_code == 404, leak_attempt.text
    finally:
        await _cleanup(email_a)
        await _cleanup(email_b)
