"""Column mixins shared across modules.

NFR-INTL-1: timestamps are stored in UTC and localized only at render time.
`DateTime(timezone=True)` + server-side now() keeps that true regardless of the
client's clock.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDelete:
    """04 §4: soft delete for tenant-owned rows.

    Audit-immutable tables (run_ledger, ledger_entries, proof_artifacts) must NOT
    use this — they are append-only by design.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
