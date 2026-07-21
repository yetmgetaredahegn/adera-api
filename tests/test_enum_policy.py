"""Regression tests for the enum column policy (app/core/enums.py).

Both behaviours here were real bugs found by probing the live schema, and both
were silent — nothing failed, the data was just wrong. They are cheap to
reintroduce (one `sa.Enum(...)` written by hand) and expensive to find later,
so they get tests.
"""

import enum

import pytest
from app.core.db import async_session_factory
from app.core.enums import pg_enum
from app.modules.identity.models import Org, OrgType
from sqlalchemy import text


class _Sample(enum.StrEnum):
    ALPHA = "alpha"
    BETA = "beta"


def test_pg_enum_persists_values_not_names() -> None:
    """SQLAlchemy's default persists `.name` ('ALPHA'); we require `.value`.

    The matching and eligibility queries (05 §7) are hand-written SQL comparing
    against literals like 'diaspora'. If the column held 'DIASPORA', those
    comparisons would match zero rows and the feed would just look empty.
    """
    col = pg_enum(_Sample, "sample")
    assert sorted(col.enums) == ["alpha", "beta"]


def test_pg_enum_creates_a_check_constraint() -> None:
    """Without create_constraint=True the column is a bare varchar.

    Verified against the live DB before this fix: it accepted org_type='banana'.
    """
    col = pg_enum(_Sample, "sample")
    assert col.create_constraint is True
    assert col.native_enum is False


@pytest.mark.integration
async def test_org_type_roundtrips_as_lowercase_value() -> None:
    async with async_session_factory() as session:
        org = Org(
            name="enum-policy-test",
            org_type=OrgType.DIASPORA,
            country="US",
            timezone="America/Seattle",
        )
        session.add(org)
        await session.commit()

        stored = (
            await session.execute(text("SELECT org_type FROM orgs WHERE name = 'enum-policy-test'"))
        ).scalar_one()

        assert stored == "diaspora"
        assert stored == OrgType.DIASPORA.value

        await session.execute(text("DELETE FROM orgs WHERE name = 'enum-policy-test'"))
        await session.commit()


@pytest.mark.integration
async def test_database_rejects_values_outside_the_enum() -> None:
    """The DB, not just Python, must enforce the domain."""
    from sqlalchemy.exc import IntegrityError

    async with async_session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO orgs (id, name, org_type, country, timezone, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), 'bad-enum-test', 'banana', 'ET', 'UTC', now(), now())"
                )
            )
            await session.commit()
        await session.rollback()
