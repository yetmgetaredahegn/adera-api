"""Public tenders API (FR-9.1 public portion) — the contract client repos build on.

These tests pin the response SHAPE as much as the behavior: adera-mobile/-web
generate their clients from this contract (ADR-025), so an accidental field change
here is a cross-repo breaking change and must fail loudly.
"""

import uuid

import httpx
import pytest
from app.core.db import async_session_factory
from app.main import create_app
from app.modules.ingestion.models import Tender
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete

# Exactly the public contract — additions here must be deliberate (see schemas.py).
EXPECTED_TENDER_FIELDS = {
    "id",
    "title",
    "buyer",
    "summary",
    "region",
    "language",
    "url",
    "published_at",
    "closing_at",
    "opening_at",
    "bid_bond_minor",
    "bid_bond_currency",
    "doc_price_minor",
    "doc_price_currency",
    "bidding_track",
}


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


@pytest.mark.integration
async def test_list_detail_pagination_and_contract_shape() -> None:
    marker = f"api-test-{uuid.uuid4()}"
    async with async_session_factory() as session:
        source = Source(
            key=f"t-{uuid.uuid4()}",
            name="t",
            type=SourceType.API,
            base_url="https://example.test",
            tos_status=ToSStatus.ALLOWED,
            enabled=False,
        )
        session.add(source)
        await session.flush()
        for i in range(3):
            session.add(
                Tender(
                    source_id=source.id,
                    source_tender_id=f"{marker}-{i}",
                    url="https://example.test/t",
                    title=f"{marker} tender {i}",
                    raw_data={},
                )
            )
        await session.commit()
        source_id = source.id

    try:
        async with await _client() as client:
            # list: seeded rows appear, newest-first keyset pages don't overlap
            page1 = (await client.get("/api/v1/tenders", params={"limit": 2})).json()
            assert set(page1["items"][0].keys()) == EXPECTED_TENDER_FIELDS
            assert page1["next_after"] is not None  # full page → cursor present

            page2 = (
                await client.get(
                    "/api/v1/tenders", params={"limit": 2, "after": page1["next_after"]}
                )
            ).json()
            ids1 = {t["id"] for t in page1["items"]}
            ids2 = {t["id"] for t in page2["items"]}
            assert ids1.isdisjoint(ids2)  # keyset pages never overlap

            # detail: found + shape
            some_id = page1["items"][0]["id"]
            detail = await client.get(f"/api/v1/tenders/{some_id}")
            assert detail.status_code == 200
            assert set(detail.json().keys()) == EXPECTED_TENDER_FIELDS

            # 404 is clean JSON, not a crash
            missing = await client.get(f"/api/v1/tenders/{uuid.uuid4()}")
            assert missing.status_code == 404

            # malformed cursor → 422, never a guessed page
            # search: query filter
            search_res = await client.get("/api/v1/tenders/search", params={"q": marker})
            assert search_res.status_code == 200
            assert len(search_res.json()["items"]) >= 3

            # qa: empty/unparsed document refusal
            qa_res = await client.post(
                f"/api/v1/tenders/{some_id}/qa",
                json={"question": "What is the bid security amount?"},
            )
            assert qa_res.status_code == 200
            qa_data = qa_res.json()
            assert qa_data["tender_id"] == some_id
            assert "not available" in qa_data["answer"] or "do not contain" in qa_data["answer"]
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Tender).where(Tender.source_id == source_id))
            await session.execute(delete(Source).where(Source.id == source_id))
            await session.commit()
