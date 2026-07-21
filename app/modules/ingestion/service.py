"""Ingestion service (M2, FR-2.3) — the idempotency spine.

`upsert_tender` is why the pipeline can crash mid-run and simply be re-run: a
second pass finds the existing row by (source_id, source_tender_id), updates it,
and never creates a duplicate. The unique constraint in the DB is the guarantee;
this function is how we act on it and report which of the three things happened.
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.adapters.base import RawTender
from app.modules.ingestion.models import Tender
from app.modules.sources.models import Source

# Fields an adapter is allowed to write onto a tender. Kept explicit so a re-fetch
# never clobbers fields that later pipeline stages own (embedding, bidding_track).
_ADAPTER_FIELDS = (
    "url",
    "title",
    "buyer",
    "summary",
    "region",
    "language",
    "published_at",
    "closing_at",
    "bid_bond_minor",
    "bid_bond_currency",
    "doc_price_minor",
    "doc_price_currency",
)


class UpsertResult(enum.StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


async def upsert_tender(
    session: AsyncSession, source: Source, raw: RawTender
) -> tuple[Tender, UpsertResult]:
    now = datetime.now(UTC)
    existing = (
        await session.execute(
            select(Tender).where(
                Tender.source_id == source.id,
                Tender.source_tender_id == raw.source_tender_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        tender = Tender(
            source_id=source.id,
            source_tender_id=raw.source_tender_id,
            raw_data=raw.raw,
            first_seen_at=now,
            last_seen_at=now,
            **{f: getattr(raw, f) for f in _ADAPTER_FIELDS},
        )
        session.add(tender)
        await session.flush()
        return tender, UpsertResult.CREATED

    # Seen before: did anything the adapter owns actually change?
    changed = False
    for field_name in _ADAPTER_FIELDS:
        new_value = getattr(raw, field_name)
        if getattr(existing, field_name) != new_value:
            setattr(existing, field_name, new_value)
            changed = True
    if existing.raw_data != raw.raw:
        existing.raw_data = raw.raw
        changed = True

    existing.last_seen_at = now
    await session.flush()
    return existing, (UpsertResult.UPDATED if changed else UpsertResult.UNCHANGED)
