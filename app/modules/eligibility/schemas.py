"""Eligibility output contract (M16, FR-16.2, prompt B6).

Same double duty as extraction/matching/qualification schemas: the LLM's
forced output shape AND the validator that rejects malformed responses.
"""

from pydantic import BaseModel, Field

from app.modules.matching.models import EligibilityVerdict


class Citation(BaseModel):
    document_name: str
    article_ref: str


class EligibilityOut(BaseModel):
    verdict: EligibilityVerdict
    reasons: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
