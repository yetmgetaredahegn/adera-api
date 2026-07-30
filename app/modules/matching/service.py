"""Matching service (M7, FR-7.1/7.2/7.3).

Flow (05 §7): profile vector -> candidate set (via ingestion.service.rank_by_embedding,
the owning module's read interface) -> similarity floor -> persist `matches` ->
(optional) LLM-grounded explanation (prompt B3).

Honesty notes still true:
- No sector pre-filter yet: tenders don't carry a sector until qualification (M5)
  assigns one — see `docs/QUALIFICATION_PREFILTER.md` (owner: Temesgen). Pure
  vector ranking is the honest current scope.
- No eligibility pre-filter (FR-7.6) yet: that is M16 (Phase 2). Verdict stays
  `unknown` — a first-class value, per NFR-LEGAL-1.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kernel.prompts import load_prompt
from app.kernel.router import Kernel
from app.modules.identity.service import get_org, require_bidder_audience
from app.modules.ingestion.service import Tender, rank_by_embedding
from app.modules.matching.models import (
    EligibilityVerdict as EligibilityVerdict,
)
from app.modules.matching.models import (
    Match as Match,
)
from app.modules.matching.models import (
    MatchState as MatchState,
)
from app.modules.matching.schemas import ExplanationOut
from app.modules.profiles.models import CompanyProfile as CompanyProfile
from app.modules.profiles.service import get_profile
from app.modules.qualification.service import get_qualified_tender_ids

# Below this cosine similarity a "match" is noise; tune on the eval set later
# (06 §6 — the floor is also most of NFR-LEGAL-1's honesty, applied to matching).
SIMILARITY_FLOOR = 0.45

PROMPT_VERSION = "v1"


class MatchExpired(Exception):
    """Raised by `save_match` when the tender has already closed (MAT-2,
    docs/11_API_REFERENCE.md: 409 expired). Dismissing has no such rule --
    a user must always be able to dismiss, expired or not."""


@dataclass
class RankedMatch:
    tender: Tender
    score: float
    persisted: bool  # False = already existed (FR-7.3: never duplicate, never resurface)
    explanation: str | None = None  # set only when a kernel was supplied and it succeeded


def _profile_text(profile: CompanyProfile) -> str:
    """Only CONFIRMED facts (FR-6.1) — an unconfirmed chip is a guess, and B3
    may not build a claim on a guess."""
    lines = [
        f"Sectors: {', '.join(profile.sectors) or 'none confirmed'}",
        f"Capabilities: {', '.join(profile.capabilities) or 'none confirmed'}",
        f"Certifications: {', '.join(profile.certifications) or 'none confirmed'}",
        f"Regions: {', '.join(profile.regions) or 'none confirmed'}",
    ]
    return "\n".join(lines)


def _tender_text(tender: Tender) -> str:
    """Only extracted fields — never the raw untrusted document (NFR-SEC-2)."""
    deadline = tender.closing_at.isoformat() if tender.closing_at else "unknown/no deadline stated"
    bond = (
        f"{tender.bid_bond_minor / 100:.2f} {tender.bid_bond_currency}"
        if tender.bid_bond_minor is not None and tender.bid_bond_currency
        else "none stated"
    )
    lines = [
        f"Title: {tender.title}",
        f"Buyer: {tender.buyer or 'unknown'}",
        f"Region: {tender.region or 'unknown'}",
        f"Closing: {deadline}",
        f"Bid bond: {bond}",
    ]
    return "\n".join(lines)


async def _explain(kernel: Kernel, profile: CompanyProfile, tender: Tender) -> str | None:
    """Grounded "why this fits you" (prompt B3). Returns None on any failure —
    a bad or malformed model response must never break ranking, and must never
    be faked (AGENTS.md rule 11: never simulate model output)."""
    prompt = (
        load_prompt("explain", PROMPT_VERSION)
        .replace("{profile}", _profile_text(profile))
        .replace("{tender}", _tender_text(tender))
    )
    try:
        result = await kernel.complete(
            task="explain",
            prompt=prompt,
            schema=ExplanationOut,
            prompt_version=PROMPT_VERSION,
        )
    except ValidationError:
        return None
    except Exception:
        # errors (rate limit, network, budget breaker); rule 2 forbids importing
        # litellm here to catch a narrower type. A failed explanation must never
        # break ranking (AGENTS.md rule 11: verify, don't crash on a soft path).
        return None
    return result.explanation


async def match_org(
    session: AsyncSession,
    org_id: uuid.UUID,
    limit: int = 10,
    kernel: Kernel | None = None,
) -> list[RankedMatch]:
    """Rank tenders for one org and persist new matches. Idempotent per (org, GROUP)
    (ADR-028) — not per (org, tender): a sibling tender from another source in an
    already-matched group is never matched again, so the same real-world
    opportunity surfacing via a second source doesn't spend a second explanation
    or show as a second "new" card.

    `kernel` is optional (mirrors extraction.service.extract): when absent, or for
    matches that already existed, no explanation is generated — never faked, per
    AGENTS.md rule 11. When present, only NEWLY persisted matches are explained,
    so re-ranking an org never re-spends budget on matches it already showed them.

    Raises `identity.service.AudienceRestricted` for a `local`-type org (ADR-029)
    — never a silently empty list, which would be indistinguishable from "no
    matches today" and hide that the feature was never meant for this org.
    """
    org = await get_org(session, org_id)
    if org is None:
        raise ValueError(f"org {org_id} does not exist")
    require_bidder_audience(org)

    profile = await get_profile(session, org_id)
    if profile is None or profile.profile_embedding is None:
        raise ValueError(f"org {org_id} has no embedded profile — build it first (FR-6.1)")

    allowed_ids = await get_qualified_tender_ids(session, profile.sectors)

    candidates = await rank_by_embedding(
        session, profile.profile_embedding, limit=limit, restrict_to_ids=allowed_ids
    )

    # ADR-028: keyed on the tender's GROUP, not its own id -- a Match for any
    # tender in a group counts as "already matched" for every sibling tender
    # in that group, regardless of which source's row was matched first.
    existing_group_ids = set(
        (
            await session.execute(
                select(Tender.group_id)
                .join(Match, Match.tender_id == Tender.id)
                .where(Match.org_id == org_id)
            )
        ).scalars()
    )

    out: list[RankedMatch] = []
    for tender, score in candidates:
        if score < SIMILARITY_FLOOR:
            continue
        is_new = tender.group_id not in existing_group_ids
        explanation: str | None = None
        if is_new:
            if kernel is not None:
                explanation = await _explain(kernel, profile, tender)
            session.add(
                Match(
                    tender_id=tender.id,
                    org_id=org_id,
                    score=score,
                    state=MatchState.NEW,
                    explanation=explanation,
                    prompt_version=PROMPT_VERSION if explanation is not None else None,
                )
            )
            # Mark the group covered immediately -- two sibling tenders from
            # the same group both ranking above the floor in ONE call must
            # still produce only one Match, not two.
            existing_group_ids.add(tender.group_id)
        out.append(
            RankedMatch(tender=tender, score=score, persisted=is_new, explanation=explanation)
        )
    await session.flush()
    return out


async def get_org_match(
    session: AsyncSession, match_id: uuid.UUID, org_id: uuid.UUID
) -> Match | None:
    """Scoped by org_id in the query itself, not checked after the fact --
    a match belonging to another org must read as `None` (404), never leak
    that the id exists (AGENTS.md rule 9)."""
    return (
        await session.execute(select(Match).where(Match.id == match_id, Match.org_id == org_id))
    ).scalar_one_or_none()


async def save_match(session: AsyncSession, match: Match, tender: Tender) -> None:
    """MAT-2. Raises `MatchExpired` if the tender's deadline has already
    passed -- a null closing_at (unknown/no deadline stated, the common World
    Bank case) is NOT expired; only a known, past deadline is."""
    if tender.closing_at is not None and tender.closing_at < datetime.now(UTC):
        raise MatchExpired(f"tender {tender.id} closed at {tender.closing_at.isoformat()}")
    match.state = MatchState.SAVED
    await session.flush()


async def dismiss_match(session: AsyncSession, match: Match) -> None:
    """MAT-3, FR-7.3: dismissed never resurfaces -- unconditional, no expiry
    check, since a user must always be able to dismiss."""
    match.state = MatchState.DISMISSED
    await session.flush()
