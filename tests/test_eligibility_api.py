"""GET /api/v1/tenders/{id}/eligibility (M16, FR-16.2; docs/11_API_REFERENCE.md
ELI-1) -- the first HTTP surface for assess_eligibility(), which existed but
was reachable only from the CLI/tests before this.

Mirrors tests/test_eligibility_service.py's stub-kernel pattern (no real
network) and tests/test_profiles_api.py's embed_texts monkeypatch (the `ai`
extra isn't installed in CI)."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.eligibility.models import EligibilityAssessment, LawChunk
from app.modules.eligibility.schemas import Citation, EligibilityOut
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import EligibilityVerdict
from app.modules.sources.models import Source, SourceType, ToSStatus
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

_VECTOR = [0.1] * 1024


class _StubKernel:
    """Counts calls so the cache test can prove the SECOND request never
    reaches this at all, not just that it returns the same answer."""

    def __init__(self, outcome: EligibilityOut) -> None:
        self._outcome = outcome
        self.call_count = 0

    async def complete(self, **_: object) -> EligibilityOut:
        self.call_count += 1
        return self._outcome


async def _register(client: AsyncClient, email: str, org_type: str = "diaspora") -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "org_name": f"Org {email}",
            "org_type": org_type,
            "country": "US" if org_type != "local" else "ET",
            "timezone": "America/Los_Angeles",
        },
    )
    assert r.status_code == 201, r.text


async def _seed_tender() -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (tender_id, source_id) for cleanup."""
    async with async_session_factory() as session:
        source = Source(
            key=f"test-{uuid.uuid4()}",
            name="test source",
            type=SourceType.API,
            base_url="https://example.test",
            tos_status=ToSStatus.ALLOWED,
            enabled=False,
        )
        session.add(source)
        group = TenderGroup()
        session.add(group)
        await session.flush()

        tender = Tender(
            source_id=source.id,
            source_tender_id=f"T-{uuid.uuid4()}",
            url="https://example.test/t",
            title="Eligibility test tender",
            region="Ethiopia",
            bidding_track=BiddingTrack.NCB,
            group_id=group.id,
        )
        session.add(tender)
        await session.commit()
        return tender.id, source.id


async def _cleanup(email: str, source_ids: list[uuid.UUID]) -> None:
    async with async_session_factory() as session:
        if source_ids:
            await session.execute(
                delete(EligibilityAssessment).where(
                    EligibilityAssessment.tender_id.in_(
                        select(Tender.id).where(Tender.source_id.in_(source_ids))
                    )
                )
            )
            await session.execute(delete(Tender).where(Tender.source_id.in_(source_ids)))
            await session.execute(delete(Source).where(Source.id.in_(source_ids)))
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            await session.commit()
            return
        memberships = (
            (await session.execute(select(OrgMember).where(OrgMember.user_id == user.id)))
            .scalars()
            .all()
        )
        for m in memberships:
            await session.execute(
                delete(EligibilityAssessment).where(EligibilityAssessment.org_id == m.org_id)
            )
            await session.execute(delete(Org).where(Org.id == m.org_id))
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.execute(delete(OrgMember).where(OrgMember.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_404_for_missing_tender() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            r = await client.get(f"/api/v1/tenders/{uuid.uuid4()}/eligibility")
            assert r.status_code == 404, r.text
    finally:
        await _cleanup(email, [])


@pytest.mark.integration
async def test_403_audience_restricted_for_local_org() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    source_ids: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email, org_type="local")
            tender_id, source_id = await _seed_tender()
            source_ids.append(source_id)

            r = await client.get(f"/api/v1/tenders/{tender_id}/eligibility")
            assert r.status_code == 403, r.text
            assert r.json()["type"].endswith("/audience_restricted")
    finally:
        await _cleanup(email, source_ids)


@pytest.mark.integration
async def test_computes_then_caches_without_recomputing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.kernel.embeddings.embed_texts", lambda texts: [_VECTOR for _ in texts])

    chunk = LawChunk(
        document_name="Test Proclamation",
        document_url="https://example.com",
        article_ref="Article 2(1)",
        text_en='"Procurement" means obtaining goods by purchase.',
    )

    async def fake_retrieve(session: object, embedding: object, limit: int = 5) -> list:  # type: ignore[no-untyped-def]
        return [(chunk, 0.9)]

    monkeypatch.setattr("app.modules.eligibility.service.retrieve_relevant_chunks", fake_retrieve)

    good_result = EligibilityOut(
        verdict=EligibilityVerdict.CONDITIONAL,
        reasons=["Foreign bidders need a local JV for NCB tenders"],
        citations=[Citation(document_name="Test Proclamation", article_ref="Article 2(1)")],
        confidence=0.85,
    )
    stub = _StubKernel(good_result)
    monkeypatch.setattr("app.modules.eligibility.router.build_kernel", lambda: stub)

    email = f"test-{uuid.uuid4()}@example.com"
    source_ids: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            await _register(client, email)
            tender_id, source_id = await _seed_tender()
            source_ids.append(source_id)

            r1 = await client.get(f"/api/v1/tenders/{tender_id}/eligibility")
            assert r1.status_code == 200, r1.text
            body = r1.json()
            assert body["verdict"] == "conditional"
            assert body["conditions"] == ["Foreign bidders need a local JV for NCB tenders"]
            assert body["citations"] == [
                {"document_name": "Test Proclamation", "article_ref": "Article 2(1)"}
            ]
            assert body["law_version"]
            assert body["disclaimer"] is True
            assert stub.call_count == 1

            # Second request: same answer, but the cache must short-circuit
            # before ever calling the kernel again (docs/11_API_REFERENCE.md
            # ELI-1: "computed on miss, cached").
            r2 = await client.get(f"/api/v1/tenders/{tender_id}/eligibility")
            assert r2.status_code == 200, r2.text
            assert r2.json() == body
            assert stub.call_count == 1
    finally:
        await _cleanup(email, source_ids)
