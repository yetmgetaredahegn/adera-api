"""Pure-logic unit tests for M8 Notifications (SKILLS.md R6, NFR-INTL-1)."""

import uuid
from datetime import UTC, datetime

from app.modules.notifications.models import NotificationChannel, NotificationEventType
from app.modules.notifications.service import (
    make_idempotency_key,
    should_send_digest_now,
)


def test_should_send_digest_now_matching_hour() -> None:
    # 05:00 UTC == 08:00 EAT (Africa/Addis_Ababa, UTC+3)
    utc_time = datetime(2026, 7, 24, 5, 0, 0, tzinfo=UTC)
    assert should_send_digest_now("Africa/Addis_Ababa", target_hour=8, current_utc=utc_time) is True


def test_should_send_digest_now_non_matching_hour() -> None:
    # 06:00 UTC == 09:00 EAT
    utc_time = datetime(2026, 7, 24, 6, 0, 0, tzinfo=UTC)
    assert (
        should_send_digest_now("Africa/Addis_Ababa", target_hour=8, current_utc=utc_time) is False
    )


def test_should_send_digest_now_diaspora_timezone() -> None:
    # 15:00 UTC == 08:00 PDT (America/Los_Angeles, UTC-7)
    utc_time = datetime(2026, 7, 24, 15, 0, 0, tzinfo=UTC)
    assert (
        should_send_digest_now("America/Los_Angeles", target_hour=8, current_utc=utc_time) is True
    )


def test_idempotency_key_format() -> None:
    u_id = uuid.uuid4()
    t_id = uuid.uuid4()
    key = make_idempotency_key(u_id, t_id, NotificationChannel.EMAIL, NotificationEventType.DIGEST)
    assert key == f"{u_id}:{t_id}:email:digest"
