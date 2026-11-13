"""fribb ids

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13 22:14:29.763089
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fribb_ids",
        sa.Column("anilist_id", sa.Integer(), nullable=False),
        sa.Column("mal_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("anilist_id"),
    )
    with op.batch_alter_table("fribb_ids", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_fribb_ids_mal_id"), ["mal_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("fribb_ids", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_fribb_ids_mal_id"))

    op.drop_table("fribb_ids")
