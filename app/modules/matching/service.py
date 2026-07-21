"""Matching service (M7, FR-7.1/7.3) — Week 3 spike scope.

Flow (05 §7): profile vector -> candidate set (via ingestion.service.rank_by_embedding,
the owning module's read interface) -> similarity floor -> persist `matches`.

Spike honesty notes:
- No sector pre-filter yet: tenders don't carry a sector until qualification (M5,
  Week 4) assigns one. Pure vector ranking is the honest current scope.
- No LLM re-rank / grounded explanation yet: prompt B3 exists
  (prompts/explain/v1.md) but requires an API key this environment doesn't have.
  `explanation` stays NULL rather than faked (never simulate model output).
- No eligibility pre-filter (FR-7.6) yet: that is M16 (Phase 2). Verdict stays
  `unknown` — a first-class value, per NFR-LEGAL-1.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.models import Tender
from app.modules.ingestion.service import rank_by_embedding
from app.modules.matching.models import Match, MatchState
from app.modules.profiles.service import get_profile

# Below this cosine similarity a "match" is noise; tune on the eval set later
# (06 §6 — the floor is also most of NFR-LEGAL-1's honesty, applied to matching).
SIMILARITY_FLOOR = 0.45


@dataclass
class RankedMatch:
    tender: Tender
    score: float
    persisted: bool  # False = already existed (FR-7.3: never duplicate, never resurface)


async def match_org(session: AsyncSession, org_id: uuid.UUID, limit: int = 10) -> list[RankedMatch]:
    """Rank tenders for one org and persist new matches. Idempotent per (tender, org)."""
    profile = await get_profile(session, org_id)
    if profile is None or profile.profile_embedding is None:
        raise ValueError(f"org {org_id} has no embedded profile — build it first (FR-6.1)")

    candidates = await rank_by_embedding(session, profile.profile_embedding, limit=limit)

    existing_ids = set(
        (await session.execute(select(Match.tender_id).where(Match.org_id == org_id))).scalars()
    )

    out: list[RankedMatch] = []
    for tender, score in candidates:
        if score < SIMILARITY_FLOOR:
            continue
        is_new = tender.id not in existing_ids
        if is_new:
            session.add(
                Match(tender_id=tender.id, org_id=org_id, score=score, state=MatchState.NEW)
            )
        out.append(RankedMatch(tender=tender, score=score, persisted=is_new))
    await session.flush()
    return out
