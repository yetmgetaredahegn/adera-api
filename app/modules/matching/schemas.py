"""Matching output contracts (M7, FR-7.2).

Mirrors extraction/schemas.py: the Pydantic model is both the LLM's forced
output shape and the validator that rejects malformed responses before they
reach the database.
"""

import enum
import uuid

from pydantic import BaseModel, Field

from app.modules.ingestion.schemas import TenderOut
from app.modules.matching.models import EligibilityVerdict, MatchState


class MatchStateFilter(enum.StrEnum):
    """What a client may ASK `GET /matches` for (docs/11 MAT-1).

    `dismissed` is deliberately absent rather than merely unsupported: FR-7.3
    makes dismissal terminal for the feed, so an endpoint that could list
    dismissed matches would be the first step toward resurfacing them.
    """

    NEW = "new"
    SAVED = "saved"


class ExplanationOut(BaseModel):
    """Prompt B3's output — the grounded "why this fits you" paragraph.

    Eval C3 (master plan Appendix C) gates this: zero unsupported claims. The
    prompt enforces grounding; this schema only enforces shape.
    """

    explanation: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class MatchOut(BaseModel):
    """Public shape for GET /api/v1/matches (org-scoped, FR-7.1)."""

    id: uuid.UUID
    tender_id: uuid.UUID
    score: float
    explanation: str | None
    state: MatchState
    # FR-16.2 / FR-7.6: the chip. Nothing sets this yet (M16 has no HTTP
    # surface and no pipeline stage), so it is `unknown` on every row today --
    # which is the honest verdict a client must render, not a reason to omit
    # the field and leave clients hardcoding a chip they cannot justify.
    eligibility: EligibilityVerdict
    tender: TenderOut
