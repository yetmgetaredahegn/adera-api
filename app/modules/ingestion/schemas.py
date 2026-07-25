"""Public API contracts for tenders (M9 public portion, FR-9.1).

Response models are EXPLICIT field lists — never `from_orm` the whole row — so a
column added to the table later (e.g. internal moderation flags) can't leak into
the public contract by accident. These schemas ARE the contract that client repos
generate Dart/TS models from (ADR-025), so changes here are contract changes:
additive is fine, breaking means /api/v2.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.ingestion.models import BiddingTrack


class TenderOut(BaseModel):
    """One tender, public fields only (facts + link-out — FR-9.1)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    buyer: str | None
    summary: str | None
    region: str | None
    language: str | None
    url: str

    published_at: datetime | None
    # UTC always; clients render user-local + EAT (NFR-INTL-1). May be null —
    # many donor notices are awards with no deadline; null is honest (FR-4.4).
    closing_at: datetime | None
    opening_at: datetime | None

    # Money: integer minor units + ISO currency (NFR-INTL-2). Clients format.
    bid_bond_minor: int | None
    bid_bond_currency: str | None
    doc_price_minor: int | None
    doc_price_currency: str | None

    bidding_track: BiddingTrack


class TenderListOut(BaseModel):
    """Keyset-paginated page (05 §12 — stable and O(1) at any depth, unlike OFFSET).

    `next_after` is an opaque cursor: pass it back as ?after= to get the next page;
    null means last page.
    """

    items: list[TenderOut]
    next_after: str | None


class TenderQAIn(BaseModel):
    """Question over a tender's parsed documents (FR-9.3)."""

    question: str


class TenderQAOut(BaseModel):
    """Answer with citations or refusal (FR-9.3, prompt B4)."""

    tender_id: uuid.UUID
    question: str
    answer: str
    citations: list[str]
    confidence: float
