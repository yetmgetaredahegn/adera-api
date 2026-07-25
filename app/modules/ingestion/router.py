"""Public tender endpoints (M9 public portion, FR-9.1) — the API clients build on.

PUBLIC BY DESIGN: tender facts are public data (they're published announcements;
our public SEO pages expose the same facts). No tenant data here — matches, saves,
and anything org-scoped waits for auth and will declare `Depends(current_org)` +
ship with a two-org leak test (AGENTS.md rule 9).

Router stays thin (05 §3): parse → service → schema. `response_model=` is mandatory
so only the contract's explicit fields ever leave the process.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import NOT_FOUND, RATE_LIMITED, VALIDATION_ERROR, APIError, problems
from app.modules.ingestion import service
from app.modules.ingestion.models import BiddingTrack
from app.modules.ingestion.schemas import (
    TenderListOut,
    TenderOut,
    TenderQAIn,
    TenderQAOut,
)

router = APIRouter(prefix="/api/v1/tenders", tags=["tenders"])

# A cursor this API did not issue is a client bug, reported like any other
# schema failure — 422 is already documented app-wide (app/core/errors.py).
_BAD_CURSOR_DETAIL = "`after` is not a cursor this API issued; restart from page one"


@router.get("", response_model=TenderListOut, responses=problems(RATE_LIMITED))
async def list_tenders(
    after: str | None = Query(default=None, description="opaque cursor from next_after"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> TenderListOut:
    try:
        tenders = await service.list_tenders(session, after=after, limit=limit)
    except ValueError as exc:  # malformed cursor — client bug, say so plainly
        raise APIError(422, VALIDATION_ERROR.code, _BAD_CURSOR_DETAIL) from exc

    # next_after only when the page is full; a short page is the last page.
    next_after = service.encode_cursor(tenders[-1]) if len(tenders) == limit else None
    return TenderListOut(
        items=[TenderOut.model_validate(t) for t in tenders],
        next_after=next_after,
    )


@router.get("/search", response_model=TenderListOut, responses=problems(RATE_LIMITED))
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
        raise APIError(422, VALIDATION_ERROR.code, _BAD_CURSOR_DETAIL) from exc

    next_after = service.encode_cursor(tenders[-1]) if len(tenders) == limit else None
    return TenderListOut(
        items=[TenderOut.model_validate(t) for t in tenders],
        next_after=next_after,
    )


@router.get("/{tender_id}", response_model=TenderOut, responses=problems(NOT_FOUND, RATE_LIMITED))
async def get_tender(
    tender_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TenderOut:
    tender = await service.get_tender(session, tender_id)
    if tender is None:
        raise APIError(404, NOT_FOUND.code, "tender not found")
    return TenderOut.model_validate(tender)


@router.post(
    "/{tender_id}/qa", response_model=TenderQAOut, responses=problems(NOT_FOUND, RATE_LIMITED)
)
async def tender_qa(
    tender_id: uuid.UUID,
    body: TenderQAIn,
    session: AsyncSession = Depends(get_session),
) -> TenderQAOut:
    tender = await service.get_tender(session, tender_id)
    if tender is None:
        raise APIError(404, NOT_FOUND.code, "tender not found")

    answer, citations, confidence = await service.answer_tender_qa(
        session, tender_id, body.question
    )
    return TenderQAOut(
        tender_id=tender_id,
        question=body.question,
        answer=answer,
        citations=citations,
        confidence=confidence,
    )
