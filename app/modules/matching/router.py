"""Per-org matches endpoint (M7, FR-7.1). Reads persisted `Match` rows —
ranking itself (with its LLM explanation call, matching/service.py::match_org)
happens out-of-request, not synchronously on every GET (that would mean an
LLM call on every page load).

Tenant isolation is enforced entirely by `Depends(current_org)` — the
`org_id` filter below IS the boundary AGENTS.md rule 9 requires a leak test
for; see tests/test_matches_tenant_isolation.py.
"""

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
from app.modules.matching.schemas import MatchOut

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
async def list_matches(
    org: Org = Depends(current_org),
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

    matches = (
        (
            await session.execute(
                select(Match)
                .where(Match.org_id == org.id, Match.state != MatchState.DISMISSED)
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
