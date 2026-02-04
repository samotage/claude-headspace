"""Add max_frustration to activity_metrics.

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-02-05

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "r0s1t2u3v4w5"
down_revision = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activity_metrics", sa.Column("max_frustration", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("activity_metrics", "max_frustration")
