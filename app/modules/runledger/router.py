"""Admin Run Ledger router (M11, FR-11.1, FR-11.5)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_admin
from app.modules.runledger import service
from app.modules.runledger.schemas import RunLedgerOut, SpendSummaryOut

# Every route here is admin-only (docs/11 §0). Declared on the router rather than
# per-route so a future ADM-* endpoint added to this file cannot be shipped
# unguarded by forgetting a decorator argument.
router = APIRouter(
    prefix="/api/v1/admin/run-ledger",
    tags=["admin"],
    dependencies=[Depends(current_admin)],
)


@router.get("", response_model=list[RunLedgerOut])
async def list_runs(
    kind: str | None = Query(default=None, description="filter by task kind"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[RunLedgerOut]:
    runs = await service.list_runs(session, limit=limit, kind=kind)
    return [RunLedgerOut.model_validate(r) for r in runs]


@router.get("/spend", response_model=SpendSummaryOut)
async def get_spend_summary(
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
) -> SpendSummaryOut:
    stats = await service.get_summary_stats(session, days=days)
    return SpendSummaryOut.model_validate(stats)
