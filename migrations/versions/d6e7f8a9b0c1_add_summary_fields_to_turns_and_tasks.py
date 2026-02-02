"""Add summary fields to turns and tasks tables.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-01-31

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("turns", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "turns",
        sa.Column("summary_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("tasks", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("summary_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("tasks", "summary_generated_at")
    op.drop_column("tasks", "summary")
    op.drop_column("turns", "summary_generated_at")
    op.drop_column("turns", "summary")
