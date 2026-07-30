"""Eligibility output contract (M16, FR-16.2, prompt B6).

Same double duty as extraction/matching/qualification schemas: the LLM's
forced output shape AND the validator that rejects malformed responses.
"""

from pydantic import BaseModel, Field

from app.modules.eligibility.models import EligibilityAssessment
from app.modules.matching.service import EligibilityVerdict


class Citation(BaseModel):
    document_name: str
    article_ref: str


class EligibilityOut(BaseModel):
    verdict: EligibilityVerdict
    reasons: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class EligibilityResponseOut(BaseModel):
    """ELI-1's public shape (docs/11_API_REFERENCE.md): `conditions`, not
    `reasons` -- the contract's naming, kept separate from EligibilityOut's
    already-tested internal field name rather than renaming it everywhere."""

    verdict: EligibilityVerdict
    conditions: list[str]
    citations: list[Citation]
    confidence: float
    law_version: str
    disclaimer: bool = True

    @classmethod
    def from_assessment(cls, row: EligibilityAssessment) -> "EligibilityResponseOut":
        return cls(
            verdict=row.verdict,
            conditions=row.reasons,
            citations=[Citation(**c) for c in row.citations],
            confidence=row.confidence,
            law_version=row.law_version,
        )
