"""media users remember their first sync (baseline for play dates)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("media_users") as batch_op:
        batch_op.add_column(sa.Column("baseline_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("media_users") as batch_op:
        batch_op.drop_column("baseline_at")
