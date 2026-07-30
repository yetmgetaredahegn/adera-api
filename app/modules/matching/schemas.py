"""Matching output contracts (M7, FR-7.2).

Mirrors extraction/schemas.py: the Pydantic model is both the LLM's forced
output shape and the validator that rejects malformed responses before they
reach the database.
"""

import uuid

from pydantic import BaseModel, Field

from app.modules.ingestion.schemas import TenderOut
from app.modules.matching.models import MatchState


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
    tender: TenderOut


class MatchStateOut(BaseModel):
    """MAT-2/MAT-3 response shape (docs/11_API_REFERENCE.md): the target
    state only -- constructed directly, never by re-serializing the mutated
    ORM row (the same onupdate=func.now()-triggered MissingGreenlet risk
    profiles/router.py hit on its UPDATE path; a minimal literal response
    sidesteps it entirely rather than needing another session.refresh())."""

    state: MatchState
