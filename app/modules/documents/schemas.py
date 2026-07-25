"""Document Acquisition & Parsing schemas (M3, FR-3.1)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.documents.models import ParseMethod


class DocumentOut(BaseModel):
    id: uuid.UUID
    tender_id: uuid.UUID
    filename: str
    mime_type: str
    file_size_bytes: int
    parse_method: ParseMethod
    confidence: float
    detected_language: str | None
    char_count: int
    created_at: datetime
