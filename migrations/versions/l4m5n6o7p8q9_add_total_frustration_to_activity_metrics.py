"""Add total_frustration to activity_metrics.

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-02-03

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activity_metrics", sa.Column("total_frustration", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("activity_metrics", "total_frustration")
