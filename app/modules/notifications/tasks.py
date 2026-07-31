"""Celery notification tasks (M8, FR-8.1)."""

import asyncio
import logging

from app.core.db import async_session_factory
from app.modules.identity.service import User
from app.modules.notifications.models import NotificationChannel, NotificationEventType
from app.modules.notifications.schemas import DigestItemOut
from app.modules.notifications.senders import send_digest_email
from app.modules.notifications.service import (
    get_user_digest_items,
    record_notification,
    should_send_digest_now,
)
from app.workers.celery_app import celery_app
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def run_digest_sweep() -> int:
    """Hourly Beat sweep: checks all users whose local time is 8:00 AM (FR-8.1).

    Top-level (not nested in the Celery task) so tests can await it directly,
    same reasoning as matching.tasks.run_matching_sweep.

    Idempotency is still recorded per-item (ADR-028: keyed on the tender's
    GROUP), but the actual send is batched into ONE email per user covering
    every newly-recordable item -- not one email per tender. Honest caveat,
    not fixed here: the idempotency record is written before send_digest_email
    is even called, so a delivery failure after a successful record still
    counts as "sent" and won't retry. That's the pre-existing idempotency
    model's own behavior (nothing sent before this either), not a regression
    introduced here -- fixing it means reworking record_notification's
    insert-then-send contract, out of scope for wiring the first real sender.
    """
    async with async_session_factory() as session:
        users = (await session.execute(select(User))).scalars().all()
        count = 0
        for user in users:
            # Default to EAT (Africa/Addis_Ababa) if user has no timezone configured
            tz = "Africa/Addis_Ababa"
            if not should_send_digest_now(tz, target_hour=8):
                continue

            items = await get_user_digest_items(session, user.id)
            new_items: list[DigestItemOut] = []
            for item in items:
                sent = await record_notification(
                    session,
                    user.id,
                    item.tender_id,
                    item.group_id,
                    NotificationChannel.EMAIL,
                    NotificationEventType.DIGEST,
                )
                if sent:
                    new_items.append(item)
                    count += 1

            if new_items:
                try:
                    await send_digest_email(user.email, new_items)
                except Exception:
                    # A delivery failure must never take down the whole
                    # sweep -- the idempotency record is already committed
                    # for this batch regardless (see docstring caveat).
                    logger.exception("digest email send failed for user %s", user.id)
        await session.commit()
    return count


@celery_app.task(name="notifications.send_digest_sweep")  # type: ignore[untyped-decorator]
def send_digest_sweep() -> int:
    """Beat-scheduled entrypoint -- see run_digest_sweep() for the logic."""
    return asyncio.run(run_digest_sweep())
