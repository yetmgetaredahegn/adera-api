"""Company profile endpoints (M6, FR-6.1/6.2; docs/11_API_REFERENCE.md PRO-2/PRO-3)
-- the only way a real org creates the profile match_org() runs against.

NOT audience-gated: PRO-2/PRO-3's Errors columns list only 422/404, unlike
MAT-1's 403 audience_restricted -- a company profile is org data, not a
bidder feature. A local org may build one even though match_org() never runs
against it; that gate lives in matching, not here.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_org
from app.core.errors import APIError
from app.kernel.router import build_kernel
from app.modules.identity.service import AudienceRestricted, Org
from app.modules.matching.service import match_org
from app.modules.profiles import service
from app.modules.profiles.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/v1/org/profile", tags=["profiles"])
logger = logging.getLogger(__name__)


@router.get("", response_model=ProfileOut)
async def get_my_profile(
    org: Org = Depends(current_org),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await service.get_profile(session, org.id)
    if profile is None:
        raise APIError(404, "not_found", "no profile yet")
    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut)
async def upsert_my_profile(
    body: ProfileIn,
    org: Org = Depends(current_org),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await service.upsert_profile(
        session,
        org_id=org.id,
        source_text=body.source_text,
        sectors=body.sectors,
        capabilities=body.capabilities,
        certifications=body.certifications,
        regions=body.regions,
    )
    # On the UPDATE path, `updated_at` (onupdate=func.now()) is left expired
    # after flush() rather than eagerly fetched -- Pydantic's synchronous
    # model_validate can't resolve an expired attribute under the async ORM
    # (MissingGreenlet). An explicit refresh forces that fetch inside an
    # awaited context before serialization touches it.
    await session.refresh(profile)

    # Every profile save (create OR edit) re-runs matching for this org,
    # synchronously, right here -- not on a schedule, not on the next GET
    # /matches (that endpoint only ever reads persisted rows, deliberately,
    # so it never pays an LLM call on page load). A profile save is rare
    # enough that a few seconds of latency here is the honest trade-off, and
    # it's the ONLY thing that ever populates a real org's feed today: no
    # cron/worker currently calls match_org() on its own. match_org() is
    # already idempotent per (org, GROUP) -- re-running it after an edit
    # costs nothing for tenders already matched, and finds new candidates the
    # updated embedding now ranks differently.
    try:
        await match_org(session, org.id, limit=10, kernel=build_kernel())
    except AudienceRestricted:
        # ADR-029: local orgs build profiles but are never matched. Expected,
        # not an error -- silently skip, exactly like the CLI demo does.
        pass
    except Exception:
        # A matching failure must never take down profile save -- the
        # profile itself already persisted successfully above. Logged, not
        # swallowed silently, so a real outage is still visible somewhere.
        logger.exception("post-save matching failed for org %s", org.id)

    return ProfileOut.model_validate(profile)
