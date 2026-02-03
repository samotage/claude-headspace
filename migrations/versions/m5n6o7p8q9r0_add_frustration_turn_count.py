"""Add frustration_turn_count to activity_metrics.

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2026-02-03

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "m5n6o7p8q9r0"
down_revision = "l4m5n6o7p8q9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activity_metrics", sa.Column("frustration_turn_count", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("activity_metrics", "frustration_turn_count")
