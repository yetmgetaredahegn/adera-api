"""Public tender endpoints (M9 public portion, FR-9.1) — the API clients build on.

PUBLIC BY DESIGN: tender facts are public data (they're published announcements;
our public SEO pages expose the same facts). No tenant data here — matches, saves,
and anything org-scoped waits for auth and will declare `Depends(current_org)` +
ship with a two-org leak test (AGENTS.md rule 9).

Router stays thin (05 §3): parse → service → schema. `response_model=` is mandatory
so only the contract's explicit fields ever leave the process.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.ingestion import service
from app.modules.ingestion.schemas import TenderListOut, TenderOut

router = APIRouter(prefix="/api/v1/tenders", tags=["tenders"])


@router.get("", response_model=TenderListOut)
async def list_tenders(
    after: str | None = Query(default=None, description="opaque cursor from next_after"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> TenderListOut:
    try:
        tenders = await service.list_tenders(session, after=after, limit=limit)
    except ValueError as exc:  # malformed cursor — client bug, say so plainly
        raise HTTPException(status_code=422, detail="invalid `after` cursor") from exc

    # next_after only when the page is full; a short page is the last page.
    next_after = service.encode_cursor(tenders[-1]) if len(tenders) == limit else None
    return TenderListOut(
        items=[TenderOut.model_validate(t) for t in tenders],
        next_after=next_after,
    )


@router.get("/{tender_id}", response_model=TenderOut)
async def get_tender(
    tender_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TenderOut:
    tender = await service.get_tender(session, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    return TenderOut.model_validate(tender)
