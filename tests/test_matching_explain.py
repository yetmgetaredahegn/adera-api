"""Pins the behavior AGENTS.md rule 11 requires: a failed/malformed explanation
must return None, never a faked string. Pure logic — no DB, no network (R6)."""

from datetime import UTC, datetime

import pytest
from app.modules.ingestion.models import Tender
from app.modules.matching.schemas import ExplanationOut
from app.modules.matching.service import _explain, _profile_text, _tender_text
from app.modules.profiles.models import CompanyProfile
from pydantic import ValidationError


def _profile(**overrides: object) -> CompanyProfile:
    defaults: dict[str, object] = {
        "sectors": ["construction"],
        "capabilities": ["latrine construction"],
        "certifications": [],
        "regions": ["Amhara"],
    }
    defaults.update(overrides)
    return CompanyProfile(source_text="n/a", **defaults)  # type: ignore[arg-type]


def _tender(**overrides: object) -> Tender:
    defaults: dict[str, object] = {
        "title": "Construction of a latrine block",
        "buyer": "Ministry of Education",
        "region": "Amhara",
        "closing_at": None,
        "bid_bond_minor": None,
        "bid_bond_currency": None,
    }
    defaults.update(overrides)
    return Tender(**defaults)  # type: ignore[arg-type]


class _StubKernel:
    """Duck-types app.kernel.router.Kernel's one method _explain calls."""

    def __init__(self, outcome: object) -> None:
        self._outcome = outcome

    async def complete(self, **_: object) -> ExplanationOut:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        assert isinstance(self._outcome, ExplanationOut)
        return self._outcome


def test_profile_text_only_lists_confirmed_facts() -> None:
    text = _profile_text(_profile(certifications=[]))
    assert "latrine construction" in text
    assert "Certifications: none confirmed" in text


def test_tender_text_states_unknown_when_bond_and_deadline_absent() -> None:
    text = _tender_text(_tender())
    assert "Closing: unknown/no deadline stated" in text
    assert "Bid bond: none stated" in text


def test_tender_text_formats_money_as_decimal_from_minor_units() -> None:
    text = _tender_text(_tender(bid_bond_minor=5_000_000, bid_bond_currency="ETB"))
    assert "Bid bond: 50000.00 ETB" in text


@pytest.mark.asyncio
async def test_explain_returns_explanation_on_success() -> None:
    kernel = _StubKernel(
        ExplanationOut(explanation="You do latrines; they need one.", confidence=0.9)
    )
    result = await _explain(kernel, _profile(), _tender())  # type: ignore[arg-type]
    assert result == "You do latrines; they need one."


@pytest.mark.asyncio
async def test_explain_returns_none_on_validation_error() -> None:
    kernel = _StubKernel(ValidationError.from_exception_data("ExplanationOut", []))
    result = await _explain(kernel, _profile(), _tender())  # type: ignore[arg-type]
    assert result is None


@pytest.mark.asyncio
async def test_explain_returns_none_on_provider_failure() -> None:
    """Rate limit / network / budget-breaker errors from litellm — not
    ValidationError, but must still degrade to None, never crash matching."""
    kernel = _StubKernel(RuntimeError("simulated provider failure"))
    result = await _explain(kernel, _profile(), _tender())  # type: ignore[arg-type]
    assert result is None


def test_closing_at_is_utc_aware_when_present() -> None:
    # Guards the format string, not the tz logic itself (that's the model's job).
    text = _tender_text(_tender(closing_at=datetime(2026, 8, 1, tzinfo=UTC)))
    assert "2026-08-01" in text
