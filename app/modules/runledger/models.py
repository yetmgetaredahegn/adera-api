"""M11 — Run Ledger (FR-11.1).

Every pipeline task wraps in `runledger.service.run(...)`, which records counts,
latency, token spend, and error taxonomy on exit — success *or* crash. The admin
dashboard is just SELECTs over this table, and the daily ops summary (FR-8.5) is
a Beat task formatting yesterday's rows.

Append-only and audit-immutable: no SoftDelete mixin here, deliberately.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk


class RunStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class RunLedger(UUIDPk, Timestamps, Base):
    __tablename__ = "run_ledger"

    kind: Mapped[str] = mapped_column(String(64), index=True)  # "fetch_source", "extract", ...
    ref: Mapped[str | None] = mapped_column(String(255), default=None)  # source key, tender id

    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"),
        default=RunStatus.RUNNING,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    # Idempotency evidence: re-running a fetch should move `unchanged`, not `created`.
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_created: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    items_unchanged: Mapped[int] = mapped_column(Integer, default=0)

    # NFR-COST-1: cost is a first-class metric, read weekly like the bill it is.
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Taxonomy, not just a message — "which of our known failure modes was this?"
    error_kind: Mapped[str | None] = mapped_column(String(64), default=None)
    error_detail: Mapped[str | None] = mapped_column(Text, default=None)

    meta: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
