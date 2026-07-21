"""enable pgvector

Separate from the table migration on purpose: the extension must exist before any
Vector column is created, and keeping it alone makes it obvious that ADR-006
(vectors live in Postgres, no dedicated vector DB) is a schema-level commitment.

Revision ID: 0001
Revises:
Create Date: 2026-07-16

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Not dropped: other schemas in the same database may depend on it, and
    # dropping an extension cascades into data loss. Dropping is a manual act.
    pass
