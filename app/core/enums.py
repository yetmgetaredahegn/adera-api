"""Enum column policy, in one place.

Two SQLAlchemy defaults are wrong for us, and both are silent:

1. `Enum(SomeEnum)` persists the member **name** (``'DIASPORA'``), not its
   **value** (``'diaspora'``). Python and JSON would say ``diaspora`` while the
   row said ``DIASPORA`` — and the matching/eligibility SQL (05 §7) is hand-written,
   so it would compare against the wrong literal and quietly match nothing.
2. `native_enum=False` does **not** create a CHECK constraint by default, so the
   column degrades to a plain varchar that accepts any string. Verified: the DB
   happily took ``org_type='banana'``.

`pg_enum` fixes both. Use it for every enum column; never construct
`sa.Enum(...)` directly.
"""

import enum

from sqlalchemy import Enum as SAEnum


def pg_enum[E: enum.Enum](enum_cls: type[E], name: str) -> SAEnum:
    """A varchar-backed enum that stores `.value` and is CHECK-constrained.

    `native_enum=False` (varchar + CHECK) rather than a Postgres ENUM type is
    deliberate: adding a member to a native ENUM requires ALTER TYPE, which does
    not run inside a transactional migration on older PGs and cannot be reverted
    cleanly. A CHECK constraint is rewritten by an ordinary migration.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )
