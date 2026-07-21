"""M7 — Matching (FR-7.1, FR-7.2, FR-7.3).

The `matches` row is the unit of value: not "here is a listing" but "here is a
judgment about you, and here is why."
"""

import enum
import uuid

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk


class MatchState(enum.StrEnum):
    NEW = "new"
    SAVED = "saved"
    # FR-7.3: dismissed never resurfaces. Respecting this is what makes the feed
    # trustworthy rather than nagging.
    DISMISSED = "dismissed"


class EligibilityVerdict(enum.StrEnum):
    """FR-16.2 / FR-7.6 — the chip on every card.

    `UNKNOWN` must be said plainly and must route to a facilitator, never guessed
    (NFR-LEGAL-1). Ineligible tenders are down-ranked and LABELED, never silently
    hidden — a bidder who can't see why is a bidder who doesn't trust us.
    """

    ELIGIBLE = "eligible"
    CONDITIONAL = "conditional"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class Match(UUIDPk, Timestamps, Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("tender_id", "org_id", name="uq_matches_tender_org"),)

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )

    # Cosine similarity from the vector stage, before re-rank.
    score: Mapped[float] = mapped_column(Float)

    # FR-7.2: the grounded one-paragraph "why this fits you" (prompt B3).
    # Eval C3 gates this: zero unsupported claims. If it cannot be grounded in
    # stated profile/extraction facts, it does not ship.
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    # Which prompt version produced it — a prompt is versioned software (§14),
    # so an explanation without its version is unreproducible.
    prompt_version: Mapped[str | None] = mapped_column(String(32), default=None)

    eligibility: Mapped[EligibilityVerdict] = mapped_column(
        pg_enum(EligibilityVerdict, "eligibility_verdict"),
        default=EligibilityVerdict.UNKNOWN,
    )

    state: Mapped[MatchState] = mapped_column(
        pg_enum(MatchState, "match_state"),
        default=MatchState.NEW,
        index=True,
    )
