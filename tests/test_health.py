"""Week 1 DoD: the app boots and reports dependency health honestly."""

import httpx
import pytest
from app.main import create_app


@pytest.mark.integration
async def test_healthz_reports_ok_when_db_reachable() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["checks"]["db"] is True


async def test_healthz_reports_unhealthy_rather_than_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A probe must be able to tell "Postgres is down" from "the app is down".

    If /healthz raised on a dead database, both would look identical to Uptime
    Kuma and the alert would point at the wrong thing.
    """
    import app.main as main_module

    class _BrokenEngine:
        def connect(self):  # type: ignore[no-untyped-def]
            raise OSError("connection refused")

    monkeypatch.setattr(main_module, "engine", _BrokenEngine())

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["checks"]["db"] is False
