"""Eligibility service — the two refusal gates (module docstring in
app/modules/eligibility/service.py), stubbed kernel, no network (R6)."""

import pytest
from app.modules.eligibility.models import LawChunk
from app.modules.eligibility.schemas import Citation, EligibilityOut
from app.modules.eligibility.service import _unknown, assess_eligibility
from app.modules.identity.models import Org, OrgType
from app.modules.identity.service import AudienceRestricted
from app.modules.ingestion.models import BiddingTrack, Tender
from app.modules.matching.models import EligibilityVerdict


def _org() -> Org:
    # diaspora/foreign only (ADR-029) -- a LOCAL org never reaches this path;
    # see test_audience_restricted_for_local_org below for that gate.
    return Org(name="Test Org", org_type=OrgType.DIASPORA, country="US")


def _tender() -> Tender:
    return Tender(title="Test tender", bidding_track=BiddingTrack.NCB)


def _chunk(article_ref: str = "Article 2(1)") -> LawChunk:
    return LawChunk(
        document_name="Test Proclamation",
        document_url="https://example.com",
        article_ref=article_ref,
        text_en='"Procurement" means obtaining goods by purchase.',
    )


class _StubKernel:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome

    async def complete(self, **_: object) -> EligibilityOut:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        assert isinstance(self._outcome, EligibilityOut)
        return self._outcome


def test_unknown_helper_shape() -> None:
    result = _unknown("test reason")
    assert result.verdict == EligibilityVerdict.UNKNOWN
    assert result.reasons == ["test reason"]
    assert result.citations == []
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_audience_restricted_for_local_org() -> None:
    """ADR-029: local orgs are supply-side only -- raises, never a silent
    `unknown` verdict (which would look like a corpus gap, not an audience
    gate)."""
    local_org = Org(name="Local Org", org_type=OrgType.LOCAL, country="ET")
    with pytest.raises(AudienceRestricted):
        await assess_eligibility(session=None, org=local_org, tender=_tender(), kernel=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_no_kernel_returns_unknown() -> None:
    result = await assess_eligibility(session=None, org=_org(), tender=_tender(), kernel=None)  # type: ignore[arg-type]
    assert result.verdict == EligibilityVerdict.UNKNOWN
    assert "no kernel" in result.reasons[0]


@pytest.mark.asyncio
async def test_confident_verdict_without_valid_citation_is_downgraded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The citation floor: an "eligible" verdict citing nothing real must be
    downgraded to unknown, not trusted (eval C6: every claim must cite)."""
    chunk = _chunk()

    async def fake_retrieve(session: object, embedding: object, limit: int = 5) -> list:  # type: ignore[no-untyped-def]
        return [(chunk, 0.9)]

    monkeypatch.setattr("app.modules.eligibility.service.retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(
        "app.kernel.embeddings.embed_texts", lambda texts: [[0.1] * 1024 for _ in texts]
    )

    bad_result = EligibilityOut(
        verdict=EligibilityVerdict.ELIGIBLE,
        reasons=["looks fine"],
        citations=[Citation(document_name="Made Up Doc", article_ref="Article 99")],
        confidence=0.9,
    )
    kernel = _StubKernel(bad_result)
    result = await assess_eligibility(session=object(), org=_org(), tender=_tender(), kernel=kernel)  # type: ignore[arg-type]
    assert result.verdict == EligibilityVerdict.UNKNOWN
    assert "citation" in result.reasons[0]


@pytest.mark.asyncio
async def test_confident_verdict_with_valid_citation_is_trusted(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    chunk = _chunk("Article 2(1)")

    async def fake_retrieve(session: object, embedding: object, limit: int = 5) -> list:  # type: ignore[no-untyped-def]
        return [(chunk, 0.9)]

    monkeypatch.setattr("app.modules.eligibility.service.retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(
        "app.kernel.embeddings.embed_texts", lambda texts: [[0.1] * 1024 for _ in texts]
    )

    good_result = EligibilityOut(
        verdict=EligibilityVerdict.ELIGIBLE,
        reasons=["matches the definition"],
        citations=[Citation(document_name="Test Proclamation", article_ref="Article 2(1)")],
        confidence=0.9,
    )
    kernel = _StubKernel(good_result)
    result = await assess_eligibility(session=object(), org=_org(), tender=_tender(), kernel=kernel)  # type: ignore[arg-type]
    assert result.verdict == EligibilityVerdict.ELIGIBLE


@pytest.mark.asyncio
async def test_provider_failure_returns_unknown(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    chunk = _chunk()

    async def fake_retrieve(session: object, embedding: object, limit: int = 5) -> list:  # type: ignore[no-untyped-def]
        return [(chunk, 0.9)]

    monkeypatch.setattr("app.modules.eligibility.service.retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(
        "app.kernel.embeddings.embed_texts", lambda texts: [[0.1] * 1024 for _ in texts]
    )
    kernel = _StubKernel(RuntimeError("simulated provider failure"))
    result = await assess_eligibility(session=object(), org=_org(), tender=_tender(), kernel=kernel)  # type: ignore[arg-type]
    assert result.verdict == EligibilityVerdict.UNKNOWN
