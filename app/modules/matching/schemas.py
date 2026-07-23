"""Matching output contracts (M7, FR-7.2).

Mirrors extraction/schemas.py: the Pydantic model is both the LLM's forced
output shape and the validator that rejects malformed responses before they
reach the database.
"""

from pydantic import BaseModel, Field


class ExplanationOut(BaseModel):
    """Prompt B3's output — the grounded "why this fits you" paragraph.

    Eval C3 (master plan Appendix C) gates this: zero unsupported claims. The
    prompt enforces grounding; this schema only enforces shape.
    """

    explanation: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
