"""Pins the two-stage qualification design (FR-5.1/5.2): rule stage rejects for
free, LLM stage judges the rest, and a failed LLM call degrades to
NEEDS_REVIEW rather than a guess (AGENTS.md rule 11). Pure logic — no DB, no
network (SKILLS.md R6)."""

from datetime import UTC, datetime, timedelta

import pytest
from app.modules.ingestion.models import Tender
from app.modules.qualification.models import (
    QualificationMethod,
    QualificationStatus,
    Urgency,
)
from app.modules.qualification.schemas import QualifyOut
from app.modules.qualification.service import (
    _llm_qualify,
    _rule_reject,
    _urgency_from_closing_at,
)


def _tender(**overrides: object) -> Tender:
    defaults: dict[str, object] = {
        "title": "Construction of a latrine block",
        "buyer": "Ministry of Education",
        "summary": None,
        "region": "Amhara",
        "closing_at": None,
        "raw_data": {},
    }
    defaults.update(overrides)
    return Tender(**defaults)  # type: ignore[arg-type]


class _StubKernel:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome

    async def complete(self, **_: object) -> QualifyOut:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        assert isinstance(self._outcome, QualifyOut)
        return self._outcome


def test_rule_rejects_contract_award_notices() -> None:
    tender = _tender(raw_data={"notice_type": "Contract Award"})
    assert _rule_reject(tender) is True


def test_rule_does_not_reject_invitation_for_bids() -> None:
    tender = _tender(raw_data={"notice_type": "Invitation for Bids"})
    assert _rule_reject(tender) is False


def test_rule_does_not_reject_when_notice_type_absent() -> None:
    # A future source might not carry notice_type at all — must not be treated
    # as a match for a rejection rule it never opted into.
    assert _rule_reject(_tender(raw_data={})) is False


def test_urgency_unknown_when_no_closing_at() -> None:
    assert _urgency_from_closing_at(None) == Urgency.UNKNOWN


def test_urgency_urgent_within_seven_days() -> None:
    soon = datetime.now(UTC) + timedelta(days=3)
    assert _urgency_from_closing_at(soon) == Urgency.URGENT


def test_urgency_normal_beyond_fourteen_days() -> None:
    later = datetime.now(UTC) + timedelta(days=30)
    assert _urgency_from_closing_at(later) == Urgency.NORMAL


@pytest.mark.asyncio
async def test_llm_qualify_returns_parsed_result_on_success() -> None:
    kernel = _StubKernel(
        QualifyOut(
            status=QualificationStatus.QUALIFIED,
            urgency=Urgency.NORMAL,
            sector="construction",
            reasons=["Clear scope, open deadline."],
            confidence=0.8,
        )
    )
    result = await _llm_qualify(kernel, _tender())  # type: ignore[arg-type]
    assert result is not None
    assert result.status == QualificationStatus.QUALIFIED
    assert result.sector == "construction"


@pytest.mark.asyncio
async def test_llm_qualify_returns_none_on_provider_failure() -> None:
    kernel = _StubKernel(RuntimeError("simulated provider failure"))
    result = await _llm_qualify(kernel, _tender())  # type: ignore[arg-type]
    assert result is None


def test_qualification_method_enum_has_rule_and_llm() -> None:
    # Guards the audit-transparency field this module is built around.
    assert {m.value for m in QualificationMethod} == {"rule", "llm"}
