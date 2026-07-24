"""Notifications Pydantic schemas (M8, FR-8.1)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DigestItemOut(BaseModel):
    tender_id: uuid.UUID
    title: str
    buyer: str | None
    region: str | None
    closing_at: datetime | None
    score: float
    explanation: str | None


class DigestPayloadOut(BaseModel):
    user_id: uuid.UUID
    email: str
    timezone: str
    items: list[DigestItemOut]
