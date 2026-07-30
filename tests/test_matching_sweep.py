"""matching.rerun_sweep (M7) -- the periodic Beat task that catches tenders
ingested AFTER an org's last profile save, which a profile-save-triggered
match_org() call alone can never reach."""

import uuid

import pytest
from app.core.db import async_session_factory
from app.modules.identity.models import Org, OrgMember, OrgRole, OrgType, Session, User
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import Match
from app.modules.matching.tasks import run_matching_sweep
from app.modules.profiles.models import CompanyProfile
from app.modules.qualification.models import Qualification, QualificationMethod, QualificationStatus
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete, select

_VECTOR = [0.1] * 1024


async def _seed_org_with_profile(email: str, sector: str) -> uuid.UUID:
    async with async_session_factory() as session:
        org = Org(name=f"Org {email}", org_type=OrgType.DIASPORA, country="US")
        session.add(org)
        await session.flush()

        user = User(email=email, password_hash="not-a-real-hash")  # noqa: S106 -- test fixture, never authenticated
        session.add(user)
        await session.flush()
        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.OWNER))

        session.add(
            CompanyProfile(
                org_id=org.id,
                source_text="We do IT consulting.",
                sectors=[sector],
                capabilities=["consulting"],
                profile_embedding=_VECTOR,
            )
        )
        await session.commit()
        return org.id


async def _seed_qualified_tender(sector: str) -> tuple[uuid.UUID, uuid.UUID]:
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
            title="Sweep test tender",
            region="Ethiopia",
            bidding_track=BiddingTrack.UNKNOWN,
            group_id=group.id,
            embedding=_VECTOR,
        )
        session.add(tender)
        await session.flush()

        session.add(
            Qualification(
                tender_id=tender.id,
                status=QualificationStatus.QUALIFIED,
                sector=sector,
                method=QualificationMethod.RULE,
            )
        )
        await session.commit()
        return tender.id, source.id


async def _cleanup(org_id: uuid.UUID, email: str, source_id: uuid.UUID | None) -> None:
    async with async_session_factory() as session:
        if source_id is not None:
            await session.execute(delete(Tender).where(Tender.source_id == source_id))
            await session.execute(delete(Source).where(Source.id == source_id))
        await session.execute(delete(Match).where(Match.org_id == org_id))
        await session.execute(delete(CompanyProfile).where(CompanyProfile.org_id == org_id))
        await session.execute(delete(OrgMember).where(OrgMember.org_id == org_id))
        await session.execute(delete(Org).where(Org.id == org_id))
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None:
            await session.execute(delete(Session).where(Session.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
        await session.commit()


@pytest.mark.integration
async def test_sweep_matches_a_tender_ingested_after_profile_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # build_kernel() is imported locally inside run_matching_sweep() (lazy,
    # since it constructs a Redis client) -- patch at the source module so
    # the local `from app.kernel.router import build_kernel` re-resolves it.
    # None -> match_org() skips _explain() entirely, so no real LLM call.
    monkeypatch.setattr("app.kernel.router.build_kernel", lambda: None)

    email = f"sweep-{uuid.uuid4()}@example.com"
    org_id = await _seed_org_with_profile(email, sector="ICT")
    tender_id, source_id = await _seed_qualified_tender(sector="ICT")
    try:
        # Assert on THIS org's own row, not the sweep's global return count:
        # this dev DB carries real leftover profiles from earlier live
        # browser verification in this session (never cleaned up, since
        # those weren't pytest runs), so other real orgs may also pick up
        # matches in the same sweep -- a global count would be flaky.
        await run_matching_sweep()

        async with async_session_factory() as session:
            match = (
                await session.execute(select(Match).where(Match.org_id == org_id))
            ).scalar_one()
            assert match.tender_id == tender_id

        # Idempotent: running it again must not create a SECOND match row
        # for this org's (org, GROUP) -- match_org()'s own existing guarantee.
        await run_matching_sweep()
        async with async_session_factory() as session:
            count = (await session.execute(select(Match).where(Match.org_id == org_id))).scalars()
            assert len(count.all()) == 1
    finally:
        await _cleanup(org_id, email, source_id)


@pytest.mark.integration
async def test_sweep_skips_local_orgs_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    # build_kernel() is imported locally inside run_matching_sweep() (lazy,
    # since it constructs a Redis client) -- patch at the source module so
    # the local `from app.kernel.router import build_kernel` re-resolves it.
    # None -> match_org() skips _explain() entirely, so no real LLM call.
    monkeypatch.setattr("app.kernel.router.build_kernel", lambda: None)

    email = f"sweep-local-{uuid.uuid4()}@example.com"
    async with async_session_factory() as session:
        org = Org(name=f"Local {email}", org_type=OrgType.LOCAL, country="ET")
        session.add(org)
        await session.flush()
        user = User(email=email, password_hash="not-a-real-hash")  # noqa: S106 -- test fixture, never authenticated
        session.add(user)
        await session.flush()
        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.OWNER))
        session.add(
            CompanyProfile(
                org_id=org.id,
                source_text="Local facilitator profile.",
                sectors=["ICT"],
                capabilities=["consulting"],
                profile_embedding=_VECTOR,
            )
        )
        await session.commit()
        org_id = org.id

    try:
        # Must not raise AudienceRestricted out of the sweep -- a local org's
        # profile existing is expected (M14 facilitator profiles), not a bug.
        # (Not asserting the global return count: this dev DB carries real
        # leftover profiles from earlier live browser testing this session.)
        await run_matching_sweep()

        async with async_session_factory() as session:
            local_matches = (
                await session.execute(select(Match).where(Match.org_id == org_id))
            ).scalars()
            assert local_matches.all() == []
    finally:
        await _cleanup(org_id, email, None)
