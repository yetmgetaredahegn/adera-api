"""Per-org matches endpoints (M7, FR-7.1/7.3). Reads persisted `Match` rows —
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
from app.core.deps import current_org, require_csrf
from app.core.errors import (
    AUDIENCE_RESTRICTED,
    CSRF_FAILED,
    FORBIDDEN,
    NOT_FOUND,
    ORG_ID_REQUIRED,
    RATE_LIMITED,
    UNAUTHENTICATED,
    APIError,
    problems,
)
from app.modules.identity.service import AudienceRestricted, Org, require_bidder_audience
from app.modules.ingestion.schemas import TenderOut
from app.modules.ingestion.service import Tender
from app.modules.matching.models import Match, MatchState
from app.modules.matching.schemas import MatchOut, MatchStateFilter
from app.modules.matching.service import set_match_state

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])

_READ_PROBLEMS = problems(
    UNAUTHENTICATED, FORBIDDEN, AUDIENCE_RESTRICTED, ORG_ID_REQUIRED, NOT_FOUND, RATE_LIMITED
)
_WRITE_PROBLEMS = problems(
    UNAUTHENTICATED,
    FORBIDDEN,
    CSRF_FAILED,
    AUDIENCE_RESTRICTED,
    ORG_ID_REQUIRED,
    NOT_FOUND,
    RATE_LIMITED,
)


def _to_out(match: Match, tender: Tender) -> MatchOut:
    return MatchOut(
        id=match.id,
        tender_id=match.tender_id,
        score=match.score,
        explanation=match.explanation,
        state=match.state,
        eligibility=match.eligibility,
        tender=TenderOut.model_validate(tender),
    )


async def _apply_state(
    session: AsyncSession, org: Org, match_id: uuid.UUID, state: MatchState
) -> MatchOut:
    """Shared tail of MAT-2 and MAT-3: gate, write, and hand back the canonical
    row so a client can redraw the card without a second round trip."""
    _require_bidder(org)
    match = await set_match_state(session, org.id, match_id, state)
    if match is None:
        raise APIError(404, NOT_FOUND.code, "match not found")
    tender = await session.get(Tender, match.tender_id)
    if tender is None:
        # FK is ON DELETE CASCADE, so a match without its tender is corruption,
        # not a client error.
        raise APIError(500, "internal", "match points at a tender that no longer exists")
    return _to_out(match, tender)


def _require_bidder(org: Org) -> None:
    # ADR-029: gated in the HTTP layer too, not just in match_org() -- these
    # endpoints touch persisted rows directly and never call match_org(), so a
    # local org with pre-pivot match rows must still get a plain 403, not a
    # silent (possibly non-empty) list.
    try:
        require_bidder_audience(org)
    except AudienceRestricted as exc:
        raise APIError(403, AUDIENCE_RESTRICTED.code, str(exc)) from exc


@router.get("", response_model=list[MatchOut], responses=_READ_PROBLEMS)
async def list_matches(
    org: Org = Depends(current_org),
    state: MatchStateFilter | None = Query(
        default=None, description="filter to one state; omit for everything not dismissed"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[MatchOut]:
    _require_bidder(org)

    query = select(Match).where(Match.org_id == org.id)
    # FR-7.3: dismissed rows are excluded on every path through this query --
    # the filter cannot ask for them (MatchStateFilter has no such member), and
    # the unfiltered default excludes them explicitly rather than by omission.
    query = (
        query.where(Match.state == MatchState(state.value))
        if state is not None
        else query.where(Match.state != MatchState.DISMISSED)
    )
    matches = (
        (await session.execute(query.order_by(Match.score.desc()).limit(limit))).scalars().all()
    )
    if not matches:
        return []

    tender_ids = [m.tender_id for m in matches]
    tenders = {
        t.id: t
        for t in (await session.execute(select(Tender).where(Tender.id.in_(tender_ids)))).scalars()
    }
    return [_to_out(m, tenders[m.tender_id]) for m in matches if m.tender_id in tenders]


@router.post("/{match_id}/save", response_model=MatchOut, responses=_WRITE_PROBLEMS)
async def save_match(
    match_id: uuid.UUID,
    org: Org = Depends(current_org),
    _: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
) -> MatchOut:
    """MAT-2. Server-side so a save follows the user to their next device — a
    client-local heart is a promise the product cannot keep. docs/11 specifies
    `200 {state:"saved"}`; the full row is a superset of that, and saves the
    client a refetch to redraw the card."""
    return await _apply_state(session, org, match_id, MatchState.SAVED)


@router.post("/{match_id}/dismiss", response_model=MatchOut, responses=_WRITE_PROBLEMS)
async def dismiss_match(
    match_id: uuid.UUID,
    org: Org = Depends(current_org),
    _: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
) -> MatchOut:
    """MAT-3. FR-7.3 makes this permanent: the row stays (so ranking still
    knows this group was judged) but never appears in a feed again. Trust in
    the feed is built on exactly this — a dismissal that comes back is a
    product that nags."""
    return await _apply_state(session, org, match_id, MatchState.DISMISSED)
