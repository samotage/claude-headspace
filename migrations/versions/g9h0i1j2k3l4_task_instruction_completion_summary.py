"""Add instruction fields and rename summary to completion_summary on tasks.

Revision ID: g9h0i1j2k3l4
Revises: f8a9b0c1d2e3
Create Date: 2026-02-01

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "g9h0i1j2k3l4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    # Rename summary -> completion_summary
    op.alter_column("tasks", "summary", new_column_name="completion_summary")
    op.alter_column("tasks", "summary_generated_at", new_column_name="completion_summary_generated_at")

    # Add instruction fields
    op.add_column("tasks", sa.Column("instruction", sa.Text(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("instruction_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    # Remove instruction fields
    op.drop_column("tasks", "instruction_generated_at")
    op.drop_column("tasks", "instruction")

    # Rename back
    op.alter_column("tasks", "completion_summary", new_column_name="summary")
    op.alter_column("tasks", "completion_summary_generated_at", new_column_name="summary_generated_at")
