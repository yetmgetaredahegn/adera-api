"""Real HTTP calls through the ASGI app (no mocks) — register, login, me,
logout. DB-backed, so @pytest.mark.integration (SKILLS.md R6)."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.identity.models import Org, OrgMember, Session, User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


def _register_payload(email: str) -> dict[str, str]:
    return {
        "email": email,
        "password": "correct horse battery staple",
        "org_name": f"Test Org {email}",
        "org_type": "local",
        "country": "ET",
        "timezone": "Africa/Addis_Ababa",
    }


async def _cleanup_by_email(email: str) -> None:
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
async def test_register_login_me_logout_flow() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            r = await client.post("/api/v1/auth/register", json=_register_payload(email))
            assert r.status_code == 201, r.text
            assert r.json()["email"] == email
            assert "adera_session" in client.cookies
            assert "adera_csrf" in client.cookies

            me = await client.get("/api/v1/auth/me")
            assert me.status_code == 200, me.text
            assert me.json()["user"]["email"] == email

            # Captured BEFORE logout, replayed explicitly AFTER: proves the
            # session was revoked server-side, not just cleared client-side.
            session_cookie_before_logout = client.cookies["adera_session"]
            csrf = client.cookies["adera_csrf"]

            logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
            assert logout.status_code == 204

            # logout clears the client's own cookie; set the pre-logout value
            # back on the jar explicitly to prove the SERVER rejects a replay.
            client.cookies.set("adera_session", session_cookie_before_logout)
            replay = await client.get("/api/v1/auth/me")
            assert replay.status_code == 401, replay.text
    finally:
        await _cleanup_by_email(email)


@pytest.mark.integration
async def test_register_duplicate_email_conflicts() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            r1 = await client.post("/api/v1/auth/register", json=_register_payload(email))
            assert r1.status_code == 201
            r2 = await client.post("/api/v1/auth/register", json=_register_payload(email))
            assert r2.status_code == 409, r2.text
    finally:
        await _cleanup_by_email(email)


@pytest.mark.integration
async def test_login_wrong_password_is_401() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await client.post("/api/v1/auth/register", json=_register_payload(email))
            r = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
            assert r.status_code == 401
    finally:
        await _cleanup_by_email(email)


@pytest.mark.integration
async def test_me_without_session_is_401() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://example.com"
    ) as client:
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 401


@pytest.mark.integration
async def test_logout_without_csrf_header_is_403() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await client.post("/api/v1/auth/register", json=_register_payload(email))
            r = await client.post("/api/v1/auth/logout")  # no X-CSRF-Token
            assert r.status_code == 403
    finally:
        await _cleanup_by_email(email)
