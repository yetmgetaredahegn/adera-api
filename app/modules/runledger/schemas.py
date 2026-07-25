"""Run Ledger Pydantic schemas (M11, FR-11.1, FR-11.5)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.runledger.models import RunStatus


class RunLedgerOut(BaseModel):
    """Single run ledger entry schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    ref: str | None
    status: RunStatus

    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None

    items_seen: int
    items_created: int
    items_updated: int
    items_unchanged: int

    tokens_in: int
    tokens_out: int
    cost_usd: float

    error_kind: str | None
    error_detail: str | None


class SpendSummaryOut(BaseModel):
    """AI token spend & cost summary (FR-11.5, NFR-COST-1)."""

    total_runs: int
    successful_runs: int
    failed_runs: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
