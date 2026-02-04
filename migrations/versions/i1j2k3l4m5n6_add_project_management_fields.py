"""Add project management fields.

Revision ID: i1j2k3l4m5n6
Revises: h0i1j2k3l4m5
Create Date: 2026-02-02

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "i1j2k3l4m5n6"
down_revision = "h0i1j2k3l4m5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("inference_paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "projects",
        sa.Column("inference_paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("inference_paused_reason", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("projects", "inference_paused_reason")
    op.drop_column("projects", "inference_paused_at")
    op.drop_column("projects", "inference_paused")
    op.drop_column("projects", "description")
