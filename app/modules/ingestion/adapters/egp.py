"""e-GP public tender listing adapter (Phase 1/2, per ADR-027).

PUBLIC, UNAUTHENTICATED ONLY (docs/ADRs/027-source-access-legality.md --
Status: Proposed). This adapter calls egp.gov.et's own public API, discovered
by loading the public `/bids/all` page in a headless browser with NO
credentials and observing its network calls -- a Playwright session that
never touched a login field, only navigated and read. The endpoint itself was
then verified with a bare `curl`, zero cookies, zero auth headers: it returns
real structured JSON (220 real tenders at discovery time, 2026-07-24). It is
what backs e-GP's own public "Total Active Tenders" dashboard shown to every
anonymous visitor -- this is data e-GP already serves to the public, not a
leak found by probing.

THIS ADAPTER MUST NEVER GAIN A LOGIN STEP. If e-GP ever requires
authentication for this endpoint, disable this adapter -- do not "upgrade" it
to log in. See ADR-027 for the reasoning and its still-open questions.

No stable per-tender deep link was found in the inspectable JS bundle (the
lazy-loaded bid-detail route wasn't reachable via static analysis) -- `url`
below points at the general public listing, not a specific tender page. Worth
revisiting if e-GP's routing changes or a detail route is found.
"""

from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.modules.ingestion.adapters.base import RawTender
from app.modules.sources.models import Source

API_URL = "https://egp.gov.et/po-gw/cms-v2/api/sourcing/get-grouped-sourcing"
PUBLIC_LISTING_URL = "https://egp.gov.et/egp/bids/all"
PAGE_SIZE = 50  # server-enforced max observed at discovery -- a larger `top` is silently capped


def _parse_dt(value: str | None) -> datetime | None:
    """e-GP mixes two date formats (space- and T-separated), and
    `invitation_date` was observed at discovery with an implausible UTC
    offset (-07:00 on what should be Addis Ababa's +03:00) -- a known
    upstream data-quality quirk. Parsed as given, never guessed into a
    "corrected" offset; FR-4.4 already means downstream code treats a single
    date field as fallible, not a source of silent certainty."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T", 1))
    except ValueError:
        return None


def _money_minor(amount: float | int | None, currency: str | None) -> tuple[int | None, str | None]:
    """NFR-INTL-2: integer minor units + ISO currency, never float.
    `bid_security_amount`/`bid_currency` were observed always 0/null in a
    100-tender sample at discovery -- this still has to handle a real value
    correctly when one eventually appears."""
    if not amount or not currency:
        return None, None
    return round(amount * 100), currency


def _text(value: object) -> str | None:
    """Several e-GP text fields (observed live: `procuring_entity`) come back
    as a localized object (`{"am": "...", "en": "..."}`) instead of a plain
    string, inconsistently with the 100-row sample used at discovery, which
    happened to only show plain strings there. Prefer English, fall back to
    Amharic, then any value present, rather than crashing on the shape."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("en", "am"):
            v = value.get(key)
            if isinstance(v, str) and v:
                return v
        for v in value.values():
            if isinstance(v, str) and v:
                return v
        return None
    return str(value)


def parse(payload: dict[str, Any]) -> list[RawTender]:
    """Pure function: e-GP API JSON -> list[RawTender]. Unit-tested against a
    fixture with no network (05 §4). Iterates per LOT, not per package --
    `result` can hold multiple lots per procurement package, each separately
    biddable (the schema supports it even though none in the discovery sample
    had more than one)."""
    out: list[RawTender] = []
    for package in payload.get("items", []):
        for lot in package.get("result", []):
            info = lot.get("packageInformation") or {}
            ref = lot.get("lotReferenceNo") or lot.get("id")
            if not ref:
                continue
            bond_minor, bond_currency = _money_minor(
                info.get("bid_security_amount"), info.get("bid_currency")
            )
            title = _text(lot.get("lotName")) or _text(info.get("name")) or str(ref)
            out.append(
                RawTender(
                    source_tender_id=str(ref),
                    url=PUBLIC_LISTING_URL,
                    title=title.strip(),
                    buyer=_text(info.get("procuring_entity")),
                    summary=_text(info.get("description")) or _text(lot.get("lotDescription")),
                    region=_text((info.get("address") or {}).get("town")),
                    language=_text(info.get("quatation_request_language")),
                    published_at=_parse_dt(info.get("invitation_date")),
                    closing_at=_parse_dt(
                        info.get("submission_deadline") or lot.get("submissionDeadline")
                    ),
                    bid_bond_minor=bond_minor,
                    bid_bond_currency=bond_currency,
                    raw=lot,
                )
            )
    return out


class EGPAdapter:
    key = "egp"

    async def fetch(self, client: httpx.AsyncClient, source: Source) -> list[RawTender]:
        page_size = int(str(source.fetch_config.get("page_size", PAGE_SIZE)))
        # A conservative page cap (FR-2.5: be a good citizen) -- not "fetch
        # everything at any cost." Revisit once real ingestion volume is known.
        max_pages = int(str(source.fetch_config.get("max_pages", 10)))
        out: list[RawTender] = []
        skip = 0
        for _ in range(max_pages):
            resp = await client.get(
                API_URL,
                params={
                    "type": "all",
                    "skip": skip,
                    "top": page_size,
                    "locale": "en",
                    "orderBy[0].field": "invitationDate",
                    "orderBy[0].direction": "desc",
                },
                headers={"User-Agent": settings.fetch_user_agent},
                timeout=settings.fetch_timeout_seconds,
            )
            resp.raise_for_status()
            payload = resp.json()
            out.extend(parse(payload))
            total = int(payload.get("total", 0))
            skip += page_size
            if skip >= total:
                break
        return out
