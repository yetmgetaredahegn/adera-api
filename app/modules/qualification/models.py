"""M5 — Qualification (FR-5.1/5.2/5.3/5.4).

One row per tender, updated in place on re-qualification (FR-5.3) rather than
appended — `updated_at` (Timestamps mixin) IS the "last qualified" timestamp.
"""

import enum
import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.dialects.postgresql import TEXT as PG_TEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk


class QualificationStatus(enum.StrEnum):
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    # FR-5.4: lands in a review queue, never silently dropped or silently shown.
    NEEDS_REVIEW = "needs_review"


class Urgency(enum.StrEnum):
    URGENT = "urgent"  # <=7 days
    SOON = "soon"  # 8-14 days
    NORMAL = "normal"  # >14 days
    UNKNOWN = "unknown"  # no closing_at


class QualificationMethod(enum.StrEnum):
    """Which stage produced this verdict — cost/audit transparency (FR-5.1's
    'zero-cost prefilter first' only means something if you can see which
    tenders it actually caught for free)."""

    RULE = "rule"
    LLM = "llm"


class Qualification(UUIDPk, Timestamps, Base):
    __tablename__ = "qualifications"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    status: Mapped[QualificationStatus] = mapped_column(
        pg_enum(QualificationStatus, "qualification_status"), index=True
    )
    urgency: Mapped[Urgency] = mapped_column(
        pg_enum(Urgency, "qualification_urgency"), default=Urgency.UNKNOWN
    )
    sector: Mapped[str | None] = mapped_column(String(128), default=None)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(PG_TEXT), default=list)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    method: Mapped[QualificationMethod] = mapped_column(
        pg_enum(QualificationMethod, "qualification_method")
    )
    # FR-5.2: "model + raw response persisted" — null for RULE-method rows (no
    # model was called). NEVER hand-edit raw_response; it is the audit trail.
    # `none_as_null=True` matters: without it, SQLAlchemy binds a Python None
    # for a JSON/JSONB column as the JSON literal `null` (a non-NULL row that
    # merely contains "null"), not SQL NULL — verified live: `raw_response IS
    # NULL` silently matched zero RULE rows until this was set. `count(col)`
    # and any `IS NULL`/`IS NOT NULL` filter would otherwise misclassify every
    # RULE-method row as having a stored response.
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    raw_response: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), default=None
    )

    # Human correction (FR-5.4: "one-click correct; corrections become golden
    # labels"). Null until a human overrides the automated verdict. Distinct
    # constraint name from `status` above — reusing "qualification_status" on a
    # second column would collide (two CHECK constraints, same name, one table).
    corrected_status: Mapped[QualificationStatus | None] = mapped_column(
        pg_enum(QualificationStatus, "qualification_status_corrected"), default=None
    )
    correction_note: Mapped[str | None] = mapped_column(Text, default=None)
