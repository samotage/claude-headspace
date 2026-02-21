"""Add handoffs table.

Revision ID: c6d7e8f9a0b1
Revises: b5c9d3e6f7a8
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa

revision = "c6d7e8f9a0b1"
down_revision = "b5c9d3e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "handoffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("injection_prompt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("handoffs")
