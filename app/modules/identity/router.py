"""AUTH-1..4 (docs/11_API_REFERENCE.md §1). AUTH-5/6 (verify-email,
password-reset) are NOT built — both need an email/Telegram delivery path
that doesn't exist yet; see docs/proposals/001-auth-implementation-plan.md's
open questions rather than guessing one here."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.deps import current_org, current_session, current_user, require_csrf
from app.core.errors import (
    CONFLICT,
    CSRF_FAILED,
    FORBIDDEN,
    NOT_FOUND,
    ORG_ID_REQUIRED,
    RATE_LIMITED,
    UNAUTHENTICATED,
    APIError,
    problems,
)
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    generate_csrf_token,
    sign_session_id,
)
from app.modules.identity import service
from app.modules.identity.models import Org, OrgType, Session, User
from app.modules.identity.schemas import (
    LoginIn,
    MeOut,
    OrgOut,
    RegisterIn,
    RegisterOut,
    UserOut,
)

# ADR-029: local orgs are supply-side only (facilitator/poster, Phase 3) --
# stated plainly at registration, never discovered later as a silently empty
# feed (identity.service.require_bidder_audience is the enforcement point;
# this is the honest heads-up).
_LOCAL_AUDIENCE_NOTE = (
    "Local companies don't receive AI matching, eligibility verdicts, digests, "
    "or tender Q&A on ADERA today -- those are for diaspora and foreign "
    "bidders. You can register and browse public tenders now, and apply as a "
    "vetted facilitator or verified tender poster once that opens (Phase 3)."
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_auth_cookies(response: Response, session_id: uuid.UUID) -> None:
    # `secure` comes from settings, not a hardcoded True: a Secure cookie is never
    # returned by a browser over plain HTTP, so hardcoding it made the whole auth
    # flow silently unusable for web/mobile on http://localhost while curl (which
    # ignores the flag) still passed. Defaults to True everywhere except env=local.
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sign_session_id(session_id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        max_age=SESSION_MAX_AGE_SECONDS,
        # NOT httponly: the client's JS must be able to read this to echo it
        # back in X-CSRF-Token — that round-trip IS the double-submit check.
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/register",
    status_code=201,
    response_model=RegisterOut,
    responses=problems(CONFLICT, RATE_LIMITED),
)
async def register_route(
    data: RegisterIn, response: Response, db: AsyncSession = Depends(get_session)
) -> RegisterOut:
    try:
        user, org = await service.register(db, data)
    except ValueError as exc:
        raise APIError(409, CONFLICT.code, str(exc)) from exc
    session_row = await service.create_session_row(db, user.id)
    _set_auth_cookies(response, session_row.id)
    return RegisterOut(
        user=UserOut.model_validate(user),
        org=OrgOut.model_validate(org),
        audience_note=_LOCAL_AUDIENCE_NOTE if org.org_type == OrgType.LOCAL else None,
    )


@router.post("/login", response_model=UserOut, responses=problems(UNAUTHENTICATED, RATE_LIMITED))
async def login_route(
    data: LoginIn, response: Response, db: AsyncSession = Depends(get_session)
) -> UserOut:
    user = await service.authenticate(db, data.email, data.password)
    if user is None:
        raise APIError(401, UNAUTHENTICATED.code, "invalid email or password")
    session_row = await service.create_session_row(db, user.id)
    _set_auth_cookies(response, session_row.id)
    return UserOut.model_validate(user)


@router.post(
    "/logout",
    status_code=204,
    responses=problems(UNAUTHENTICATED, CSRF_FAILED, RATE_LIMITED),
)
async def logout_route(
    response: Response,
    session_row: Session = Depends(current_session),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_session),
) -> None:
    await service.revoke_session_row(db, session_row.id)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get(
    "/me",
    response_model=MeOut,
    responses=problems(UNAUTHENTICATED, FORBIDDEN, ORG_ID_REQUIRED, NOT_FOUND, RATE_LIMITED),
)
async def me_route(user: User = Depends(current_user), org: Org = Depends(current_org)) -> MeOut:
    """Session restore. Resolves the org through `current_org`, the same
    dependency every org-scoped route uses, so `/me` and (say) `/matches` can
    never disagree about which org the caller is acting as. It previously took
    the FIRST membership row, which for a multi-org user silently named an org
    that `/matches` would then refuse to serve without `?org_id=`."""
    return MeOut(user=UserOut.model_validate(user), org=OrgOut.model_validate(org))
