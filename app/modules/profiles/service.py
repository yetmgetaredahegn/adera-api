"""Profiles service (M6, FR-6.1/6.2) — the public surface other modules import.

A profile's embedding is computed from a canonical text built out of its CONFIRMED
facts. Grounding rule downstream (B3, eval C3): explanations may only cite what is
stored here — an unconfirmed guess never becomes a "fact about the company".
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profiles.models import CompanyProfile


def profile_text(
    source_text: str,
    sectors: list[str],
    capabilities: list[str],
    certifications: list[str],
    regions: list[str],
) -> str:
    """Canonical embedding input. Kept as one function so profile and tender
    embeddings can never drift apart in format by accident."""
    parts = [
        f"Sectors: {', '.join(sectors)}" if sectors else "",
        f"Capabilities: {', '.join(capabilities)}" if capabilities else "",
        f"Certifications: {', '.join(certifications)}" if certifications else "",
        f"Regions: {', '.join(regions)}" if regions else "",
        source_text,
    ]
    return "\n".join(p for p in parts if p)


async def get_profile(session: AsyncSession, org_id: uuid.UUID) -> CompanyProfile | None:
    return (
        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
    ).scalar_one_or_none()


async def list_profiles(session: AsyncSession) -> list[CompanyProfile]:
    rows = await session.execute(select(CompanyProfile).where(CompanyProfile.deleted_at.is_(None)))
    return list(rows.scalars().all())


async def upsert_profile(
    session: AsyncSession,
    org_id: uuid.UUID,
    source_text: str,
    sectors: list[str],
    capabilities: list[str],
    certifications: list[str] | None = None,
    regions: list[str] | None = None,
) -> CompanyProfile:
    """Create or update the org's profile and (re)embed it (FR-6.2).

    Any change re-embeds: a stale embedding silently degrades matching, which is
    worse than the few seconds of CPU this costs.
    """
    from app.kernel.embeddings import embed_texts  # lazy: torch-heavy

    certifications = certifications or []
    regions = regions or []

    text = profile_text(source_text, sectors, capabilities, certifications, regions)
    embedding = embed_texts([text])[0]

    profile = await get_profile(session, org_id)
    if profile is None:
        profile = CompanyProfile(org_id=org_id, source_text=source_text)
        session.add(profile)

    profile.source_text = source_text
    profile.sectors = sectors
    profile.capabilities = capabilities
    profile.certifications = certifications
    profile.regions = regions
    profile.profile_embedding = embedding

    await session.flush()
    return profile
