"""add tender_groups table (ADR-028: cross-source tender identity)

Revision ID: a1c3e8f92b71
Revises: 48419dc0e4ac
Create Date: 2026-07-25 09:00:00.000000

Schema + a same-transaction data backfill: every pre-existing `tenders` row
gets its own new, one-tender `tender_groups` row (a "group of one"), so
`group_id` can be made NOT NULL by the end of this migration rather than left
nullable indefinitely. `find_or_create_group`
(app/modules/ingestion/service.py) assigns a real, possibly-shared group to
every tender created from this point on.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e8f92b71"
down_revision: str | None = "48419dc0e4ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tender_groups",
        sa.Column("has_conflict", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("tenders", sa.Column("group_id", sa.UUID(), nullable=True))

    # Backfill: one new group per pre-existing tender (a "group of one" --
    # ADR-028 draws no distinction between that and a real multi-source
    # cluster). Done as a plain Python loop, not a clever single SQL
    # statement, specifically so row correlation can't silently go wrong --
    # tender/group counts at this stage are small enough that this is cheap.
    bind = op.get_bind()
    tender_ids = bind.execute(sa.text("SELECT id FROM tenders WHERE group_id IS NULL")).scalars().all()
    for tender_id in tender_ids:
        group_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO tender_groups (id, has_conflict, created_at, updated_at) "
                "VALUES (:id, false, now(), now())"
            ),
            {"id": group_id},
        )
        bind.execute(
            sa.text("UPDATE tenders SET group_id = :group_id WHERE id = :tender_id"),
            {"group_id": group_id, "tender_id": tender_id},
        )

    op.alter_column("tenders", "group_id", nullable=False)
    op.create_foreign_key(
        "fk_tenders_group_id_tender_groups",
        "tenders",
        "tender_groups",
        ["group_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_tenders_group_id"), "tenders", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenders_group_id"), table_name="tenders")
    op.drop_constraint("fk_tenders_group_id_tender_groups", "tenders", type_="foreignkey")
    op.drop_column("tenders", "group_id")
    op.drop_table("tender_groups")
