"""Extraction output contract (M4, FR-4.1).

This Pydantic model does double duty (the FastAPI/Pydantic pattern): it is the
schema the LLM is forced to return for unstructured sources, and the validator
that rejects malformed model output before it can reach the database (FR-4.4).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TenderExtraction(BaseModel):
    title: str
    buyer: str | None = None
    summary: str | None = None
    region: str | None = None
    language: str | None = None

    published_at: datetime | None = None
    # FR-4.4: the field we are strictest about — a wrong closing date loses a bid.
    closing_at: datetime | None = None

    # NFR-INTL-2: integer minor units + ISO currency; never float.
    bid_bond_minor: int | None = None
    bid_bond_currency: str | None = None
    doc_price_minor: int | None = None
    doc_price_currency: str | None = None

    # Per-field confidence 0..1 (FR-4.2). Low confidence -> review, never published.
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
