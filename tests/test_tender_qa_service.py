"""answer_tender_qa (M9, FR-9.3, prompt B4) -- replaced a non-LLM keyword-match
stub that returned a canned "excerpt matches query" string regardless of the
actual question. Pure logic, stub kernel, no network (R6), mirrors
test_eligibility_service.py's pattern."""

import uuid

import pytest
from app.modules.documents.models import TenderDocument
from app.modules.ingestion.schemas import TenderQAAnswer
from app.modules.ingestion.service import answer_tender_qa


def _doc(
    filename: str = "notice.pdf", text: str | None = "The bid bond is 50000 ETB."
) -> TenderDocument:
    return TenderDocument(tender_id=uuid.uuid4(), filename=filename, text=text)


class _StubKernel:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome

    async def complete(self, **_: object) -> TenderQAAnswer:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        assert isinstance(self._outcome, TenderQAAnswer)
        return self._outcome


class _FakeSession:
    """Duck-types the one call answer_tender_qa makes: session.execute(...)
    .scalars().all() -> the seeded documents."""

    def __init__(self, docs: list[TenderDocument]) -> None:
        self._docs = docs

    async def execute(self, *_: object, **__: object) -> "_FakeResult":
        return _FakeResult(self._docs)


class _FakeResult:
    def __init__(self, docs: list[TenderDocument]) -> None:
        self._docs = docs

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[TenderDocument]:
        return self._docs


@pytest.mark.asyncio
async def test_no_parsed_documents_refuses_without_calling_kernel() -> None:
    session = _FakeSession([_doc(text=None)])
    kernel = _StubKernel(RuntimeError("must not be called"))
    answer, citations, confidence = await answer_tender_qa(
        session,
        uuid.uuid4(),
        "What is the bid bond?",
        kernel=kernel,  # type: ignore[arg-type]
    )
    assert "not available or have not been parsed" in answer
    assert citations == []
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_no_kernel_refuses() -> None:
    session = _FakeSession([_doc()])
    answer, citations, confidence = await answer_tender_qa(
        session,
        uuid.uuid4(),
        "What is the bid bond?",
        kernel=None,  # type: ignore[arg-type]
    )
    assert "not available right now" in answer
    assert citations == []
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_grounded_answer_with_valid_citation_is_trusted() -> None:
    doc = _doc(filename="notice.pdf")
    session = _FakeSession([doc])
    good = TenderQAAnswer(
        answer="The bid bond is 50,000 ETB.",
        answerable=True,
        citations=["notice.pdf"],
        confidence=0.9,
    )
    kernel = _StubKernel(good)
    answer, citations, confidence = await answer_tender_qa(
        session,
        uuid.uuid4(),
        "What is the bid bond?",
        kernel=kernel,  # type: ignore[arg-type]
    )
    assert answer == "The bid bond is 50,000 ETB."
    assert citations == ["notice.pdf"]
    assert confidence == 0.9


@pytest.mark.asyncio
async def test_model_says_unanswerable_is_returned_with_no_citations() -> None:
    session = _FakeSession([_doc()])
    unanswerable = TenderQAAnswer(
        answer="The documents don't state a submission method.", answerable=False
    )
    kernel = _StubKernel(unanswerable)
    answer, citations, confidence = await answer_tender_qa(
        session,
        uuid.uuid4(),
        "How do I submit?",
        kernel=kernel,  # type: ignore[arg-type]
    )
    assert answer == "The documents don't state a submission method."
    assert citations == []
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_citation_to_a_document_never_given_is_downgraded() -> None:
    """The citation floor: a filename the model invented (never actually
    passed to it) must not be trusted, mirroring eligibility's citation
    floor for the same reason (AGENTS.md rule 11)."""
    session = _FakeSession([_doc(filename="real.pdf")])
    bad = TenderQAAnswer(
        answer="Looks fine.", answerable=True, citations=["made_up.pdf"], confidence=0.9
    )
    kernel = _StubKernel(bad)
    answer, citations, confidence = await answer_tender_qa(
        session,
        uuid.uuid4(),
        "What is the deadline?",
        kernel=kernel,  # type: ignore[arg-type]
    )
    assert "do not clearly answer" in answer
    assert citations == []
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_provider_failure_refuses_gracefully() -> None:
    session = _FakeSession([_doc()])
    kernel = _StubKernel(RuntimeError("simulated provider failure"))
    answer, citations, confidence = await answer_tender_qa(
        session,
        uuid.uuid4(),
        "What is the bid bond?",
        kernel=kernel,  # type: ignore[arg-type]
    )
    assert "failed" in answer
    assert citations == []
    assert confidence == 0.0
