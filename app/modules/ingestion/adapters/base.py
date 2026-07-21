"""Adapter contract (05 §4).

Adding a source is: one adapter file here + one `sources` row + golden fixtures.
Nothing else in the codebase changes. An adapter's whole job is to turn a source's
native shape (JSON, HTML, PDF listing) into a list of `RawTender` — the normalized
hand-off the rest of the pipeline understands.
"""

from datetime import datetime
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.modules.sources.models import Source


class RawTender(BaseModel):
    """One tender as an adapter sees it, before extraction/embedding.

    `source_tender_id` + the source is the idempotency key (FR-2.3). `raw` keeps the
    adapter's original record verbatim so extraction can improve without re-fetching.
    Money is minor units + ISO currency (NFR-INTL-2). Times are tz-aware UTC (NFR-INTL-1).
    """

    source_tender_id: str
    url: str
    title: str
    buyer: str | None = None
    summary: str | None = None
    region: str | None = None
    language: str | None = None

    published_at: datetime | None = None
    closing_at: datetime | None = None

    bid_bond_minor: int | None = None
    bid_bond_currency: str | None = None
    doc_price_minor: int | None = None
    doc_price_currency: str | None = None

    raw: dict[str, object]


class Adapter(Protocol):
    """A source adapter. `fetch` does the network I/O and normalization."""

    key: str

    async def fetch(self, client: httpx.AsyncClient, source: Source) -> list[RawTender]: ...
