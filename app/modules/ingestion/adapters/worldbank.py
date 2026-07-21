"""World Bank procurement-notices adapter — a Phase-1 donor-portal source.

The master plan lists "donor portals (WB/AfDB/JICA/EU)" among Phase-1 sources. The
World Bank exposes a public, no-auth JSON API of procurement notices that filters
cleanly to Ethiopia — real Ethiopian donor-funded tenders, structured well enough
that extraction is deterministic (FR-4.2), so no LLM is needed to ingest it.

API: https://search.worldbank.org/api/v2/procnotices
     ?format=json&rows=N&project_ctry_name_exact=Ethiopia
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.modules.ingestion.adapters.base import RawTender
from app.modules.sources.models import Source

API_URL = "https://search.worldbank.org/api/v2/procnotices"


def _parse_dt(value: str | None) -> datetime | None:
    """WB dates come as ISO ('2026-08-18T00:00:00Z') or '14-Jul-2026'. Missing is
    fine — a Contract Award has no deadline, and FR-4.4 would rather have None than
    a wrong closing date."""
    if not value:
        return None
    for fmt in ("iso", "%d-%b-%Y"):
        try:
            if fmt == "iso":
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse(payload: dict[str, Any]) -> list[RawTender]:
    """Pure function: WB API JSON -> list[RawTender]. Unit-tested against a fixture
    with no network (05 §4)."""
    out: list[RawTender] = []
    for row in payload.get("procnotices", []):
        notice_id = str(row.get("id", "")).strip()
        if not notice_id:
            continue
        out.append(
            RawTender(
                source_tender_id=notice_id,
                url=f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{notice_id}",
                title=(row.get("bid_description") or row.get("project_name") or notice_id).strip(),
                buyer=row.get("contact_organization") or row.get("project_name"),
                summary=row.get("notice_type"),
                region=row.get("project_ctry_name"),
                language=(row.get("notice_lang_name") or "English")[:8].lower()[:2] or None,
                published_at=_parse_dt(row.get("noticedate")),
                closing_at=_parse_dt(row.get("submission_deadline_date")),
                raw=row,
            )
        )
    return out


class WorldBankAdapter:
    key = "worldbank"

    async def fetch(self, client: httpx.AsyncClient, source: Source) -> list[RawTender]:
        rows = int(str(source.fetch_config.get("rows", 60)))
        country = str(source.fetch_config.get("country", "Ethiopia"))
        resp = await client.get(
            API_URL,
            params={"format": "json", "rows": rows, "project_ctry_name_exact": country},
            headers={"User-Agent": settings.fetch_user_agent},
            timeout=settings.fetch_timeout_seconds,
        )
        resp.raise_for_status()
        return parse(resp.json())
