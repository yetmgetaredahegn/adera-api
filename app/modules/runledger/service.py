"""Run-ledger service (FR-11.1).

`run(...)` is an async context manager that opens a ledger row, hands you a
handle to record counts and cost, and closes the row on exit — recording success
*or* failure with a duration. Every pipeline task wraps its work in it, so the
admin dashboard (later) is just SELECTs over one table, and a crash is still a
row (status=failed) rather than silence.

Usage:
    async with run(session, kind="fetch_source", ref="worldbank") as rl:
        ...
        rl.seen(10); rl.created(3); rl.unchanged(7)
        rl.add_cost(tokens_in=0, tokens_out=0, usd=0.0)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.runledger.models import RunLedger as RunLedger
from app.modules.runledger.models import RunStatus as RunStatus


@dataclass
class RunHandle:
    """A mutable tally the caller updates; flushed to the row on exit."""

    items_seen: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    meta: dict[str, object] = field(default_factory=dict)

    def seen(self, n: int = 1) -> None:
        self.items_seen += n

    def created(self, n: int = 1) -> None:
        self.items_created += n

    def updated(self, n: int = 1) -> None:
        self.items_updated += n

    def unchanged(self, n: int = 1) -> None:
        self.items_unchanged += n

    def add_cost(self, tokens_in: int = 0, tokens_out: int = 0, usd: float = 0.0) -> None:
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.cost_usd += usd


@asynccontextmanager
async def run(session: AsyncSession, kind: str, ref: str | None = None) -> AsyncIterator[RunHandle]:
    started = datetime.now(UTC)
    row = RunLedger(kind=kind, ref=ref, status=RunStatus.RUNNING, started_at=started)
    session.add(row)
    await session.flush()  # get row.id without ending the caller's transaction

    handle = RunHandle()
    try:
        yield handle
    except Exception as exc:
        # A failure must still leave a row — silence is the enemy (FR-11.1).
        # Commit the failure record on its own so the caller's rollback of the
        # work doesn't also erase the evidence that it was attempted.
        await session.rollback()
        row = await session.get(RunLedger, row.id) or row
        _finalize(row, handle, started, status=RunStatus.FAILED, exc=exc)
        session.add(row)
        await session.commit()
        raise
    else:
        _finalize(row, handle, started, status=RunStatus.SUCCESS)
        await session.commit()


def _finalize(
    row: RunLedger,
    handle: RunHandle,
    started: datetime,
    status: RunStatus,
    exc: Exception | None = None,
) -> None:
    finished = datetime.now(UTC)
    row.status = status
    row.finished_at = finished
    row.duration_ms = int((finished - started).total_seconds() * 1000)
    row.items_seen = handle.items_seen
    row.items_created = handle.items_created
    row.items_updated = handle.items_updated
    row.items_unchanged = handle.items_unchanged
    row.tokens_in = handle.tokens_in
    row.tokens_out = handle.tokens_out
    row.cost_usd = handle.cost_usd
    row.meta = handle.meta
    if exc is not None:
        row.error_kind = type(exc).__name__
        row.error_detail = str(exc)[:2000]


async def list_runs(
    session: AsyncSession, limit: int = 50, kind: str | None = None
) -> list[RunLedger]:
    """Fetch recent run ledger entries (FR-11.1)."""
    query = select(RunLedger).order_by(RunLedger.started_at.desc()).limit(limit)
    if kind:
        query = query.where(RunLedger.kind == kind)
    return list((await session.execute(query)).scalars().all())


async def get_summary_stats(session: AsyncSession, days: int = 7) -> dict[str, object]:
    """Aggregate token spend, cost, and run stats over recent period (FR-11.5, NFR-COST-1)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    query = select(
        func.count(RunLedger.id).label("total_runs"),
        func.coalesce(func.sum(func.cast(RunLedger.status == RunStatus.SUCCESS, Integer)), 0).label(
            "successful_runs"
        ),
        func.coalesce(func.sum(func.cast(RunLedger.status == RunStatus.FAILED, Integer)), 0).label(
            "failed_runs"
        ),
        func.coalesce(func.sum(RunLedger.tokens_in), 0).label("total_tokens_in"),
        func.coalesce(func.sum(RunLedger.tokens_out), 0).label("total_tokens_out"),
        func.coalesce(func.sum(RunLedger.cost_usd), 0.0).label("total_cost_usd"),
    ).where(RunLedger.started_at >= cutoff)

    row = (await session.execute(query)).one()
    return {
        "total_runs": row.total_runs,
        "successful_runs": row.successful_runs,
        "failed_runs": row.failed_runs,
        "total_tokens_in": row.total_tokens_in,
        "total_tokens_out": row.total_tokens_out,
        "total_cost_usd": float(row.total_cost_usd),
    }
