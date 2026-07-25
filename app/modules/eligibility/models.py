"""M16 — Eligibility law corpus (FR-16.2, NFR-LEGAL-1).

`LawChunk` is the ONLY thing prompt B6 may cite. Every chunk carries the exact
citation a verdict must reference (document + article) — an eligibility
answer that cannot point at a real `LawChunk` row is not a valid answer.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import TEXT as PG_TEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import Timestamps, UUIDPk
from app.modules.ingestion.models import EMBEDDING_DIM


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
