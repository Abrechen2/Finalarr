"""series details from Sonarr, postponed episodes

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_OLD = (
    "type IN ('season_announced', 'episodes_available', 'finale_available', "
    "'season_complete', 'part_complete', 'sequel_announced', 'news_mention')"
)
_NEW = _OLD[:-1] + ", 'episode_delayed')"


def upgrade() -> None:
    with op.batch_alter_table("series") as batch_op:
        batch_op.add_column(sa.Column("fanart_url", sa.String(1000), nullable=True))
        batch_op.add_column(sa.Column("overview", sa.Text(), server_default="", nullable=False))
        batch_op.add_column(sa.Column("network", sa.String(200), server_default="", nullable=False))
        batch_op.add_column(sa.Column("runtime", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("genres_json", sa.Text(), server_default="[]", nullable=False)
        )
    with op.batch_alter_table("episodes") as batch_op:
        batch_op.add_column(sa.Column("delayed_from", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_type", type_="check")
        batch_op.create_check_constraint("ck_events_type", _NEW)


def downgrade() -> None:
    op.execute("DELETE FROM events WHERE type = 'episode_delayed'")
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_type", type_="check")
        batch_op.create_check_constraint("ck_events_type", _OLD)
    with op.batch_alter_table("episodes") as batch_op:
        batch_op.drop_column("delayed_from")
    with op.batch_alter_table("series") as batch_op:
        for column in ("genres_json", "runtime", "network", "overview", "fanart_url"):
            batch_op.drop_column(column)
