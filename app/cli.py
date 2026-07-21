"""Developer CLI — run pipeline steps by hand without Celery.

    uv run python -m app.cli seed              # seed the source registry
    uv run python -m app.cli ingest worldbank  # fetch + upsert; print a report
    uv run python -m app.cli tenders           # show what's in the DB
    uv run python -m app.cli seed-profiles     # Week-3 spike: 3 demo company profiles
    uv run python -m app.cli embed             # embed tenders that lack vectors
    uv run python -m app.cli demo              # match every profile + print judgment sheet

This is the "admin dry-run" surface (FR-11.3) until the real admin UI exists.
Prefix with DEBUG=false to silence SQL echo.
"""

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import func, select

from app.core.db import async_session_factory
from app.modules.identity.models import Org, OrgType
from app.modules.ingestion.models import Tender
from app.modules.ingestion.tasks import run_source
from app.modules.sources.service import seed_sources


# Week-3 spike profiles. REALISTIC BUT AUTHORED, not interviewed companies — good
# enough to judge matching quality; swap in real firms before citing any G0-style
# conclusion (master plan §8: no product decision may cite an uncast persona).
@dataclass(frozen=True)
class DemoProfile:
    org_name: str
    org_type: OrgType
    country: str
    timezone: str
    source_text: str
    sectors: list[str]
    capabilities: list[str]
    regions: list[str]


DEMO_PROFILES: list[DemoProfile] = [
    DemoProfile(
        org_name="Habesha Build Contractors PLC",
        org_type=OrgType.LOCAL,
        country="ET",
        timezone="Africa/Addis_Ababa",
        source_text=(
            "Grade-3 general building contractor based in Addis Ababa. We construct "
            "schools, health posts, latrines, and small water-supply lines for woreda- "
            "and zone-level government clients across Amhara and Oromia. 45 permanent "
            "staff, own mixers and scaffolding, ETB 20M annual turnover, experienced "
            "with government tender paperwork and site handover."
        ),
        sectors=["construction", "water and sanitation"],
        capabilities=[
            "building construction",
            "latrine construction",
            "water line installation",
            "site supervision",
        ],
        regions=["Addis Ababa", "Amhara", "Oromia"],
    ),
    DemoProfile(
        org_name="Selam Digital Solutions LLC",
        org_type=OrgType.DIASPORA,
        country="US",
        timezone="America/Los_Angeles",
        source_text=(
            "Ethiopian-American software consultancy in Seattle with a remote team in "
            "Addis Ababa. We build web and mobile applications, data platforms and "
            "dashboards, and advise on digital government services: service taxonomies, "
            "process digitization, and e-government portals for public-sector and NGO "
            "clients."
        ),
        sectors=["ICT", "consulting"],
        capabilities=[
            "software development",
            "digital government consulting",
            "service taxonomy design",
            "data systems and dashboards",
        ],
        regions=["remote", "Addis Ababa"],
    ),
    DemoProfile(
        org_name="Nile Office & Medical Supplies PLC",
        org_type=OrgType.LOCAL,
        country="ET",
        timezone="Africa/Addis_Ababa",
        source_text=(
            "Import and supply company in Addis Ababa serving government and NGO "
            "buyers: office equipment (printers, laptops, photocopiers), office "
            "furniture, and basic medical consumables. Framework-agreement experience "
            "and after-sales service coverage."
        ),
        sectors=["goods supply", "ICT equipment", "medical supplies"],
        capabilities=[
            "supply of printers and laptops",
            "office equipment supply",
            "office furniture supply",
            "medical consumables supply",
        ],
        regions=["Addis Ababa", "nationwide delivery"],
    ),
]


async def _seed() -> None:
    async with async_session_factory() as session:
        await seed_sources(session)
    print("seeded source registry")


async def _ingest(source_key: str) -> None:
    report = await run_source(source_key)
    print(
        f"[{report.source}] seen={report.seen} "
        f"created={report.created} updated={report.updated} unchanged={report.unchanged}"
    )


async def _tenders() -> None:
    async with async_session_factory() as session:
        total = (await session.execute(select(func.count()).select_from(Tender))).scalar_one()
        rows = (
            (await session.execute(select(Tender).order_by(Tender.created_at.desc()).limit(10)))
            .scalars()
            .all()
        )
        print(f"{total} tenders in db. latest 10:")
        for t in rows:
            deadline = t.closing_at.date().isoformat() if t.closing_at else "—"
            print(f"  [{deadline}] {t.title[:70]}")


async def _seed_profiles() -> None:
    from app.modules.profiles.service import upsert_profile

    async with async_session_factory() as session:
        for spec in DEMO_PROFILES:
            org = (
                await session.execute(select(Org).where(Org.name == spec.org_name))
            ).scalar_one_or_none()
            if org is None:
                org = Org(
                    name=spec.org_name,
                    org_type=spec.org_type,
                    country=spec.country,
                    timezone=spec.timezone,
                )
                session.add(org)
                await session.flush()
            await upsert_profile(
                session,
                org_id=org.id,
                source_text=spec.source_text,
                sectors=spec.sectors,
                capabilities=spec.capabilities,
                regions=spec.regions,
            )
            print(f"profile ready: {spec.org_name}")
        await session.commit()


async def _embed() -> None:
    from app.modules.ingestion.service import embed_pending

    async with async_session_factory() as session:
        n = await embed_pending(session)
        await session.commit()
    print(f"embedded {n} tenders (already-embedded rows skipped — idempotent)")


async def _demo() -> None:
    """The Week-3 judgment sheet: every profile's top matches, scores visible.

    A human reads this and answers the go/no-go questions (plan, Week 3): are the
    matches relevant? would a real bidder act on this? Explanations are absent by
    honesty: prompt B3 needs an LLM key this environment doesn't have.
    """
    from app.modules.matching.service import match_org
    from app.modules.profiles.service import list_profiles

    async with async_session_factory() as session:
        profiles = await list_profiles(session)
        if not profiles:
            print("no profiles — run `seed-profiles` first")
            return
        for profile in profiles:
            org = await session.get(Org, profile.org_id)
            if org is None:  # orphaned profile; nothing to display
                continue
            print(f"\n=== {org.name}  ({org.org_type.value}, {org.country}) ===")
            print(f"    sectors: {', '.join(profile.sectors)}")
            ranked = await match_org(session, org.id, limit=8)
            if not ranked:
                print("    (no tenders above the similarity floor)")
            for r in ranked:
                deadline = (
                    r.tender.closing_at.date().isoformat() if r.tender.closing_at else "no deadline"
                )
                flag = "NEW" if r.persisted else "seen"
                print(f"    {r.score:.3f} [{flag}] [{deadline}] {r.tender.title[:64]}")
        await session.commit()
    print("\nJudge honestly (plan Week 3): relevant? actionable? would a bidder trust it?")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, *rest = args
    match cmd:
        case "seed":
            asyncio.run(_seed())
        case "ingest":
            asyncio.run(_ingest(rest[0] if rest else "worldbank"))
        case "tenders":
            asyncio.run(_tenders())
        case "seed-profiles":
            asyncio.run(_seed_profiles())
        case "embed":
            asyncio.run(_embed())
        case "demo":
            asyncio.run(_demo())
        case _:
            print(f"unknown command: {cmd}")
            print(__doc__)


if __name__ == "__main__":
    main()
