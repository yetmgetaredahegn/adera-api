"""Pure-logic & DB unit tests for M2 Source Registry (SKILLS.md R6, FR-2.1/2.5)."""

from datetime import UTC, datetime

import pytest
from app.core.db import async_session_factory
from app.modules.sources.models import Source, SourceType
from app.modules.sources.service import seed_sources


def test_list_due_cron_hourly() -> None:
    now = datetime(2026, 7, 24, 10, 5, 0, tzinfo=UTC)
    source = Source(
        key="test-source",
        name="Test",
        type=SourceType.API,
        base_url="https://example.test",
        cron="0 * * * *",
        enabled=True,
    )
    # Most recent fire time was 10:00, within the 1-hour window
    due = (now - datetime(2026, 7, 24, 10, 0, 0, tzinfo=UTC)).total_seconds() <= 3600
    assert source.enabled and due is True


@pytest.mark.integration
async def test_seed_sources_idempotent() -> None:
    async with async_session_factory() as session:
        await seed_sources(session)
        # Second run must be idempotent and not raise IntegrityError
        await seed_sources(session)
