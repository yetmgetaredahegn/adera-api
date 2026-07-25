"""Unit & integration tests for M11 Run Ledger & Operations Dashboard (FR-11.1, FR-11.5)."""

import uuid

import httpx
import pytest
from app.core.db import async_session_factory
from app.main import create_app
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.runledger.models import RunLedger, RunStatus
from app.modules.runledger.service import run
from sqlalchemy import delete, select, update


@pytest.mark.integration
async def test_run_context_manager_success() -> None:
    async with async_session_factory() as session:
        async with run(session, kind="test_success_task", ref="ref-1") as handle:
            handle.seen(5)
            handle.created(2)
            handle.add_cost(tokens_in=100, tokens_out=50, usd=0.005)

    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    delete(RunLedger)
                    .where(RunLedger.kind == "test_success_task")
                    .returning(RunLedger)
                )
            )
            .scalars()
            .all()
        )
        await session.commit()
        assert len(rows) == 1
        r = rows[0]
        assert r.status == RunStatus.SUCCESS
        assert r.items_seen == 5
        assert r.items_created == 2
        assert r.tokens_in == 100
        assert r.tokens_out == 50
        assert r.cost_usd == 0.005
        assert r.duration_ms is not None and r.duration_ms >= 0


@pytest.mark.integration
async def test_run_context_manager_failure_captures_error() -> None:
    with pytest.raises(RuntimeError, match="simulated failure"):
        async with async_session_factory() as session:
            async with run(session, kind="test_failed_task") as handle:
                handle.seen(1)
                raise RuntimeError("simulated failure")

    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    delete(RunLedger)
                    .where(RunLedger.kind == "test_failed_task")
                    .returning(RunLedger)
                )
            )
            .scalars()
            .all()
        )
        await session.commit()
        assert len(rows) == 1
        r = rows[0]
        assert r.status == RunStatus.FAILED
        assert r.error_kind == "RuntimeError"
        assert "simulated failure" in (r.error_detail or "")


@pytest.mark.integration
async def test_runledger_admin_api_requires_staff() -> None:
    """These two endpoints (ADM-2, ADM-5) served the AI spend figures to anyone
    with the URL -- no auth dependency at all. Pins all three outcomes:
    unauthenticated 401, authenticated-but-not-staff 403, staff 200."""
    async with async_session_factory() as session:
        async with run(session, kind="test_api_task") as handle:
            handle.add_cost(tokens_in=10, tokens_out=10, usd=0.001)

    email = f"admin-{uuid.uuid4()}@example.com"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="https://t"
        ) as client:
            anon = await client.get("/api/v1/admin/run-ledger")
            assert anon.status_code == 401, anon.text

            reg = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": "correct horse battery staple",
                    "org_name": "Admin Test Org",
                    "org_type": "diaspora",
                    "country": "US",
                    "timezone": "America/Los_Angeles",
                },
            )
            assert reg.status_code == 201, reg.text

            non_staff = await client.get("/api/v1/admin/run-ledger")
            assert non_staff.status_code == 403, non_staff.text

            # Promote the same user; the session cookie is unchanged, so a 200
            # here can only come from is_staff being read on each request.
            async with async_session_factory() as session:
                await session.execute(update(User).where(User.email == email).values(is_staff=True))
                await session.commit()

            res = await client.get("/api/v1/admin/run-ledger")
            assert res.status_code == 200, res.text
            assert any(item["kind"] == "test_api_task" for item in res.json())

            spend_res = await client.get("/api/v1/admin/run-ledger/spend", params={"days": 7})
            assert spend_res.status_code == 200
            spend = spend_res.json()
            assert spend["total_runs"] >= 1
            assert spend["total_tokens_in"] >= 10
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(RunLedger).where(RunLedger.kind == "test_api_task"))
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is not None:
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
