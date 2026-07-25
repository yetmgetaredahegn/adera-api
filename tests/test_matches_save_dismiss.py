"""MAT-2 / MAT-3 — save and dismiss (FR-7.3).

Two promises are under test, and both are product-level rather than technical:
a save must outlive the device that made it, and a dismissed match must never
come back. The third is the usual one (rule 9): neither write may reach across
orgs.
"""

import uuid

import pytest
from app.core.db import async_session_factory
from app.main import app
from app.modules.identity.models import Org, OrgMember, Session, User
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import Match, MatchState
from app.modules.sources.models import Source, SourceType, ToSStatus
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


async def _register(client: AsyncClient, email: str, org_type: str = "diaspora") -> uuid.UUID:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "org_name": f"Org {email}",
            "org_type": org_type,
            "country": "ET" if org_type == "local" else "US",
            "timezone": "Africa/Addis_Ababa" if org_type == "local" else "America/Los_Angeles",
        },
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["org"]["id"])


def _csrf(client: AsyncClient) -> dict[str, str]:
    """The double-submit echo. A test that skipped this would pass against an
    endpoint that forgot `require_csrf` -- which is the bug worth catching."""
    return {"X-CSRF-Token": client.cookies["adera_csrf"]}


async def _seed_match(org_id: uuid.UUID, title: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (source_id, match_id) — the source id so cleanup can remove the
    Source/TenderGroup/Tender chain it created."""
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
            title=title,
            region="Ethiopia",
            bidding_track=BiddingTrack.UNKNOWN,
            group_id=group.id,
        )
        session.add(tender)
        await session.flush()

        match = Match(tender_id=tender.id, org_id=org_id, score=0.9, state=MatchState.NEW)
        session.add(match)
        await session.flush()
        match_id = match.id
        await session.commit()
        return source.id, match_id


async def _state_of(match_id: uuid.UUID) -> MatchState:
    async with async_session_factory() as session:
        match = await session.get(Match, match_id)
        assert match is not None
        return match.state


async def _cleanup(email: str, source_ids: list[uuid.UUID]) -> None:
    async with async_session_factory() as session:
        if source_ids:
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
        for membership in memberships:
            await session.execute(delete(Match).where(Match.org_id == membership.org_id))
            await session.execute(delete(Org).where(Org.id == membership.org_id))
        await session.execute(delete(Session).where(Session.user_id == user.id))
        await session.execute(delete(OrgMember).where(OrgMember.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_save_persists_and_is_listable_by_state() -> None:
    email = f"test-save-{uuid.uuid4()}@example.com"
    sources: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            org_id = await _register(client, email)
            source_id, match_id = await _seed_match(org_id, "Saveable tender")
            sources.append(source_id)

            saved = await client.post(f"/api/v1/matches/{match_id}/save", headers=_csrf(client))
            assert saved.status_code == 200, saved.text
            # docs/11 MAT-2: the response carries the new state, so a client can
            # redraw the card from the write's own reply.
            assert saved.json()["state"] == "saved"
            assert await _state_of(match_id) == MatchState.SAVED

            listed = await client.get("/api/v1/matches?state=saved")
            assert listed.status_code == 200, listed.text
            assert [m["id"] for m in listed.json()] == [str(match_id)]
            # The chip's field must be present and honest, not omitted (FR-16.2).
            assert listed.json()[0]["eligibility"] == "unknown"

            # ...and it is no longer "new", so the two filters don't double-count.
            assert (await client.get("/api/v1/matches?state=new")).json() == []
    finally:
        await _cleanup(email, sources)


@pytest.mark.integration
async def test_dismissed_match_never_resurfaces() -> None:
    """FR-7.3 as an assertion: not merely 'the write succeeded' but 'no listing
    this endpoint offers can show it again'."""
    email = f"test-dismiss-{uuid.uuid4()}@example.com"
    sources: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            org_id = await _register(client, email)
            source_id, match_id = await _seed_match(org_id, "Dismissable tender")
            sources.append(source_id)

            gone = await client.post(f"/api/v1/matches/{match_id}/dismiss", headers=_csrf(client))
            assert gone.status_code == 200, gone.text
            assert gone.json()["state"] == "dismissed"
            # The row survives -- that is what lets ranking remember the judgment.
            assert await _state_of(match_id) == MatchState.DISMISSED

            for url in (
                "/api/v1/matches",
                "/api/v1/matches?state=new",
                "/api/v1/matches?state=saved",
            ):
                assert (await client.get(url)).json() == [], url

            # And the filter cannot be talked into asking for them.
            assert (await client.get("/api/v1/matches?state=dismissed")).status_code == 422
    finally:
        await _cleanup(email, sources)


@pytest.mark.integration
async def test_write_without_csrf_token_is_refused() -> None:
    email = f"test-csrf-{uuid.uuid4()}@example.com"
    sources: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            org_id = await _register(client, email)
            source_id, match_id = await _seed_match(org_id, "CSRF tender")
            sources.append(source_id)

            refused = await client.post(f"/api/v1/matches/{match_id}/dismiss")
            assert refused.status_code == 403, refused.text
            assert refused.json()["type"].endswith("/csrf_failed")
            assert await _state_of(match_id) == MatchState.NEW
    finally:
        await _cleanup(email, sources)


@pytest.mark.integration
async def test_org_a_cannot_dismiss_org_b_match() -> None:
    """Rule 9's leak test for the write path: a cross-org id must 404 exactly
    like a nonexistent one, and B's match must be untouched afterwards."""
    email_a = f"test-wa-{uuid.uuid4()}@example.com"
    email_b = f"test-wb-{uuid.uuid4()}@example.com"
    sources_a: list[uuid.UUID] = []
    sources_b: list[uuid.UUID] = []
    try:
        async with (
            AsyncClient(
                transport=ASGITransport(app=app), base_url="https://example.com"
            ) as client_a,
            AsyncClient(
                transport=ASGITransport(app=app), base_url="https://example.com"
            ) as client_b,
        ):
            org_a = await _register(client_a, email_a)
            org_b = await _register(client_b, email_b)

            source_a, _ = await _seed_match(org_a, "A's tender")
            source_b, match_b = await _seed_match(org_b, "B's tender")
            sources_a.append(source_a)
            sources_b.append(source_b)

            attempt = await client_a.post(
                f"/api/v1/matches/{match_b}/dismiss", headers=_csrf(client_a)
            )
            assert attempt.status_code == 404, attempt.text
            assert await _state_of(match_b) == MatchState.NEW
    finally:
        await _cleanup(email_a, sources_a)
        await _cleanup(email_b, sources_b)


@pytest.mark.integration
async def test_local_org_cannot_save() -> None:
    """ADR-029 on the write path too — otherwise a local org could build a
    saved list for a feature it is never served."""
    email = f"test-local-save-{uuid.uuid4()}@example.com"
    sources: list[uuid.UUID] = []
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://example.com"
        ) as client:
            org_id = await _register(client, email, org_type="local")
            source_id, match_id = await _seed_match(org_id, "Local org tender")
            sources.append(source_id)

            refused = await client.post(f"/api/v1/matches/{match_id}/save", headers=_csrf(client))
            assert refused.status_code == 403, refused.text
            assert refused.json()["type"].endswith("/audience_restricted")
    finally:
        await _cleanup(email, sources)
