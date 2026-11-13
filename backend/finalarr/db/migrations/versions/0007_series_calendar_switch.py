"""series calendar switch

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13 22:43:13.927648
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("series", schema=None) as batch_op:
        batch_op.add_column(sa.Column("calendar", sa.Boolean(), server_default="1", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("series", schema=None) as batch_op:
        batch_op.drop_column("calendar")
