"""allow sequel_announced events

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-13
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_OLD = (
    "type IN ('season_announced', 'episodes_available', 'finale_available', "
    "'season_complete', 'part_complete')"
)
_NEW = _OLD[:-1] + ", 'sequel_announced')"


def upgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_type", type_="check")
        batch_op.create_check_constraint("ck_events_type", _NEW)


def downgrade() -> None:
    op.execute("DELETE FROM events WHERE type = 'sequel_announced'")
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_type", type_="check")
        batch_op.create_check_constraint("ck_events_type", _OLD)
