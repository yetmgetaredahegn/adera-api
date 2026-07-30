"""Celery matching tasks (M7, FR-7.1).

Honest gap this closes: `PUT /api/v1/org/profile` triggers match_org() on
save, but nothing re-ran matching for a tender ingested AFTER an org's last
profile save. A daily ingest run growing the corpus produced zero new
matches for anyone who wasn't actively editing their profile that day.
"""

import asyncio
import logging

from app.core.db import async_session_factory
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def run_matching_sweep() -> int:
    """Re-run match_org() for every org with a company profile. Returns the
    count of newly-persisted matches across all orgs. Top-level (not nested
    in the Celery task) so tests can await it directly without going through
    asyncio.run() inside an already-running event loop.

    match_org() is idempotent per (org, GROUP) -- re-running it for an org
    with nothing new costs one query and zero writes, so this is safe to run
    on a schedule regardless of how much (or little) actually changed.
    """
    from app.kernel.router import build_kernel
    from app.modules.identity.service import AudienceRestricted
    from app.modules.matching.service import match_org
    from app.modules.profiles.service import list_profiles

    kernel = build_kernel()
    new_matches = 0
    async with async_session_factory() as session:
        profiles = await list_profiles(session)
        for profile in profiles:
            try:
                ranked = await match_org(session, profile.org_id, kernel=kernel)
            except AudienceRestricted:
                # ADR-029: local orgs never match -- expected, not an error.
                continue
            except Exception:
                # One org's bad data must never take down the whole sweep.
                logger.exception("matching sweep failed for org %s", profile.org_id)
                continue
            new_matches += sum(1 for r in ranked if r.persisted)
        await session.commit()
    return new_matches


@celery_app.task(name="matching.rerun_sweep")  # type: ignore[untyped-decorator]
def rerun_matching_sweep() -> int:
    """Beat-scheduled entrypoint -- see run_matching_sweep() for the logic."""
    return asyncio.run(run_matching_sweep())
