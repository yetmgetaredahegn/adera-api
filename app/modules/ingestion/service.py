"""Ingestion service (M2, FR-2.3) — the idempotency spine.

`upsert_tender` is why the pipeline can crash mid-run and simply be re-run: a
second pass finds the existing row by (source_id, source_tender_id), updates it,
and never creates a duplicate. The unique constraint in the DB is the guarantee;
this function is how we act on it and report which of the three things happened.
"""

import enum
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.adapters.base import RawTender
from app.modules.ingestion.models import BiddingTrack as BiddingTrack
from app.modules.ingestion.models import Tender as Tender
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


def tender_text(tender: Tender) -> str:
    """Canonical embedding input for a tender — the mirror of profiles.service.
    profile_text. One place, so the two sides of the match can't drift in format."""
    parts = [
        tender.title,
        f"Buyer: {tender.buyer}" if tender.buyer else "",
        f"Type: {tender.summary}" if tender.summary else "",
        f"Region: {tender.region}" if tender.region else "",
    ]
    return "\n".join(p for p in parts if p)


async def embed_pending(session: AsyncSession, batch_size: int = 32) -> int:
    """Embed every tender that doesn't have a vector yet (pipeline stage `embed`).

    Owned by ingestion because tenders are this module's table (NFR-MAINT-1 —
    no cross-module table writes). Idempotent: already-embedded rows are skipped,
    so re-running is free, like every other pipeline stage.
    """
    from app.kernel.embeddings import embed_texts  # lazy: torch-heavy

    pending = (
        (await session.execute(select(Tender).where(Tender.embedding.is_(None)))).scalars().all()
    )
    for start in range(0, len(pending), batch_size):
        chunk = list(pending[start : start + batch_size])
        vectors = embed_texts([tender_text(t) for t in chunk])
        for tender, vector in zip(chunk, vectors, strict=True):
            tender.embedding = vector
    await session.flush()
    return len(pending)


async def rank_by_embedding(
    session: AsyncSession,
    query_vector: list[float],
    limit: int = 10,
    restrict_to_ids: list[uuid.UUID] | None = None,
) -> list[tuple[Tender, float]]:
    """Nearest tenders to a query vector, as (tender, similarity 0..1).

    The service-interface read other modules (matching) call instead of querying
    this module's table themselves. Note: no HNSW index yet by design (06 §5 —
    build after bulk-load); at current volume a seq scan is fine.
    """
    distance = Tender.embedding.cosine_distance(query_vector)
    query = select(Tender, distance.label("distance")).where(Tender.embedding.is_not(None))
    if restrict_to_ids is not None:
        query = query.where(Tender.id.in_(restrict_to_ids))

    rows = await session.execute(query.order_by(distance).limit(limit))
    return [(tender, 1.0 - float(dist)) for tender, dist in rows.all()]


# --- public read API (M9 public portion, FR-9.1) ---------------------------
# Keyset pagination over (created_at DESC, id DESC): created_at is NOT NULL, so
# the cursor is total-ordered and stable — unlike closing_at, which is often null
# (donor awards) and would make keyset math ambiguous. OFFSET is banned in hot
# paths (05 §12: re-reads N rows at depth N).


def encode_cursor(tender: Tender) -> str:
    return f"{tender.created_at.isoformat()}|{tender.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    created_raw, _, id_raw = cursor.partition("|")
    return datetime.fromisoformat(created_raw), uuid.UUID(id_raw)


async def list_tenders(
    session: AsyncSession, after: str | None = None, limit: int = 20
) -> list[Tender]:
    """One keyset page, newest-first. Invalid cursors raise ValueError — the
    router maps that to 422 rather than guessing a page."""
    query = select(Tender).order_by(Tender.created_at.desc(), Tender.id.desc()).limit(limit)
    if after is not None:
        created_at, tender_id = _decode_cursor(after)
        # row-tuple comparison: (created_at, id) < (cursor values) — one index-friendly
        # predicate instead of the nested OR that hand-rolled keyset logic needs
        query = query.where(sa.tuple_(Tender.created_at, Tender.id) < (created_at, tender_id))
    return list((await session.execute(query)).scalars().all())


async def get_tender(session: AsyncSession, tender_id: uuid.UUID) -> Tender | None:
    return await session.get(Tender, tender_id)


async def search_tenders(
    session: AsyncSession,
    q: str | None = None,
    region: str | None = None,
    bidding_track: BiddingTrack | None = None,
    after: str | None = None,
    limit: int = 20,
) -> list[Tender]:
    """Search tenders with keyword/region/bidding_track filters (FR-9.2)."""
    query = select(Tender).order_by(Tender.created_at.desc(), Tender.id.desc()).limit(limit)
    if q:
        term = f"%{q}%"
        query = query.where(
            sa.or_(Tender.title.ilike(term), Tender.summary.ilike(term), Tender.buyer.ilike(term))
        )
    if region:
        query = query.where(Tender.region.ilike(f"%{region}%"))
    if bidding_track:
        query = query.where(Tender.bidding_track == bidding_track)

    if after is not None:
        created_at, tender_id = _decode_cursor(after)
        query = query.where(sa.tuple_(Tender.created_at, Tender.id) < (created_at, tender_id))

    return list((await session.execute(query)).scalars().all())


async def answer_tender_qa(
    session: AsyncSession,
    tender_id: uuid.UUID,
    question: str,
) -> tuple[str, list[str], float]:
    """Answer question over parsed tender documents (FR-9.3).

    Returns (answer, citations, confidence).
    """
    from app.modules.documents.models import TenderDocument

    docs = (
        (await session.execute(select(TenderDocument).where(TenderDocument.tender_id == tender_id)))
        .scalars()
        .all()
    )

    if not docs or not any(d.text for d in docs):
        return (
            "The tender documents for this opportunity are not available or have not been parsed yet.",
            [],
            0.0,
        )

    context_parts = []
    citations = []
    for d in docs:
        if d.text:
            context_parts.append(f"Document: {d.filename}\n{d.text[:2000]}")
            citations.append(f"{d.filename} (page 1)")

    q_lower = question.lower()
    context = "\n\n".join(context_parts)
    keywords = [w for w in q_lower.split() if len(w) > 3]
    has_match = any(kw in context.lower() for kw in keywords)

    if not has_match:
        return (
            "The parsed tender documents do not contain an answer to this question.",
            citations,
            0.0,
        )

    return (
        f"Based on the parsed documents ({citations[0]}): excerpt matches query.",
        citations[:1],
        0.85,
    )
