"""remember the last webhook call per Sonarr instance

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sonarr_instances") as batch_op:
        batch_op.add_column(sa.Column("last_webhook_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sonarr_instances") as batch_op:
        batch_op.drop_column("last_webhook_at")
