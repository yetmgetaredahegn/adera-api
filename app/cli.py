"""Developer CLI — run pipeline steps by hand without Celery.

    uv run python -m app.cli seed              # seed the source registry
    uv run python -m app.cli ingest worldbank  # fetch + upsert; print a report
    uv run python -m app.cli tenders           # show what's in the DB
    uv run python -m app.cli seed-profiles     # Week-3 spike: 3 demo company profiles
    uv run python -m app.cli embed             # embed tenders that lack vectors
    uv run python -m app.cli qualify           # rule + LLM qualify tenders that lack a verdict
    uv run python -m app.cli seed-law          # ingest Article 2 (definitions) of Proc. 1333/2024
    uv run python -m app.cli demo              # match every profile + print judgment sheet
    uv run python -m app.cli demo-login <email> <password> [org]
                                               # attach a login to a demo-profile org

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
        # ADR-029: local orgs are supply-side only (facilitator/poster), never
        # an AI-matching consumer -- flipped from `LOCAL` to a real bidder
        # audience (`FOREIGN`) so `demo` still exercises the product for all
        # three profiles. `Habesha Build Contractors` above stays `LOCAL`
        # specifically to prove the audience gate refuses it (see `_demo`).
        org_name="Nile Office & Medical Supplies FZE",
        org_type=OrgType.FOREIGN,
        country="AE",
        timezone="Asia/Dubai",
        source_text=(
            "Dubai-based export supplier bidding into Ethiopian government and NGO "
            "procurement: office equipment (printers, laptops, photocopiers), office "
            "furniture, and basic medical consumables. Framework-agreement experience "
            "and after-sales service coverage across East Africa."
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


DEFAULT_DEMO_LOGIN_ORG = "Selam Digital Solutions LLC"


async def _demo_login(email: str, password: str, org_name: str) -> None:
    """Attach a real login to one of the authored demo-profile orgs.

    Why this exists: `POST /auth/register` (AUTH-1) always creates a BRAND NEW
    org, and no endpoint can give that org a company profile yet (the profile
    API is unbuilt — docs/PROGRESS.md). So a freshly registered account can
    never have matches, and a browser has no way to reach a populated feed.
    This binds a password login to an org `seed-profiles` already built, so the
    web client exercises the real `/auth/*` + `/matches` path against real
    data. Dev affordance only — it is not reachable over HTTP.
    """
    from app.core.security import hash_password
    from app.modules.identity.models import OrgMember, OrgRole, User

    async with async_session_factory() as session:
        org = (await session.execute(select(Org).where(Org.name == org_name))).scalar_one_or_none()
        if org is None:
            print(f"no org named {org_name!r} — run `seed-profiles` first")
            return

        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, password_hash=hash_password(password))
            session.add(user)
            await session.flush()
        else:
            user.password_hash = hash_password(password)

        member = (
            (await session.execute(select(OrgMember).where(OrgMember.user_id == user.id)))
            .scalars()
            .first()
        )
        if member is None:
            session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.OWNER))
        else:
            # A prior `/auth/register` already gave this email its own brand-new
            # org. Re-point it, or the caller silently keeps logging into the
            # profile-less org while this command reports the target one.
            member.org_id = org.id
        await session.commit()
        print(f"login ready: {email} -> {org_name} ({org.org_type.value})")


async def _embed() -> None:
    from app.modules.ingestion.service import embed_pending

    async with async_session_factory() as session:
        n = await embed_pending(session)
        await session.commit()
    print(f"embedded {n} tenders (already-embedded rows skipped — idempotent)")


async def _qualify() -> None:
    """Rule stage (free) + LLM stage (prompt B2) over every tender without a
    qualification row yet. Rule-rejected tenders never reach the LLM — see
    app/modules/qualification/service.py for which notice types and why."""
    from app.kernel.router import build_kernel
    from app.modules.qualification.models import Qualification, QualificationStatus
    from app.modules.qualification.service import qualify_tender

    kernel = build_kernel()
    counts: dict[str, int] = {}
    async with async_session_factory() as session:
        already = select(Qualification.tender_id)
        pending = (await session.execute(select(Tender).where(Tender.id.not_in(already)))).scalars()
        for tender in pending:
            q = await qualify_tender(session, tender, kernel)
            counts[q.status.value] = counts.get(q.status.value, 0) + 1
        await session.commit()
    if not counts:
        print("nothing to qualify — every tender already has a verdict")
        return
    for status in (
        QualificationStatus.QUALIFIED,
        QualificationStatus.REJECTED,
        QualificationStatus.NEEDS_REVIEW,
    ):
        print(f"{status.value}: {counts.get(status.value, 0)}")


async def _seed_law() -> None:
    from app.kernel.embeddings import embed_texts
    from app.modules.eligibility.ingest import seed_law_corpus

    async with async_session_factory() as session:
        n = await seed_law_corpus(session, embed_texts)
    print(f"seeded {n} new law chunks (already-seeded article refs skipped — idempotent)")


async def _demo() -> None:
    """The judgment sheet: every profile's top matches, scores visible.

    A human reads this and answers the go/no-go questions: are the matches
    relevant? would a real bidder act on this? Explanations are generated when a
    provider key is present (OPENROUTER_API_KEY or similar) — absent one, they
    stay None rather than faked (AGENTS.md rule 11).
    """
    from app.kernel.router import build_kernel
    from app.modules.identity.service import AudienceRestricted
    from app.modules.matching.service import match_org
    from app.modules.profiles.service import list_profiles

    kernel = build_kernel()

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
            try:
                ranked = await match_org(session, org.id, limit=8, kernel=kernel)
            except AudienceRestricted:
                # ADR-029: local orgs are supply-side only. Printed, not
                # silently skipped -- the demo's whole point is to make this
                # gate visible, not to hide it.
                print("    audience_restricted: local orgs don't receive AI matching (ADR-029)")
                continue
            if not ranked:
                print("    (no tenders above the similarity floor)")
            for r in ranked:
                deadline = (
                    r.tender.closing_at.date().isoformat() if r.tender.closing_at else "no deadline"
                )
                flag = "NEW" if r.persisted else "seen"
                print(f"    {r.score:.3f} [{flag}] [{deadline}] {r.tender.title[:64]}")
                if r.explanation:
                    print(f'        -> "{r.explanation}"')
        await session.commit()


async def _dry_run(source_key: str) -> None:
    from app.modules.sources.service import dry_run_source

    async with async_session_factory() as session:
        raws = await dry_run_source(session, source_key)
        print(f"[{source_key}] dry-run parsed {len(raws)} tenders (zero database writes):")
        for r in raws[:10]:
            print(f"  - {getattr(r, 'title', str(r))[:80]}")


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
        case "dry-run":
            asyncio.run(_dry_run(rest[0] if rest else "egp"))
        case "tenders":
            asyncio.run(_tenders())
        case "seed-profiles":
            asyncio.run(_seed_profiles())
        case "embed":
            asyncio.run(_embed())
        case "qualify":
            asyncio.run(_qualify())
        case "seed-law":
            asyncio.run(_seed_law())
        case "demo":
            asyncio.run(_demo())
        case "demo-login":
            if len(rest) < 2:
                print("usage: demo-login <email> <password> [org_name]")
                return
            org_name = rest[2] if len(rest) > 2 else DEFAULT_DEMO_LOGIN_ORG
            asyncio.run(_demo_login(rest[0], rest[1], org_name))
        case _:
            print(f"unknown command: {cmd}")
            print(__doc__)


if __name__ == "__main__":
    main()
