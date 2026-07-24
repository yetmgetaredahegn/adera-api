"""M3 — Document Acquisition & Parsing (FR-3.1, FR-3.4).

`TenderDocument` stores parsed tender artifacts (PDFs, notice documents) with
extraction metadata, confidence, and language detection.
"""

import enum
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk


class ParseMethod(enum.StrEnum):
    PDFIUM = "pdfium"
    OCR = "ocr"
    DOCLING = "docling"


class TenderDocument(UUIDPk, Timestamps, Base):
    __tablename__ = "tender_documents"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(255), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    parse_method: Mapped[ParseMethod] = mapped_column(
        pg_enum(ParseMethod, "document_parse_method"), default=ParseMethod.PDFIUM
    )
    text: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    detected_language: Mapped[str | None] = mapped_column(String(8), default=None)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
