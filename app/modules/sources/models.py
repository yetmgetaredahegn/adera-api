"""M2 — Source Registry (FR-2.1).

Adding a source is: an adapter file in ingestion/adapters/, a row here, and
golden fixtures. Nothing else changes (05 §4).
"""

import enum

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import pg_enum
from app.core.mixins import Timestamps, UUIDPk


class SourceType(enum.StrEnum):
    HTML_STATIC = "html_static"  # httpx + selectolax — ~90% of sources
    HTML_DYNAMIC = "html_dynamic"  # Playwright, only where JS-rendered
    PDF = "pdf"
    API = "api"


class ToSStatus(enum.StrEnum):
    """FR-2.5 / §6 scraping conduct. A source is not enabled until this is
    reviewed — facts-not-expression, robots.txt honoured, link out, takedown SLA.
    """

    UNREVIEWED = "unreviewed"
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


class Source(UUIDPk, Timestamps, Base):
    __tablename__ = "sources"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # "egp"
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[SourceType] = mapped_column(pg_enum(SourceType, "source_type"))
    base_url: Mapped[str] = mapped_column(Text)

    # Adapter-specific knobs (list URL, selectors, pagination). Kept as JSONB so a
    # new source needs no migration.
    fetch_config: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)

    cron: Mapped[str] = mapped_column(String(64), default="0 * * * *")
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=20)

    tos_status: Mapped[ToSStatus] = mapped_column(
        pg_enum(ToSStatus, "tos_status"), default=ToSStatus.UNREVIEWED
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
