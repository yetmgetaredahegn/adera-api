"""The fatal bug class (AGENTS.md rule 9): org A must never see or overwrite
org B's company profile."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.profiles.models import CompanyProfile
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

_VECTOR = [0.1] * 1024


def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_VECTOR for _ in texts]


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


async def _cleanup(email: str) -> None:
    async with async_session_factory() as session:
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
            await session.execute(delete(CompanyProfile).where(CompanyProfile.org_id == m.org_id))
            await session.execute(delete(Org).where(Org.id == m.org_id))
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.execute(delete(OrgMember).where(OrgMember.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_org_a_never_sees_or_overwrites_org_b_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.kernel.embeddings.embed_texts", _fake_embed_texts)
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

            put_a = await client_a.put(
                "/api/v1/org/profile",
                json={
                    "source_text": "Org A profile",
                    "sectors": ["ICT"],
                    "capabilities": ["software development"],
                },
            )
            assert put_a.status_code == 200, put_a.text

            put_b = await client_b.put(
                "/api/v1/org/profile",
                json={
                    "source_text": "Org B profile",
                    "sectors": ["Construction"],
                    "capabilities": ["civil engineering"],
                },
            )
            assert put_b.status_code == 200, put_b.text

            # 1. Default scoping: each org's own GET returns only its own profile.
            get_a = await client_a.get("/api/v1/org/profile")
            assert get_a.json()["source_text"] == "Org A profile"

            get_b = await client_b.get("/api/v1/org/profile")
            assert get_b.json()["source_text"] == "Org B profile"

            # 2. Explicit cross-org request: A asking for B's org_id must NOT
            # succeed and must NOT even confirm B's org exists (404, not 403 --
            # docs/11_API_REFERENCE.md §0), mirroring test_matches_tenant_isolation.py.
            leak_attempt = await client_a.get(f"/api/v1/org/profile?org_id={org_b_id}")
            assert leak_attempt.status_code == 404, leak_attempt.text

            # 3. A's own profile is unaffected by anything B did.
            get_a_again = await client_a.get("/api/v1/org/profile")
            assert get_a_again.json()["source_text"] == "Org A profile"
    finally:
        await _cleanup(email_a)
        await _cleanup(email_b)
