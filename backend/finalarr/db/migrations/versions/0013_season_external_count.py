"""episode count of live-action seasons from TVmaze/TMDB/Trakt

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("seasons") as batch_op:
        batch_op.add_column(sa.Column("external_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("external_source", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("seasons") as batch_op:
        batch_op.drop_column("external_source")
        batch_op.drop_column("external_count")
