"""Eligibility endpoint (M16, FR-16.2; docs/11_API_REFERENCE.md ELI-1) -- the
only way a client reaches assess_eligibility(). The engine has existed for a
while; nothing outside the CLI/tests could call it until this router.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_org
from app.core.errors import APIError
from app.kernel.router import build_kernel
from app.modules.eligibility import service
from app.modules.eligibility.schemas import EligibilityResponseOut
from app.modules.identity.service import AudienceRestricted, Org
from app.modules.ingestion.service import Tender

router = APIRouter(prefix="/api/v1/tenders", tags=["eligibility"])


@router.get("/{tender_id}/eligibility", response_model=EligibilityResponseOut)
async def get_tender_eligibility(
    tender_id: uuid.UUID,
    org: Org = Depends(current_org),
    session: AsyncSession = Depends(get_session),
) -> EligibilityResponseOut:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise APIError(404, "not_found", "tender not found")

    cached = await service.get_cached_assessment(session, org.id, tender_id)
    if cached is not None:
        return EligibilityResponseOut.from_assessment(cached)

    try:
        result = await service.assess_eligibility(session, org, tender, kernel=build_kernel())
    except AudienceRestricted as exc:
        raise APIError(403, "audience_restricted", str(exc)) from exc

    row = await service.cache_assessment(session, org.id, tender_id, result)
    return EligibilityResponseOut.from_assessment(row)
