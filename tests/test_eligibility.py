"""Pure-logic & mock unit tests for M16 Eligibility (SKILLS.md R6, NFR-LEGAL-1)."""

import pytest
from app.modules.eligibility.service import (
    assess_eligibility,
    classify_bidding_track,
)
from app.modules.identity.models import Org, OrgType
from app.modules.ingestion.models import BiddingTrack, Tender
from app.modules.matching.models import EligibilityVerdict


def test_classify_bidding_track_donor() -> None:
    tender = Tender(
        title="World Bank Education Project",
        raw_data={"notice_type": "Contract Award"},
        bidding_track=BiddingTrack.UNKNOWN,
    )
    track, conf, snippet = classify_bidding_track(tender)
    assert track == BiddingTrack.DONOR
    assert conf >= 0.9
    assert "World Bank" in snippet


def test_classify_bidding_track_icb() -> None:
    tender = Tender(
        title="Supply of Medical Equipment (International Competitive Bidding)",
        raw_data={},
        bidding_track=BiddingTrack.UNKNOWN,
    )
    track, conf, _ = classify_bidding_track(tender)
    assert track == BiddingTrack.ICB
    assert conf == 0.90


def test_classify_bidding_track_ncb() -> None:
    tender = Tender(
        title="Construction of Local Health Post (NCB)",
        raw_data={},
        bidding_track=BiddingTrack.UNKNOWN,
    )
    track, conf, _ = classify_bidding_track(tender)
    assert track == BiddingTrack.NCB
    assert conf == 0.90


def test_classify_bidding_track_unknown() -> None:
    tender = Tender(
        title="General Services",
        raw_data={},
        bidding_track=BiddingTrack.UNKNOWN,
    )
    track, conf, _ = classify_bidding_track(tender)
    assert track == BiddingTrack.UNKNOWN
    assert conf == 0.0


@pytest.mark.asyncio
async def test_assess_eligibility_unknown_when_no_kernel() -> None:
    org = Org(org_type=OrgType.LOCAL, country="ET", name="Test Org")
    tender = Tender(title="Test Tender", bidding_track=BiddingTrack.NCB)

    res = await assess_eligibility(session=None, org=org, tender=tender, kernel=None)
    assert res.verdict == EligibilityVerdict.UNKNOWN
    assert res.confidence == 0.0
    assert "no kernel available" in res.reasons[0]
