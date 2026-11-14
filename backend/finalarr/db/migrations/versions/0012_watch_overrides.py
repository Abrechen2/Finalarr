"""manual corrections of watched state

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watch_overrides",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("media_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "series_id",
            sa.Integer(),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("season_number", sa.Integer(), primary_key=True),
        sa.Column("episode_number", sa.Integer(), primary_key=True),
        sa.Column("watched", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("watch_overrides")
