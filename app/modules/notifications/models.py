"""M8 — Notifications (FR-8.1, FR-8.2, FR-8.4, NFR-INTL-1).

Channel-level idempotency spine: `unique(user_id, tender_id, channel, event_type)`
prevents double-sending notifications even if Celery retries a task.
"""

import enum
import uuid

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class NotificationChannel(enum.StrEnum):
    EMAIL = "email"
    TELEGRAM = "telegram"


class NotificationEventType(enum.StrEnum):
    DIGEST = "digest"
    INSTANT = "instant"


class NotificationLog(UUIDPk, Timestamps, Base):
    __tablename__ = "notifications_log"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tender_id",
            "channel",
            "event_type",
            name="uq_notifications_log_idempotency",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel"), index=True
    )
    event_type: Mapped[NotificationEventType] = mapped_column(
        pg_enum(NotificationEventType, "notification_event_type"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
