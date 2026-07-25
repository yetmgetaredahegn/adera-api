"""Notifications service logic (M8, FR-8.1/8.4, NFR-INTL-1).

Timezone-aware digest scheduling using `zoneinfo` and channel-level
idempotency tracking to prevent double-sending notifications.
"""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.modules.identity.service import OrgMember, OrgType, get_org
from app.modules.ingestion.service import Tender
from app.modules.matching.service import Match, MatchState
from app.modules.notifications.models import (
    NotificationChannel,
    NotificationEventType,
    NotificationLog,
)
from app.modules.notifications.schemas import DigestItemOut
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def should_send_digest_now(
    user_timezone: str, target_hour: int = 8, current_utc: datetime | None = None
) -> bool:
    """Check if the current local hour in `user_timezone` matches `target_hour` (NFR-INTL-1).

    Uses `zoneinfo.ZoneInfo` for accurate timezone conversion across DST.
    """
    now_utc = current_utc or datetime.now(UTC)
    try:
        tz = ZoneInfo(user_timezone)
        local_time = now_utc.astimezone(tz)
        return local_time.hour == target_hour
    except Exception:
        # Fallback to UTC if timezone string is invalid
        return now_utc.hour == target_hour


def make_idempotency_key(
    user_id: uuid.UUID,
    group_id: uuid.UUID,
    channel: NotificationChannel,
    event_type: NotificationEventType,
) -> str:
    """Keyed on the tender's GROUP (ADR-028), not the tender row itself --
    otherwise the same real-world opportunity notifying via a second source's
    tender row (a different `tender_id`, same `group_id`) would defeat FR-8.4
    entirely and re-notify a user about something they already saw."""
    return f"{user_id}:{group_id}:{channel.value}:{event_type.value}"


async def record_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    tender_id: uuid.UUID,
    group_id: uuid.UUID,
    channel: NotificationChannel,
    event_type: NotificationEventType,
) -> bool:
    """Insert-then-send check (FR-8.4, extended by ADR-028 to key on `group_id`).

    `tender_id` still names the specific row that was actually shown (FK +
    display); `group_id` is what idempotency is computed from. Returns True if
    a notification record was created (new), or False if it was already sent
    for this group.
    """
    key = make_idempotency_key(user_id, group_id, channel, event_type)
    existing = (
        await session.execute(select(NotificationLog).where(NotificationLog.idempotency_key == key))
    ).scalar_one_or_none()

    if existing is not None:
        return False

    log_entry = NotificationLog(
        user_id=user_id,
        tender_id=tender_id,
        channel=channel,
        event_type=event_type,
        idempotency_key=key,
    )
    session.add(log_entry)
    try:
        await session.flush()
        return True
    except IntegrityError:
        return False


async def get_user_digest_items(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 10
) -> list[DigestItemOut]:
    """Fetch un-notified matches for the user's primary organization.

    Local orgs are silently skipped here (ADR-029: supply-side only, never a
    digest recipient) -- unlike the synchronous `matching`/`eligibility`
    guards, this is a bulk background sweep over every user, so "not this
    user" is an ordinary, expected outcome, not a client-facing error to
    surface as 403.
    """
    membership = (
        (await session.execute(select(OrgMember).where(OrgMember.user_id == user_id)))
        .scalars()
        .first()
    )
    if membership is None:
        return []

    org_id = membership.org_id
    org = await get_org(session, org_id)
    if org is None or org.org_type == OrgType.LOCAL:
        return []

    matches = (
        (
            await session.execute(
                select(Match)
                .where(Match.org_id == org_id, Match.state != MatchState.DISMISSED)
                .order_by(Match.score.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    if not matches:
        return []

    tender_ids = [m.tender_id for m in matches]
    tenders = {
        t.id: t
        for t in (await session.execute(select(Tender).where(Tender.id.in_(tender_ids)))).scalars()
    }

    items: list[DigestItemOut] = []
    for m in matches:
        if m.tender_id in tenders:
            t = tenders[m.tender_id]
            items.append(
                DigestItemOut(
                    tender_id=t.id,
                    group_id=t.group_id,
                    title=t.title,
                    buyer=t.buyer,
                    region=t.region,
                    closing_at=t.closing_at,
                    score=m.score,
                    explanation=m.explanation,
                )
            )

    return items
