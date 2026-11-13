"""season anilist start

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 15:06:24.534768
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.add_column(sa.Column("anilist_start", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.drop_column("anilist_start")
