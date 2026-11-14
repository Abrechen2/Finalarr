"""media servers, watched episodes, follow modes

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("unmatched_json", sa.Text(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('emby', 'jellyfin', 'plex')", name="ck_media_kind"),
    )
    op.create_table(
        "media_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "server_id",
            sa.Integer(),
            sa.ForeignKey("media_servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("remote_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("server_id", "remote_id"),
    )
    op.create_table(
        "watched_episodes",
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
        sa.Column("watched_on", sa.Date(), nullable=True),
    )
    op.create_index("ix_watched_episodes_series_id", "watched_episodes", ["series_id"])
    with op.batch_alter_table("series") as batch_op:
        batch_op.add_column(
            sa.Column("follow_mode", sa.String(10), server_default="auto", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_series_follow_mode", "follow_mode IN ('auto', 'always', 'never')"
        )
    # What the user followed so far was their own choice.
    op.execute("UPDATE series SET follow_mode = 'always' WHERE followed = 1")


def downgrade() -> None:
    with op.batch_alter_table("series") as batch_op:
        batch_op.drop_constraint("ck_series_follow_mode", type_="check")
        batch_op.drop_column("follow_mode")
    op.drop_index("ix_watched_episodes_series_id", "watched_episodes")
    op.drop_table("watched_episodes")
    op.drop_table("media_users")
    op.drop_table("media_servers")
