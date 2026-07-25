"""Auth business logic (M1, AUTH-1..4) + the audience gate (ADR-029)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SESSION_MAX_AGE_SECONDS, hash_password, verify_password
from app.modules.identity.models import (
    Org as Org,
)
from app.modules.identity.models import (
    OrgMember as OrgMember,
)
from app.modules.identity.models import (
    OrgRole,
    Session,
)
from app.modules.identity.models import (
    OrgType as OrgType,
)
from app.modules.identity.models import (
    User as User,
)
from app.modules.identity.schemas import RegisterIn


class AudienceRestricted(Exception):
    """Raised when a `local`-type org calls a bidder-only feature (ADR-029).

    ADERA's paying bidder audience is diaspora/foreign companies only; local
    orgs are supply-side (facilitator/poster, Phase 3) and never receive AI
    matching, eligibility verdicts, digests, or tender Q&A. Callers map this to
    **403 `audience_restricted`** (docs/11_API_REFERENCE.md §0) — never a
    silently empty result, which would be indistinguishable from a bug."""

    def __init__(self, org_type: OrgType) -> None:
        self.org_type = org_type
        super().__init__(
            f"org_type={org_type.value} is supply-side only (ADR-029); bidder "
            "features (matching, eligibility, digests, Q&A) are for diaspora/"
            "foreign orgs"
        )


def require_bidder_audience(org: Org) -> None:
    """The audience gate every bidder-only feature calls first (ADR-029).

    A diaspora-owned, Ethiopia-registered org still has `org_type=diaspora`
    (FR-1.6: `org_type` is the org's relationship to Ethiopia, `country` is
    where it's registered — the two are independent) and passes this gate; it
    remains a full paying customer with domestic NCB standing besides.
    """
    if org.org_type == OrgType.LOCAL:
        raise AudienceRestricted(org.org_type)


async def get_org(session: AsyncSession, org_id: uuid.UUID) -> Org | None:
    return await session.get(Org, org_id)


async def register(session: AsyncSession, data: RegisterIn) -> tuple[User, Org]:
    """Raises ValueError on a duplicate email — the router maps this to 409
    (docs/11 §1: AUTH-1 "409 email exists")."""
    existing = (
        await session.execute(select(User).where(User.email == data.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("email already registered")

    user = User(email=data.email, password_hash=hash_password(data.password))
    session.add(user)
    await session.flush()

    org = Org(
        name=data.org_name,
        org_type=OrgType(data.org_type),
        country=data.country,
        timezone=data.timezone,
    )
    session.add(org)
    await session.flush()

    session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.OWNER))
    await session.flush()
    return user, org


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """None on any failure (no such user, wrong password) — never distinguish
    the two to a client (that would leak which emails are registered)."""
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def create_session_row(session: AsyncSession, user_id: uuid.UUID) -> Session:
    row = Session(
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
    )
    session.add(row)
    await session.flush()
    return row


async def revoke_session_row(session: AsyncSession, session_id: uuid.UUID) -> None:
    row = await session.get(Session, session_id)
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await session.flush()
