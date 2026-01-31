"""Add priority fields to agents table.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-01-31

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("priority_score", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("priority_reason", sa.Text(), nullable=True))
    op.add_column(
        "agents",
        sa.Column("priority_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("agents", "priority_updated_at")
    op.drop_column("agents", "priority_reason")
    op.drop_column("agents", "priority_score")
