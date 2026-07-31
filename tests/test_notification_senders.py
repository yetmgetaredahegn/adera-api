"""app/modules/notifications/senders.py (M8, FR-8.1/8.2) -- the first real
delivery integration; the digest scheduler previously recorded a notification
as "sent" without ever sending anything. No network (R6): httpx.AsyncClient.post
is monkeypatched, never a real call to Brevo/Telegram."""

import uuid

import httpx
import pytest
from app.modules.notifications.schemas import DigestItemOut
from app.modules.notifications.senders import send_digest_email, send_digest_telegram


def _item(title: str = "Test tender") -> DigestItemOut:
    return DigestItemOut(
        tender_id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        title=title,
        buyer="Ministry of Testing",
        region="Ethiopia",
        closing_at=None,
        score=0.9,
        explanation=None,
    )


def _fake_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", "https://example.test"))


@pytest.mark.asyncio
async def test_send_digest_email_skips_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.notifications.senders.settings.brevo_api_key", None)
    called = False

    async def fake_post(*_: object, **__: object) -> httpx.Response:
        nonlocal called
        called = True
        return _fake_response(200)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    sent = await send_digest_email("user@example.com", [_item()])
    assert sent is False
    assert called is False


@pytest.mark.asyncio
async def test_send_digest_email_skips_with_no_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.notifications.senders.settings.brevo_api_key", "fake-key")
    called = False

    async def fake_post(*_: object, **__: object) -> httpx.Response:
        nonlocal called
        called = True
        return _fake_response(200)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    sent = await send_digest_email("user@example.com", [])
    assert sent is False
    assert called is False


@pytest.mark.asyncio
async def test_send_digest_email_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.notifications.senders.settings.brevo_api_key", "fake-key")
    captured: dict[str, object] = {}

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs.get("headers")
        return _fake_response(201)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    item = _item("Solar mini-grid procurement")
    sent = await send_digest_email("user@example.com", [item])

    assert sent is True
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["to"] == [{"email": "user@example.com"}]
    assert "Solar mini-grid procurement" in body["htmlContent"]
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["api-key"] == "fake-key"


@pytest.mark.asyncio
async def test_send_digest_email_provider_rejection_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.notifications.senders.settings.brevo_api_key", "fake-key")

    async def fake_post(*_: object, **__: object) -> httpx.Response:
        return _fake_response(401)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    sent = await send_digest_email("user@example.com", [_item()])
    assert sent is False


@pytest.mark.asyncio
async def test_send_digest_email_network_error_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.notifications.senders.settings.brevo_api_key", "fake-key")

    async def fake_post(*_: object, **__: object) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    sent = await send_digest_email("user@example.com", [_item()])
    assert sent is False


@pytest.mark.asyncio
async def test_send_digest_telegram_skips_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.notifications.senders.settings.telegram_bot_token", None)
    sent = await send_digest_telegram("12345", [_item()])
    assert sent is False


@pytest.mark.asyncio
async def test_send_digest_telegram_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.modules.notifications.senders.settings.telegram_bot_token", "fake-token"
    )
    captured: dict[str, object] = {}

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return _fake_response(200)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    sent = await send_digest_telegram("12345", [_item("Road maintenance tender")])

    assert sent is True
    assert captured["url"] == "https://api.telegram.org/botfake-token/sendMessage"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["chat_id"] == "12345"
    assert "Road maintenance tender" in body["text"]
