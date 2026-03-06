"""add agent voice_unread_since

Revision ID: f484c4bca281
Revises: 73f76234a592
Create Date: 2026-03-06 17:11:21.009523

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f484c4bca281"
down_revision = "73f76234a592"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("voice_unread_since", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("voice_unread_since")
