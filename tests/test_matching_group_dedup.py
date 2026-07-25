"""ADR-028: match_org() must produce ONE Match per opportunity GROUP, not one
per tender row -- two sibling tenders (same group, different sources) both
ranking above the similarity floor must never both get matched; whichever one
match_org sees is the one that counts, and no explanation budget is spent
twice for the same real-world opportunity."""

import uuid
from datetime import UTC, datetime

import pytest
from app.core.db import async_session_factory
from app.modules.identity.models import Org, OrgType
from app.modules.ingestion.models import BiddingTrack, Tender, TenderGroup
from app.modules.matching.models import Match
from app.modules.matching.service import match_org
from app.modules.profiles.models import CompanyProfile
from app.modules.qualification.models import Qualification, QualificationMethod, QualificationStatus
from app.modules.sources.models import Source, SourceType, ToSStatus
from sqlalchemy import delete, select

_VECTOR = [0.1] * 1024


@pytest.mark.integration
async def test_two_sibling_tenders_in_one_group_produce_one_match() -> None:
    async with async_session_factory() as session:
        org = Org(name="Test Diaspora Org", org_type=OrgType.DIASPORA, country="US")
        session.add(org)
        await session.flush()

        profile = CompanyProfile(
            org_id=org.id,
            source_text="Software consultancy",
            sectors=["ICT"],
            capabilities=["software development"],
            profile_embedding=_VECTOR,
        )
        session.add(profile)

        source_a = Source(
            key=f"egp-{uuid.uuid4()}",
            name="egp",
            type=SourceType.API,
            base_url="https://example.test",
            tos_status=ToSStatus.ALLOWED,
            enabled=False,
        )
        source_b = Source(
            key=f"wb-{uuid.uuid4()}",
            name="wb",
            type=SourceType.API,
            base_url="https://example.test",
            tos_status=ToSStatus.ALLOWED,
            enabled=False,
        )
        session.add_all([source_a, source_b])
        await session.flush()

        group = TenderGroup()
        session.add(group)
        await session.flush()

        closing = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
        tender_a = Tender(
            source_id=source_a.id,
            source_tender_id=f"A-{uuid.uuid4()}",
            url="https://example.test/a",
            title="Digital service taxonomy consulting",
            buyer="Ministry of Innovation",
            closing_at=closing,
            bidding_track=BiddingTrack.DONOR,
            embedding=_VECTOR,
            group_id=group.id,
            raw_data={},
        )
        tender_b = Tender(
            source_id=source_b.id,
            source_tender_id=f"B-{uuid.uuid4()}",
            url="https://example.test/b",
            title="Digital Service Taxonomy Consulting",
            buyer="Ministry of Innovation",
            closing_at=closing,
            bidding_track=BiddingTrack.DONOR,
            embedding=_VECTOR,
            group_id=group.id,  # same group -- the two sides of ADR-028's test
            raw_data={},
        )
        session.add_all([tender_a, tender_b])
        await session.flush()

        session.add_all(
            [
                Qualification(
                    tender_id=tender_a.id,
                    status=QualificationStatus.QUALIFIED,
                    sector="ICT",
                    method=QualificationMethod.RULE,
                ),
                Qualification(
                    tender_id=tender_b.id,
                    status=QualificationStatus.QUALIFIED,
                    sector="ICT",
                    method=QualificationMethod.RULE,
                ),
            ]
        )
        await session.flush()

        try:
            ranked = await match_org(session, org.id, limit=10, kernel=None)
            await session.commit()

            assert {r.tender.id for r in ranked} == {tender_a.id, tender_b.id}
            new_count = sum(1 for r in ranked if r.persisted)
            assert new_count == 1  # one group, one persisted Match -- never two

            match_rows = (
                (await session.execute(select(Match).where(Match.org_id == org.id))).scalars().all()
            )
            assert len(match_rows) == 1
        finally:
            await session.execute(delete(Match).where(Match.org_id == org.id))
            await session.execute(
                delete(Qualification).where(Qualification.tender_id.in_([tender_a.id, tender_b.id]))
            )
            await session.execute(delete(Tender).where(Tender.id.in_([tender_a.id, tender_b.id])))
            await session.execute(delete(TenderGroup).where(TenderGroup.id == group.id))
            await session.execute(delete(CompanyProfile).where(CompanyProfile.org_id == org.id))
            await session.execute(delete(Org).where(Org.id == org.id))
            await session.execute(delete(Source).where(Source.id.in_([source_a.id, source_b.id])))
            await session.commit()
