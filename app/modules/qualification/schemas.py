"""Qualification output contract (M5, FR-5.2, prompt B2).

Same double duty as extraction/matching schemas: the LLM's forced output shape
AND the validator that rejects malformed responses before they reach the DB.
"""

from pydantic import BaseModel, Field

from app.modules.qualification.models import QualificationStatus, Urgency


class QualifyOut(BaseModel):
    status: QualificationStatus
    urgency: Urgency = Urgency.UNKNOWN
    sector: str | None = None
    reasons: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
