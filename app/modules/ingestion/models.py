"""M2/M4 — Tenders (FR-2.3, FR-4.1).

The idempotency spine of the whole pipeline: `unique(source_id, source_tender_id)`
means re-running a fetch is free and safe. Everything upstream can retry.
"""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk

# BGE-M3 (ADR-009) — local, multilingual (critical for Amharic), 1024-dim.
EMBEDDING_DIM = 1024


class BiddingTrack(enum.StrEnum):
    """FR-16.1 — what the eligibility engine turns on.

    `UNKNOWN` is a first-class answer, not a failure: NFR-LEGAL-1 requires we say
    so plainly rather than guess (eval C5 forbids confident-wrong here).
    """

    NCB = "ncb"  # National Competitive Bidding — favours domestic bidders
    ICB = "icb"  # International Competitive Bidding
    DONOR = "donor"  # WB/AfDB/JICA/EU rules
    PRIVATE = "private"
    UNKNOWN = "unknown"


class Tender(UUIDPk, Timestamps, Base):
    __tablename__ = "tenders"
    __table_args__ = (
        # FR-2.3: idempotent upsert. This constraint IS the guarantee.
        UniqueConstraint("source_id", "source_tender_id", name="uq_tenders_source_ref"),
        # GIN on the raw payload so adapter-shape questions stay queryable
        # without a migration (master plan Appendix A).
        Index("ix_tenders_raw_data", "raw_data", postgresql_using="gin"),
        # Note: Appendix A also calls for a partial index on "is_open". That
        # cannot be `WHERE closing_at > now()` — index predicates must be
        # IMMUTABLE and now() is not. It needs either a maintained is_open
        # column or a scheduled reindex; deferred until there is enough data
        # for EXPLAIN to justify it (05 §12: indexes follow queries).
        # HNSW on `embedding` is deliberately absent: 06 §5 requires building it
        # AFTER bulk-load, so it lands in its own migration once tenders exist.
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), index=True
    )
    source_tender_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)

    # --- extracted fields (FR-4.1) -----------------------------------------
    title: Mapped[str] = mapped_column(Text)
    buyer: Mapped[str | None] = mapped_column(Text, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    region: Mapped[str | None] = mapped_column(String(128), default=None)
    # ISO-639-1: "en", "am", "om". FR-4.3 — must survive end-to-end uncorrupted.
    language: Mapped[str | None] = mapped_column(String(8), default=None)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # FR-4.4: a tender whose closing_at is low-confidence is NEVER notified.
    # Wrong deadlines are the one error that loses a user their bid.
    closing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
    opening_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # NFR-INTL-2: money is integer minor units + ISO currency. Never float.
    bid_bond_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    bid_bond_currency: Mapped[str | None] = mapped_column(String(3), default=None)
    doc_price_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    doc_price_currency: Mapped[str | None] = mapped_column(String(3), default=None)

    bidding_track: Mapped[BiddingTrack] = mapped_column(
        pg_enum(BiddingTrack, "bidding_track"),
        default=BiddingTrack.UNKNOWN,
        index=True,
    )

    # Raw adapter payload, kept verbatim (FR-2.3). When extraction improves, we
    # re-extract from this instead of re-scraping the source.
    raw_data: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), default=None)

    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
