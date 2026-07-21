"""Adapter parse logic, tested against a saved real fixture — no network (05 §4).

The fixture is 5 real World Bank Ethiopia notices captured from the live API. This
is how a source's parsing is pinned: change the adapter, these assertions catch a
regression without hitting the internet or costing anything.
"""

import json
from pathlib import Path

from app.modules.ingestion.adapters.worldbank import parse

FIXTURE = Path(__file__).parent / "fixtures" / "worldbank_ethiopia.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_returns_one_rawtender_per_notice() -> None:
    payload = _payload()
    tenders = parse(payload)
    assert len(tenders) == len(payload["procnotices"])


def test_parse_maps_the_identity_and_title() -> None:
    t = parse(_payload())[0]
    assert t.source_tender_id  # the idempotency key, never empty
    assert t.title
    assert t.region == "Ethiopia"
    assert t.raw  # original record kept verbatim for re-extraction


def test_parse_tolerates_missing_deadline() -> None:
    """Contract Awards have no submission deadline. Missing must become None, not a
    crash and not a wrong date (FR-4.4)."""
    tenders = parse(_payload())
    # at least one fixture row is a Contract Award with no deadline
    assert any(t.closing_at is None for t in tenders)
    # and any deadline that IS set is timezone-aware (NFR-INTL-1)
    for t in tenders:
        if t.closing_at is not None:
            assert t.closing_at.tzinfo is not None


def test_parse_skips_rows_without_an_id() -> None:
    payload = {"procnotices": [{"bid_description": "no id here"}]}
    assert parse(payload) == []
