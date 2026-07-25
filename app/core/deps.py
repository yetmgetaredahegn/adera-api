"""Request-scoped auth dependencies (05 §3). `current_org` is the tenancy
anchor every tenant route must declare (04 §2, AGENTS.md rule 9) — forgetting
it is the fatal leak class.
"""

import uuid
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import (
    CSRF_FAILED,
    FORBIDDEN,
    NOT_FOUND,
    ORG_ID_REQUIRED,
    UNAUTHENTICATED,
    APIError,
)
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    csrf_tokens_match,
    unsign_session_id,
)
from app.modules.identity.models import Org, OrgMember, Session, User


async def current_session(
    adera_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_session),
) -> Session:
    """The base dependency: resolves and validates the session ROW (not just
    the user), because logout needs the row's id to revoke it. FastAPI caches
    a dependency per request, so `current_user` depending on this too costs no
    extra query. 401 on any failure — "no cookie", "bad signature", and
    "expired" all read identically as unauthenticated to the client."""
    if adera_session is None:
        raise APIError(401, UNAUTHENTICATED.code, "no session cookie")

    session_id = unsign_session_id(adera_session)
    if session_id is None:
        raise APIError(401, UNAUTHENTICATED.code, "invalid or expired session")

    row = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one_or_none()
    if row is None or row.revoked_at is not None or row.expires_at < datetime.now(UTC):
        raise APIError(401, UNAUTHENTICATED.code, "session revoked or expired")
    return row


async def current_user(
    session_row: Session = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> User:
    user = await db.get(User, session_row.user_id)
    if user is None or user.deleted_at is not None:
        raise APIError(401, UNAUTHENTICATED.code, "user not found")
    return user


async def require_csrf(
    x_csrf_token: str | None = Header(default=None),
    adera_csrf: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
) -> None:
    """Double-submit CSRF check for unsafe methods (05 §3).

    Logout has done this inline since AUTH-3. As a dependency it is declarable,
    which is what stops the next unsafe endpoint from quietly omitting it --
    exactly the reasoning behind `current_org` for tenancy (rule 9). Cookie auth
    means the browser attaches credentials to a cross-site form post whether the
    user meant it or not; the header echo is the proof that they did.
    """
    if not csrf_tokens_match(adera_csrf, x_csrf_token):
        raise APIError(403, CSRF_FAILED.code, "missing or mismatched CSRF token")


async def current_admin(user: User = Depends(current_user)) -> User:
    """The `admin` auth level (docs/11 §0) for every /admin surface (M11).

    `users.is_staff` has existed since the core schema and nothing read it, so
    the run-ledger and AI-spend endpoints (ADM-2, ADM-5) were reachable by
    anyone with the URL -- unauthenticated. 403 rather than 404 here: unlike a
    cross-org resource, an admin endpoint's existence is public knowledge (it is
    in the published contract), so hiding it buys nothing and a clear `forbidden`
    is easier to debug.
    """
    if not user.is_staff:
        raise APIError(403, FORBIDDEN.code, "staff privileges required")
    return user


async def current_org(
    org_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> Org:
    """Scope decision, open for review (docs/proposals/001, its own open
    questions section): a user with exactly one org membership needs no
    `?org_id=`; a user in multiple orgs must disambiguate explicitly. Asking
    for a foreign org_id 404s rather than 403s — never confirm a resource
    exists to a non-member (docs/11_API_REFERENCE.md §0)."""
    memberships = (
        (await db.execute(select(OrgMember).where(OrgMember.user_id == user.id))).scalars().all()
    )
    if not memberships:
        raise APIError(403, FORBIDDEN.code, "user belongs to no organization")

    if org_id is not None:
        match = next((m for m in memberships if m.org_id == org_id), None)
        if match is None:
            raise APIError(404, NOT_FOUND.code, "organization not found")
        target_id = org_id
    elif len(memberships) == 1:
        target_id = memberships[0].org_id
    else:
        raise APIError(400, ORG_ID_REQUIRED.code, "multiple org memberships; specify ?org_id=")

    org = await db.get(Org, target_id)
    if org is None:
        raise APIError(404, NOT_FOUND.code, "organization not found")
    return org
