"""series tags

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13 15:40:32.104004
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("series", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tags_json", sa.Text(), server_default="[]", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("series", schema=None) as batch_op:
        batch_op.drop_column("tags_json")
