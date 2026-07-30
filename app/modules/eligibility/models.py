"""M16 — Eligibility law corpus (FR-16.2, NFR-LEGAL-1).

`LawChunk` is the ONLY thing prompt B6 may cite. Every chunk carries the exact
citation a verdict must reference (document + article) — an eligibility
answer that cannot point at a real `LawChunk` row is not a valid answer.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.dialects.postgresql import TEXT as PG_TEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk
from app.modules.ingestion.models import EMBEDDING_DIM
from app.modules.matching.service import EligibilityVerdict


class LawChunk(UUIDPk, Timestamps, Base):
    __tablename__ = "law_chunks"

    # e.g. "Federal Public Procurement and Property Administration
    # Proclamation No. 1333/2024"
    document_name: Mapped[str] = mapped_column(String(255))
    document_url: Mapped[str] = mapped_column(Text)
    # e.g. "Article 2(1)" -- what a citation in a verdict actually points at.
    article_ref: Mapped[str] = mapped_column(String(64), index=True)
    # English only for now (the LLM prompt and citations are English-first;
    # the source PDF is bilingual Amharic/English -- see HANDOFF.md for the
    # real extraction story: only Article 2 (definitions) is ingested so far,
    # not the full document. Extending this needs careful, non-rushed
    # extraction work -- a wrong citation is worse than none, NFR-LEGAL-1.
    text_en: Mapped[str] = mapped_column(PG_TEXT)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), default=None)


class EligibilityAssessment(UUIDPk, Timestamps, Base):
    """ELI-1 cache (docs/11_API_REFERENCE.md: "computed on miss, cached").
    assess_eligibility() is a real LLM call plus a retrieval pass -- repeat
    views of the same tender by the same org must not re-spend budget."""

    __tablename__ = "eligibility_assessments"
    __table_args__ = (UniqueConstraint("org_id", "tender_id", name="uq_eligibility_org_tender"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), index=True
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    verdict: Mapped[EligibilityVerdict] = mapped_column(
        pg_enum(EligibilityVerdict, "eligibility_verdict")
    )
    # FR-16.2's "conditions" on the public contract -- named `reasons` here to
    # match EligibilityOut's existing, already-tested field; the router maps
    # the name at the response boundary, not here.
    reasons: Mapped[list[str]] = mapped_column(ARRAY(PG_TEXT), default=list)
    citations: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    law_version: Mapped[str] = mapped_column(String(64))
