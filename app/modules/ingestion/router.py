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
from app.kernel.router import build_kernel
from app.modules.ingestion import service
from app.modules.ingestion.models import BiddingTrack
from app.modules.ingestion.schemas import (
    TenderListOut,
    TenderOut,
    TenderQAIn,
    TenderQAOut,
)
from app.modules.qualification.service import list_qualified_sectors

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


@router.get("/search", response_model=TenderListOut)
async def search_tenders(
    q: str | None = Query(default=None, description="search query"),
    region: str | None = Query(default=None, description="filter by region"),
    bidding_track: BiddingTrack | None = Query(default=None, description="filter by bidding track"),
    after: str | None = Query(default=None, description="opaque cursor from next_after"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> TenderListOut:
    try:
        tenders = await service.search_tenders(
            session, q=q, region=region, bidding_track=bidding_track, after=after, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid `after` cursor") from exc

    next_after = service.encode_cursor(tenders[-1]) if len(tenders) == limit else None
    return TenderListOut(
        items=[TenderOut.model_validate(t) for t in tenders],
        next_after=next_after,
    )


@router.get("/sectors", response_model=list[str])
async def list_sectors(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Real sector strings seen across qualified tenders (M6 profile builder) --
    NOT a hand-picked list. Must stay declared before `/{tender_id}` or FastAPI
    tries to parse "sectors" as a tender UUID and 422s instead of matching here."""
    return await list_qualified_sectors(session)


@router.get("/{tender_id}", response_model=TenderOut)
async def get_tender(
    tender_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TenderOut:
    tender = await service.get_tender(session, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")
    return TenderOut.model_validate(tender)


@router.post("/{tender_id}/qa", response_model=TenderQAOut)
async def tender_qa(
    tender_id: uuid.UUID,
    body: TenderQAIn,
    session: AsyncSession = Depends(get_session),
) -> TenderQAOut:
    tender = await service.get_tender(session, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="tender not found")

    answer, citations, confidence = await service.answer_tender_qa(
        session, tender_id, body.question, kernel=build_kernel()
    )
    return TenderQAOut(
        tender_id=tender_id,
        question=body.question,
        answer=answer,
        citations=citations,
        confidence=confidence,
    )
