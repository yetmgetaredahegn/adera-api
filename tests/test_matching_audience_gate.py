"""ADR-029: local orgs are supply-side only, never a bidder-feature consumer.
Both the service (`match_org`) and the HTTP layer (`GET /matches`) must refuse
a local org plainly -- never a silently empty list, which would be
indistinguishable from "no matches today" (AGENTS.md rule 9's sibling concern:
a wrong silence is as dangerous as a wrong leak)."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.identity.models import Org, OrgMember, OrgType, Session, User
from app.modules.identity.service import AudienceRestricted
from app.modules.matching.service import match_org
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


async def _register(client: AsyncClient, email: str, org_type: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "org_name": f"Org {email}",
            "org_type": org_type,
            "country": "ET" if org_type == "local" else "US",
            "timezone": "Africa/Addis_Ababa" if org_type == "local" else "America/Los_Angeles",
        },
    )
    assert r.status_code == 201, r.text


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
            await session.execute(delete(Org).where(Org.id == m.org_id))
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.execute(delete(OrgMember).where(OrgMember.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_match_org_raises_for_local_org() -> None:
    async with async_session_factory() as session:
        org = Org(name="Local Test Org", org_type=OrgType.LOCAL, country="ET")
        session.add(org)
        await session.flush()
        org_id = org.id
        await session.commit()

    try:
        async with async_session_factory() as session:
            with pytest.raises(AudienceRestricted):
                await match_org(session, org_id)
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Org).where(Org.id == org_id))
            await session.commit()


@pytest.mark.integration
async def test_matches_endpoint_403s_for_local_org() -> None:
    email = f"test-local-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email, "local")
            resp = await client.get("/api/v1/matches")
            assert resp.status_code == 403, resp.text
            assert resp.json()["type"].endswith("/audience_restricted")
    finally:
        await _cleanup(email)


@pytest.mark.integration
async def test_matches_endpoint_200s_for_diaspora_org() -> None:
    email = f"test-diaspora-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email, "diaspora")
            resp = await client.get("/api/v1/matches")
            assert resp.status_code == 200, resp.text
            assert resp.json() == []  # no matches seeded; not a 403
    finally:
        await _cleanup(email)
