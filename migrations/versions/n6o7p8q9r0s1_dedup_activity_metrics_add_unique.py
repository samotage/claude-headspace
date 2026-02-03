"""Deduplicate activity_metrics and add unique constraint.

Removes duplicate records (keeping the one with the highest turn_count)
and adds a unique index to prevent future duplicates. Uses COALESCE to
handle NULLable agent_id/project_id columns (PostgreSQL treats NULL != NULL
in unique constraints).

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-02-03

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "n6o7p8q9r0s1"
down_revision = "m5n6o7p8q9r0"
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Remove duplicates, keeping the row with highest turn_count per group
    op.execute("""
        DELETE FROM activity_metrics
        WHERE id NOT IN (
            SELECT DISTINCT ON (
                bucket_start,
                COALESCE(agent_id, -1),
                COALESCE(project_id, -1),
                is_overall
            ) id
            FROM activity_metrics
            ORDER BY
                bucket_start,
                COALESCE(agent_id, -1),
                COALESCE(project_id, -1),
                is_overall,
                turn_count DESC
        )
    """)

    # Step 2: Add unique functional index using COALESCE for nullable columns
    op.execute("""
        CREATE UNIQUE INDEX uq_activity_metrics_bucket_scope
        ON activity_metrics (
            bucket_start,
            COALESCE(agent_id, -1),
            COALESCE(project_id, -1),
            is_overall
        )
    """)


def downgrade():
    op.drop_index("uq_activity_metrics_bucket_scope", table_name="activity_metrics")
