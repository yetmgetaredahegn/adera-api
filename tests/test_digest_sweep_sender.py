"""notifications.send_digest_sweep -- proves the sweep actually calls the
real sender (batched per user) now, not just records idempotency and does
nothing, which was the entire behavior before app/modules/notifications/
senders.py existed.

get_user_digest_items is patched to return real items ONLY for this test's
own seeded user and `[]` for every other real user in this dev DB (which
carries genuine leftover accounts from earlier live browser testing this
session) -- letting should_send_digest_now fire for everyone while faking
data for only one user would otherwise create real notifications_log rows
for other people's real accounts as a side effect of running this test.
"""

import uuid

import pytest
from app.core.db import async_session_factory
from app.modules.identity.models import Org, OrgMember, OrgRole, OrgType, Session, User
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import Match, MatchState
from app.modules.notifications.models import NotificationLog
from app.modules.notifications.schemas import DigestItemOut
from app.modules.notifications.tasks import run_digest_sweep
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete, select


async def _seed_org_user_with_match(
    email: str,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (org_id, user_id, source_id, group_id, tender_id) for cleanup/assertions."""
    async with async_session_factory() as session:
        org = Org(name=f"Digest Org {email}", org_type=OrgType.DIASPORA, country="US")
        session.add(org)
        user = User(email=email, password_hash="not-a-real-hash")  # noqa: S106
        session.add(user)
        await session.flush()
        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.OWNER))

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
            title="Digest sweep test tender",
            region="Ethiopia",
            bidding_track=BiddingTrack.UNKNOWN,
            group_id=group.id,
        )
        session.add(tender)
        await session.flush()

        session.add(Match(tender_id=tender.id, org_id=org.id, score=0.9, state=MatchState.NEW))
        await session.commit()
        return org.id, user.id, source.id, group.id, tender.id


async def _cleanup(org_id: uuid.UUID, user_id: uuid.UUID, email: str, source_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(Tender).where(Tender.source_id == source_id))
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.execute(delete(Match).where(Match.org_id == org_id))
        await session.execute(delete(NotificationLog).where(NotificationLog.user_id == user_id))
        await session.execute(delete(OrgMember).where(OrgMember.org_id == org_id))
        await session.execute(delete(Org).where(Org.id == org_id))
        await session.execute(delete(Session).where(Session.user_id == user_id))
        await session.execute(delete(User).where(User.email == email))
        await session.commit()


def _scoped_digest_items(target_user_id: uuid.UUID, tender_id: uuid.UUID, group_id: uuid.UUID):  # type: ignore[no-untyped-def]
    """Real items for target_user_id only; `[]` for every other real user in
    this dev DB, so should_send_digest_now firing for everyone can't create
    real notification records for anyone but this test's own seeded user."""

    async def fake(session: object, user_id: uuid.UUID, limit: int = 10) -> list[DigestItemOut]:
        if user_id != target_user_id:
            return []
        return [
            DigestItemOut(
                tender_id=tender_id,
                group_id=group_id,
                title="Digest sweep test tender",
                buyer="Ministry of Testing",
                region="Ethiopia",
                closing_at=None,
                score=0.9,
                explanation=None,
            )
        ]

    return fake


@pytest.mark.integration
async def test_sweep_sends_one_batched_email_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.modules.notifications.tasks.should_send_digest_now", lambda *a, **k: True
    )

    email = f"digest-{uuid.uuid4()}@example.com"
    org_id, user_id, source_id, group_id, tender_id = await _seed_org_user_with_match(email)
    monkeypatch.setattr(
        "app.modules.notifications.tasks.get_user_digest_items",
        _scoped_digest_items(user_id, tender_id, group_id),
    )

    sent_calls: list[tuple[str, list[DigestItemOut]]] = []

    async def fake_send(to_email: str, items: list[DigestItemOut]) -> bool:
        sent_calls.append((to_email, items))
        return True

    monkeypatch.setattr("app.modules.notifications.tasks.send_digest_email", fake_send)

    try:
        await run_digest_sweep()

        assert len(sent_calls) == 1
        assert sent_calls[0][0] == email
        assert len(sent_calls[0][1]) == 1
        assert sent_calls[0][1][0].title == "Digest sweep test tender"

        # Idempotent: a second sweep must not re-send for the same
        # (user, group) -- record_notification's existing guarantee.
        sent_calls.clear()
        await run_digest_sweep()
        assert sent_calls == []

        async with async_session_factory() as session:
            logs = (
                (
                    await session.execute(
                        select(NotificationLog).where(NotificationLog.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(logs) == 1
    finally:
        await _cleanup(org_id, user_id, email, source_id)


@pytest.mark.integration
async def test_sweep_survives_a_send_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.modules.notifications.tasks.should_send_digest_now", lambda *a, **k: True
    )

    email = f"digest-fail-{uuid.uuid4()}@example.com"
    org_id, user_id, source_id, group_id, tender_id = await _seed_org_user_with_match(email)
    monkeypatch.setattr(
        "app.modules.notifications.tasks.get_user_digest_items",
        _scoped_digest_items(user_id, tender_id, group_id),
    )

    async def failing_send(to_email: str, items: list[DigestItemOut]) -> bool:
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr("app.modules.notifications.tasks.send_digest_email", failing_send)

    try:
        # Must not raise out of the sweep -- one user's send failure can't
        # take down every other user's digest in the same run.
        count = await run_digest_sweep()
        assert count >= 1
    finally:
        await _cleanup(org_id, user_id, email, source_id)
