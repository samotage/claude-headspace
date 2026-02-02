"""Add headspace monitoring: Turn.frustration_score + headspace_snapshots table.

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-02-02

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "k3l4m5n6o7p8"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade():
    # Add frustration_score column to turns table
    op.add_column("turns", sa.Column("frustration_score", sa.Integer(), nullable=True))

    # Create headspace_snapshots table
    op.create_table(
        "headspace_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frustration_rolling_10", sa.Float(), nullable=True),
        sa.Column("frustration_rolling_30min", sa.Float(), nullable=True),
        sa.Column("state", sa.String(10), nullable=False, server_default=sa.text("'green'")),
        sa.Column("turn_rate_per_hour", sa.Float(), nullable=True),
        sa.Column("is_flow_state", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("flow_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("last_alert_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_count_today", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_headspace_snapshots_timestamp", "headspace_snapshots", ["timestamp"])


def downgrade():
    op.drop_index("ix_headspace_snapshots_timestamp", table_name="headspace_snapshots")
    op.drop_table("headspace_snapshots")
    op.drop_column("turns", "frustration_score")
