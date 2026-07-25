"""AUTH-1..4 (docs/11_API_REFERENCE.md §1). AUTH-5/6 (verify-email,
password-reset) are NOT built — both need an email/Telegram delivery path
that doesn't exist yet; see docs/proposals/001-auth-implementation-plan.md's
open questions rather than guessing one here."""

import uuid

from fastapi import APIRouter, Cookie, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.deps import current_session, current_user
from app.core.errors import APIError
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    csrf_tokens_match,
    generate_csrf_token,
    sign_session_id,
)
from app.modules.identity import service
from app.modules.identity.models import Org, OrgMember, OrgType, Session, User
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


@router.post("/register", status_code=201, response_model=RegisterOut)
async def register_route(
    data: RegisterIn, response: Response, db: AsyncSession = Depends(get_session)
) -> RegisterOut:
    try:
        user, org = await service.register(db, data)
    except ValueError as exc:
        raise APIError(409, "conflict", str(exc)) from exc
    session_row = await service.create_session_row(db, user.id)
    _set_auth_cookies(response, session_row.id)
    return RegisterOut(
        user=UserOut.model_validate(user),
        org=OrgOut.model_validate(org),
        audience_note=_LOCAL_AUDIENCE_NOTE if org.org_type == OrgType.LOCAL else None,
    )


@router.post("/login", response_model=UserOut)
async def login_route(
    data: LoginIn, response: Response, db: AsyncSession = Depends(get_session)
) -> UserOut:
    user = await service.authenticate(db, data.email, data.password)
    if user is None:
        raise APIError(401, "unauthenticated", "invalid email or password")
    session_row = await service.create_session_row(db, user.id)
    _set_auth_cookies(response, session_row.id)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
async def logout_route(
    response: Response,
    session_row: Session = Depends(current_session),
    x_csrf_token: str | None = Header(default=None),
    adera_csrf: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    db: AsyncSession = Depends(get_session),
) -> None:
    if not csrf_tokens_match(adera_csrf, x_csrf_token):
        raise APIError(403, "csrf_failed", "missing or mismatched CSRF token")
    await service.revoke_session_row(db, session_row.id)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get("/me", response_model=MeOut)
async def me_route(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_session)
) -> MeOut:
    membership = (
        (await db.execute(select(OrgMember).where(OrgMember.user_id == user.id))).scalars().first()
    )
    if membership is None:
        raise APIError(403, "forbidden", "user belongs to no organization")
    org = await db.get(Org, membership.org_id)
    if org is None:
        # A membership row pointing at a missing org is a data-integrity bug,
        # not a client error -- surfaced as 500 rather than silently 403ing.
        raise APIError(500, "internal", "organization membership is inconsistent")
    return MeOut(user=UserOut.model_validate(user), org=OrgOut.model_validate(org))
