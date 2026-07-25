"""Adapter parse logic, tested against a saved real fixture — no network (05 §4).

The fixture is 6 real e-GP tenders captured live from egp.gov.et's public API
(no login, no cookies — see app/modules/ingestion/adapters/egp.py's module
docstring for how that was verified). This is how the adapter's parsing is
pinned: change it, these assertions catch a regression without hitting the
network or costing anything.
"""

import json
from pathlib import Path

from app.modules.ingestion.adapters.egp import _text, parse

FIXTURE = Path(__file__).parent / "fixtures" / "egp_ethiopia.json"


def test_text_handles_localized_dict() -> None:
    """Real e-GP quirk found live (not in the 100-row discovery sample):
    `procuring_entity` sometimes comes back as {"am":..., "en":...} instead of
    a plain string. A real live ingest run crashed on this before the fix."""
    assert _text({"am": "የአዲስ አበባ", "en": "Addis Ababa City"}) == "Addis Ababa City"


def test_text_falls_back_to_amharic_when_english_absent() -> None:
    assert _text({"am": "የአዲስ አበባ"}) == "የአዲስ አበባ"


def test_text_passes_through_plain_strings() -> None:
    assert _text("Ministry of Health") == "Ministry of Health"


def test_text_none_for_empty_or_missing() -> None:
    assert _text(None) is None
    assert _text("") is None
    assert _text({}) is None


def _payload() -> dict:
    return json.loads(FIXTURE.read_text())


def _count_lots(payload: dict) -> int:
    return sum(len(pkg["result"]) for pkg in payload["items"])


def test_parse_returns_one_rawtender_per_lot() -> None:
    payload = _payload()
    tenders = parse(payload)
    assert len(tenders) == _count_lots(payload)


def test_parse_maps_identity_title_and_buyer() -> None:
    t = parse(_payload())[0]
    assert t.source_tender_id  # the idempotency key, never empty
    assert t.title
    assert t.buyer  # procuring_entity
    assert t.raw  # original lot record kept verbatim for re-extraction


def test_parse_all_closing_dates_are_tz_aware() -> None:
    """NFR-INTL-1. (Unlike World Bank's award notices, every "Active Tender"
    row observed at discovery carries a deadline somewhere — either field;
    this endpoint appears to only ever list open solicitations. The defensive
    None-handling below is still real code, just exercised synthetically.)"""
    tenders = parse(_payload())
    assert tenders  # sanity: the fixture actually has rows
    for t in tenders:
        if t.closing_at is not None:
            assert t.closing_at.tzinfo is not None


def test_parse_tolerates_missing_deadline_synthetic() -> None:
    """No real e-GP row in the discovery sample lacked a deadline entirely —
    this endpoint is "Active Tenders", not World Bank's mixed award/open feed.
    Still must not crash if one ever does (FR-4.4): missing becomes None."""
    payload = {
        "items": [
            {
                "result": [
                    {
                        "lotReferenceNo": "NO-DEADLINE-1",
                        "lotName": "Synthetic — no deadline anywhere",
                        "packageInformation": {"procuring_entity": "Test Buyer"},
                    }
                ]
            }
        ]
    }
    t = parse(payload)[0]
    assert t.closing_at is None


def test_parse_falls_back_to_lot_id_when_reference_is_empty() -> None:
    """Real e-GP quirk found at discovery: a lot can carry an empty-string
    `lotReferenceNo` (not missing — genuinely `""`, which is falsy) while
    still having a real `id`. Must not be treated as a missing reference."""
    import uuid

    tenders = parse(_payload())
    fell_back_to_uuid_id = []
    for t in tenders:
        try:
            uuid.UUID(t.source_tender_id)
            fell_back_to_uuid_id.append(t.source_tender_id)
        except ValueError:
            pass
    assert fell_back_to_uuid_id  # at least one row fell back to its UUID `id`


def test_parse_skips_lots_without_a_reference() -> None:
    payload = {"items": [{"result": [{"packageInformation": {}}]}]}
    assert parse(payload) == []


def test_parse_never_returns_a_float_bond() -> None:
    """NFR-INTL-2: integer minor units, never float, even if a real bid_currency
    eventually shows up (all observed at discovery were null/zero)."""
    payload = {
        "items": [
            {
                "result": [
                    {
                        "lotReferenceNo": "TEST-1",
                        "lotName": "Test lot",
                        "packageInformation": {
                            "procuring_entity": "Test Buyer",
                            "bid_security_amount": 50000.0,
                            "bid_currency": "ETB",
                        },
                    }
                ]
            }
        ]
    }
    t = parse(payload)[0]
    assert isinstance(t.bid_bond_minor, int)
    assert t.bid_bond_minor == 5_000_000
    assert t.bid_bond_currency == "ETB"


def test_parse_handles_multiple_lots_in_one_package() -> None:
    """The schema supports >1 lot per package even though none in the live
    discovery sample did — each lot is separately biddable and must become
    its own RawTender."""
    payload = {
        "items": [
            {
                "result": [
                    {
                        "lotReferenceNo": "MULTI-1",
                        "lotName": "Lot 1",
                        "packageInformation": {"procuring_entity": "Buyer"},
                    },
                    {
                        "lotReferenceNo": "MULTI-2",
                        "lotName": "Lot 2",
                        "packageInformation": {"procuring_entity": "Buyer"},
                    },
                ]
            }
        ]
    }
    tenders = parse(payload)
    assert {t.source_tender_id for t in tenders} == {"MULTI-1", "MULTI-2"}
