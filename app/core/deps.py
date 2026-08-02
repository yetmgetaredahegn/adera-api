"""Request-scoped auth dependencies (05 §3). `current_org` is the tenancy
anchor every tenant route must declare (04 §2, AGENTS.md rule 9) — forgetting
it is the fatal leak class.
"""

import uuid
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import APIError
from app.core.security import SESSION_COOKIE_NAME, unsign_session_id
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
        raise APIError(401, "unauthenticated", "no session cookie")

    session_id = unsign_session_id(adera_session)
    if session_id is None:
        raise APIError(401, "unauthenticated", "invalid or expired session")

    row = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one_or_none()
    if row is None or row.revoked_at is not None or row.expires_at < datetime.now(UTC):
        raise APIError(401, "unauthenticated", "session revoked or expired")
    return row


async def current_user(
    session_row: Session = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> User:
    user = await db.get(User, session_row.user_id)
    if user is None or user.deleted_at is not None:
        raise APIError(401, "unauthenticated", "user not found")
    return user


async def current_platform_admin(user: User = Depends(current_user)) -> User:
    """The gate `/admin/*` endpoints were missing entirely until now (found
    2026-08-02, docs/PROGRESS.md): `GET /admin/run-ledger` and `/spend` had
    no auth check of any kind, tenant-scoped or otherwise -- anyone who could
    reach the API could read internal pipeline/spend data. `User.is_staff`
    already existed on the model and in the live DB, unused everywhere;
    this is its first real consumer. Distinct from `OrgRole` (an org's own
    owner/member/admin roles, scoped to that one org) -- platform admin is
    the master plan's P6 founder-operator persona, not tied to any org."""
    if not user.is_staff:
        raise APIError(403, "forbidden", "platform admin access required")
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
        raise APIError(403, "forbidden", "user belongs to no organization")

    if org_id is not None:
        match = next((m for m in memberships if m.org_id == org_id), None)
        if match is None:
            raise APIError(404, "not_found", "organization not found")
        target_id = org_id
    elif len(memberships) == 1:
        target_id = memberships[0].org_id
    else:
        raise APIError(400, "org_id_required", "multiple org memberships; specify ?org_id=")

    org = await db.get(Org, target_id)
    if org is None:
        raise APIError(404, "not_found", "organization not found")
    return org
