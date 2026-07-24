"""Celery notification tasks (M8, FR-8.1)."""

import asyncio

from app.core.db import async_session_factory
from app.modules.identity.models import User
from app.modules.notifications.models import NotificationChannel, NotificationEventType
from app.modules.notifications.service import (
    get_user_digest_items,
    record_notification,
    should_send_digest_now,
)
from app.workers.celery_app import celery_app
from sqlalchemy import select


@celery_app.task(name="notifications.send_digest_sweep")  # type: ignore[untyped-decorator]
def send_digest_sweep() -> int:
    """Hourly Beat sweep: checks all users whose local time is 8:00 AM (FR-8.1)."""

    async def _sweep() -> int:
        async with async_session_factory() as session:
            users = (await session.execute(select(User))).scalars().all()
            count = 0
            for user in users:
                # Default to EAT (Africa/Addis_Ababa) if user has no timezone configured
                tz = "Africa/Addis_Ababa"
                if should_send_digest_now(tz, target_hour=8):
                    items = await get_user_digest_items(session, user.id)
                    for item in items:
                        sent = await record_notification(
                            session,
                            user.id,
                            item.tender_id,
                            NotificationChannel.EMAIL,
                            NotificationEventType.DIGEST,
                        )
                        if sent:
                            count += 1
            await session.commit()
            return count

    return asyncio.run(_sweep())
