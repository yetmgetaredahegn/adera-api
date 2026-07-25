"""Unit & integration tests for M11 Run Ledger & Operations Dashboard (FR-11.1, FR-11.5)."""

import httpx
import pytest
from app.core.db import async_session_factory
from app.main import create_app
from app.modules.runledger.models import RunLedger, RunStatus
from app.modules.runledger.service import run
from sqlalchemy import delete


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
async def test_runledger_admin_api_endpoints() -> None:
    async with async_session_factory() as session:
        async with run(session, kind="test_api_task") as handle:
            handle.add_cost(tokens_in=10, tokens_out=10, usd=0.001)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://t"
        ) as client:
            res = await client.get("/api/v1/admin/run-ledger")
            assert res.status_code == 200
            items = res.json()
            assert any(item["kind"] == "test_api_task" for item in items)

            spend_res = await client.get("/api/v1/admin/run-ledger/spend", params={"days": 7})
            assert spend_res.status_code == 200
            spend = spend_res.json()
            assert spend["total_runs"] >= 1
            assert spend["total_tokens_in"] >= 10
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(RunLedger).where(RunLedger.kind == "test_api_task"))
            await session.commit()
