"""Create activity_metrics table.

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-02-02

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "j2k3l4m5n6o7"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_overall", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_turn_time_seconds", sa.Float(), nullable=True),
        sa.Column("active_agents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_activity_metrics_agent_bucket", "activity_metrics", ["agent_id", "bucket_start"])
    op.create_index("ix_activity_metrics_project_bucket", "activity_metrics", ["project_id", "bucket_start"])
    op.create_index("ix_activity_metrics_overall_bucket", "activity_metrics", ["is_overall", "bucket_start"])


def downgrade():
    op.drop_index("ix_activity_metrics_overall_bucket", table_name="activity_metrics")
    op.drop_index("ix_activity_metrics_project_bucket", table_name="activity_metrics")
    op.drop_index("ix_activity_metrics_agent_bucket", table_name="activity_metrics")
    op.drop_table("activity_metrics")
