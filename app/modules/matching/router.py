"""Per-org matches endpoint (M7, FR-7.1). Reads persisted `Match` rows —
ranking itself (with its LLM explanation call, matching/service.py::match_org)
happens out-of-request, not synchronously on every GET (that would mean an
LLM call on every page load).

Tenant isolation is enforced entirely by `Depends(current_org)` — the
`org_id` filter below IS the boundary AGENTS.md rule 9 requires a leak test
for; see tests/test_matches_tenant_isolation.py.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_org
from app.core.errors import APIError
from app.modules.identity.service import AudienceRestricted, Org, require_bidder_audience
from app.modules.ingestion.schemas import TenderOut
from app.modules.ingestion.service import Tender
from app.modules.matching.models import Match, MatchState
from app.modules.matching.schemas import MatchOut, MatchStateOut
from app.modules.matching.service import MatchExpired, dismiss_match, get_org_match, save_match

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
async def list_matches(
    org: Org = Depends(current_org),
    state: MatchState | None = Query(default=None, description="filter to new|saved|dismissed"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[MatchOut]:
    # ADR-029: gated here too, not just in match_org() -- this endpoint reads
    # persisted rows directly and never calls match_org(), so a local org
    # with pre-pivot match rows must still get a plain 403, not a silent
    # (possibly non-empty) list.
    try:
        require_bidder_audience(org)
    except AudienceRestricted as exc:
        raise APIError(403, "audience_restricted", str(exc)) from exc

    # No ?state=: the default feed, which never shows dismissed items (FR-7.3).
    # ?state=dismissed is honored explicitly (e.g. an admin/debug view) --
    # only the unfiltered default hides them.
    state_filter = (
        (Match.state == state) if state is not None else (Match.state != MatchState.DISMISSED)
    )
    matches = (
        (
            await session.execute(
                select(Match)
                .where(Match.org_id == org.id, state_filter)
                .order_by(Match.score.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    if not matches:
        return []

    tender_ids = [m.tender_id for m in matches]
    tenders = {
        t.id: t
        for t in (await session.execute(select(Tender).where(Tender.id.in_(tender_ids)))).scalars()
    }
    return [
        MatchOut(
            id=m.id,
            tender_id=m.tender_id,
            score=m.score,
            explanation=m.explanation,
            state=m.state,
            tender=TenderOut.model_validate(tenders[m.tender_id]),
        )
        for m in matches
        if m.tender_id in tenders
    ]


@router.post("/{match_id}/save", response_model=MatchStateOut)
async def save_match_route(
    match_id: uuid.UUID,
    org: Org = Depends(current_org),
    session: AsyncSession = Depends(get_session),
) -> MatchStateOut:
    match = await get_org_match(session, match_id, org.id)
    if match is None:
        raise APIError(404, "not_found", "match not found")
    tender = await session.get(Tender, match.tender_id)
    if tender is None:
        # Data-integrity bug (an FK-constrained row missing), not a client error.
        raise APIError(500, "internal", "match references a missing tender")
    try:
        await save_match(session, match, tender)
    except MatchExpired as exc:
        raise APIError(409, "expired", str(exc)) from exc
    return MatchStateOut(state=MatchState.SAVED)


@router.post("/{match_id}/dismiss", response_model=MatchStateOut)
async def dismiss_match_route(
    match_id: uuid.UUID,
    org: Org = Depends(current_org),
    session: AsyncSession = Depends(get_session),
) -> MatchStateOut:
    match = await get_org_match(session, match_id, org.id)
    if match is None:
        raise APIError(404, "not_found", "match not found")
    await dismiss_match(session, match)
    return MatchStateOut(state=MatchState.DISMISSED)
