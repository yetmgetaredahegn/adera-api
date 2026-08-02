"""Admin Run Ledger router (M11, FR-11.1, FR-11.5)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_platform_admin
from app.modules.identity.models import User
from app.modules.runledger import service
from app.modules.runledger.schemas import RunLedgerOut, SpendSummaryOut

router = APIRouter(prefix="/api/v1/admin/run-ledger", tags=["admin"])


@router.get("", response_model=list[RunLedgerOut])
async def list_runs(
    kind: str | None = Query(default=None, description="filter by task kind"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_platform_admin),
) -> list[RunLedgerOut]:
    runs = await service.list_runs(session, limit=limit, kind=kind)
    return [RunLedgerOut.model_validate(r) for r in runs]


@router.get("/spend", response_model=SpendSummaryOut)
async def get_spend_summary(
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_platform_admin),
) -> SpendSummaryOut:
    stats = await service.get_summary_stats(session, days=days)
    return SpendSummaryOut.model_validate(stats)
