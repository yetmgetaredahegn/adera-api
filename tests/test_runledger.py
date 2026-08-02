"""Unit & integration tests for M11 Run Ledger & Operations Dashboard (FR-11.1, FR-11.5)."""

import uuid

import httpx
import pytest
from app.core.db import async_session_factory
from app.main import create_app
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.runledger.models import RunLedger, RunStatus
from app.modules.runledger.service import run
from sqlalchemy import delete, select


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


async def _register(client: httpx.AsyncClient, email: str) -> None:
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


async def _cleanup_user(email: str) -> None:
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
            await session.execute(delete(Org).where(Org.id == m.org_id))
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.execute(delete(OrgMember).where(OrgMember.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_runledger_admin_api_requires_platform_admin() -> None:
    """Found live 2026-08-02: these endpoints had NO auth check at all --
    proving the gate now exists is as important as proving it lets the right
    people through (AGENTS.md rule 9's spirit, applied to platform admin
    rather than tenant isolation)."""
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://t"
        ) as client:
            await _register(client, email)
            # A regular, non-staff bidder org must be refused -- 403, not a
            # silent empty list (which would look like "no runs exist").
            res = await client.get("/api/v1/admin/run-ledger")
            assert res.status_code == 403, res.text
            spend_res = await client.get("/api/v1/admin/run-ledger/spend")
            assert spend_res.status_code == 403, spend_res.text

            # Also fully unauthenticated (no session at all) -- 401 via the
            # underlying current_user dependency, not a crash.
            anon = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app()), base_url="http://t"
            )
            async with anon as anon_client:
                anon_res = await anon_client.get("/api/v1/admin/run-ledger")
                assert anon_res.status_code == 401, anon_res.text
    finally:
        await _cleanup_user(email)


@pytest.mark.integration
async def test_runledger_admin_api_endpoints_for_platform_admin() -> None:
    async with async_session_factory() as session:
        async with run(session, kind="test_api_task") as handle:
            handle.add_cost(tokens_in=10, tokens_out=10, usd=0.001)

    email = f"test-admin-{uuid.uuid4()}@example.com"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://t"
        ) as client:
            await _register(client, email)
            async with async_session_factory() as session:
                user = (await session.execute(select(User).where(User.email == email))).scalar_one()
                user.is_staff = True
                await session.commit()

            res = await client.get("/api/v1/admin/run-ledger")
            assert res.status_code == 200, res.text
            items = res.json()
            assert any(item["kind"] == "test_api_task" for item in items)

            spend_res = await client.get("/api/v1/admin/run-ledger/spend", params={"days": 7})
            assert spend_res.status_code == 200, spend_res.text
            spend = spend_res.json()
            assert spend["total_runs"] >= 1
            assert spend["total_tokens_in"] >= 10
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(RunLedger).where(RunLedger.kind == "test_api_task"))
            await session.commit()
        await _cleanup_user(email)
