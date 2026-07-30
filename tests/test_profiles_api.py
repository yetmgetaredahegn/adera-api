"""GET/PUT /api/v1/org/profile (M6, FR-6.1/6.2; docs/11_API_REFERENCE.md PRO-2/PRO-3)
-- the endpoint that lets a real org create the profile match_org() runs against.

`upsert_profile` unconditionally calls `app.kernel.embeddings.embed_texts`, a
sentence-transformers model load -- an optional `ai` extra CI's `check` job does
NOT install. Every test that reaches PUT monkeypatches it at its source module
so the lazy `from app.kernel.embeddings import embed_texts` inside
`upsert_profile` picks up the fake at call time.
"""

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
async def test_get_profile_404s_when_missing() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            r = await client.get("/api/v1/org/profile")
            assert r.status_code == 404, r.text
            assert r.json()["type"].endswith("/not_found")
    finally:
        await _cleanup(email)


@pytest.mark.integration
async def test_put_rejects_empty_sectors_and_capabilities() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            r = await client.put(
                "/api/v1/org/profile",
                json={
                    "source_text": "We build things",
                    "sectors": [],
                    "capabilities": ["software development"],
                },
            )
            assert r.status_code == 422, r.text

            r = await client.put(
                "/api/v1/org/profile",
                json={"source_text": "We build things", "sectors": ["ICT"], "capabilities": []},
            )
            assert r.status_code == 422, r.text
    finally:
        await _cleanup(email)


@pytest.mark.integration
async def test_put_then_get_roundtrip_and_idempotent_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.kernel.embeddings.embed_texts", _fake_embed_texts)
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)

            r = await client.put(
                "/api/v1/org/profile",
                json={
                    "source_text": "We build custom software for donor-funded projects.",
                    "sectors": ["ICT"],
                    "capabilities": ["software development", "systems integration"],
                    "regions": ["Addis Ababa"],
                },
            )
            assert r.status_code == 200, r.text
            body = r.json()
            profile_id = body["id"]
            assert body["sectors"] == ["ICT"]
            assert body["capabilities"] == ["software development", "systems integration"]
            assert body["certifications"] == []
            assert "profile_embedding" not in body

            r = await client.get("/api/v1/org/profile")
            assert r.status_code == 200, r.text
            assert r.json()["id"] == profile_id
            assert r.json()["sectors"] == ["ICT"]

            # Second PUT updates in place -- same id, changed sectors, not a
            # second row (upsert_profile's create-or-update, not append-only).
            r = await client.put(
                "/api/v1/org/profile",
                json={
                    "source_text": "We build custom software for donor-funded projects.",
                    "sectors": ["ICT", "Consulting"],
                    "capabilities": ["software development"],
                },
            )
            assert r.status_code == 200, r.text
            assert r.json()["id"] == profile_id
            assert r.json()["sectors"] == ["ICT", "Consulting"]
    finally:
        await _cleanup(email)
