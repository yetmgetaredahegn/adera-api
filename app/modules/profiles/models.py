"""M6 — Company Profiles & Embeddings (FR-6.1, FR-6.2)."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.dialects.postgresql import TEXT as PG_TEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import SoftDelete, Timestamps, UUIDPk
from app.modules.ingestion.models import EMBEDDING_DIM


class CompanyProfile(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "company_profiles"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), unique=True, index=True
    )

    # What the user pasted (site copy, capability statement). Kept because
    # re-embedding on a better model must not require re-asking the user.
    source_text: Mapped[str] = mapped_column(Text)

    # FR-6.1: LLM-drafted chips the user CONFIRMS. Confirmation is what makes
    # these citable facts for the grounded explanation (B3) — an unconfirmed
    # chip is a guess, and B3 may not build a claim on a guess.
    sectors: Mapped[list[str]] = mapped_column(ARRAY(PG_TEXT), default=list)
    capabilities: Mapped[list[str]] = mapped_column(ARRAY(PG_TEXT), default=list)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(PG_TEXT), default=list)
    regions: Mapped[list[str]] = mapped_column(ARRAY(PG_TEXT), default=list)

    profile_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), default=None
    )
