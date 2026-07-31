"""Notification delivery (M8, FR-8.1/8.2).

Honest status: both senders are real, tested integrations (httpx calls to
each provider's actual REST API, mocked in tests -- no network in the suite,
R6) but genuinely UNEXERCISED against a live provider. No BREVO_API_KEY or
TELEGRAM_BOT_TOKEN exists in this environment. Each send_* function returns
False (never raises) when its key is unset, so the digest sweep degrades to
"scheduling only" -- exactly what it already does today -- rather than
crashing once only one of the two is eventually configured.
"""

import httpx
from app.core.config import settings
from app.modules.notifications.schemas import DigestItemOut

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _format_digest_html(items: list[DigestItemOut]) -> str:
    rows = "".join(
        "<li><strong>{title}</strong> — {buyer}{deadline}</li>".format(
            title=item.title,
            buyer=item.buyer or "Unknown buyer",
            deadline=f" (closes {item.closing_at.date().isoformat()})" if item.closing_at else "",
        )
        for item in items
    )
    return f"<p>Your new ADERA tender matches:</p><ul>{rows}</ul>"


def _format_digest_text(items: list[DigestItemOut]) -> str:
    lines = [f"• {item.title} — {item.buyer or 'Unknown buyer'}" for item in items]
    return "Your new ADERA tender matches:\n" + "\n".join(lines)


async def send_digest_email(to_email: str, items: list[DigestItemOut]) -> bool:
    """Returns True if actually sent, False if skipped (no key) or the
    provider rejected it -- never raises, per this module's docstring."""
    if not settings.brevo_api_key or not items:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                BREVO_API_URL,
                headers={
                    "api-key": settings.brevo_api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "sender": {"email": settings.brevo_sender_email},
                    "to": [{"email": to_email}],
                    "subject": "Your new ADERA tender matches",
                    "htmlContent": _format_digest_html(items),
                },
            )
    except httpx.HTTPError:
        return False
    return resp.status_code < 300


async def send_digest_telegram(chat_id: str, items: list[DigestItemOut]) -> bool:
    if not settings.telegram_bot_token or not items:
        return False

    url = TELEGRAM_API_URL.format(token=settings.telegram_bot_token)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url, json={"chat_id": chat_id, "text": _format_digest_text(items)}
            )
    except httpx.HTTPError:
        return False
    return resp.status_code < 300
