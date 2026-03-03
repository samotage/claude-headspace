"""add min_frustration and sum_frustration_squared columns for candlestick chart

Revision ID: d4e5f6a7b8c9
Revises: c5f6f4b1893b
Create Date: 2026-03-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c5f6f4b1893b'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns
    op.add_column('activity_metrics', sa.Column('min_frustration', sa.Integer(), nullable=True))
    op.add_column('activity_metrics', sa.Column('sum_frustration_squared', sa.Integer(), nullable=True))

    # Backfill agent-level rows from Turn data
    op.execute("""
        UPDATE activity_metrics am
        SET min_frustration = sub.min_f,
            sum_frustration_squared = sub.sum_sq
        FROM (
            SELECT am2.id,
                   MIN(t.frustration_score) AS min_f,
                   SUM(t.frustration_score * t.frustration_score)::integer AS sum_sq
            FROM activity_metrics am2
            JOIN commands c ON c.agent_id = am2.agent_id
            JOIN turns t ON t.command_id = c.id
            WHERE am2.agent_id IS NOT NULL
              AND am2.total_frustration IS NOT NULL
              AND t.actor = 'USER'
              AND t.frustration_score IS NOT NULL
              AND t.timestamp >= am2.bucket_start
              AND t.timestamp < am2.bucket_start + INTERVAL '1 hour'
            GROUP BY am2.id
        ) sub
        WHERE am.id = sub.id
    """)

    # Backfill project-level rows from agent-level rows
    op.execute("""
        UPDATE activity_metrics am
        SET min_frustration = sub.min_f,
            sum_frustration_squared = sub.sum_sq
        FROM (
            SELECT am_proj.id,
                   MIN(am_agent.min_frustration) AS min_f,
                   SUM(am_agent.sum_frustration_squared)::integer AS sum_sq
            FROM activity_metrics am_proj
            JOIN agents a ON a.project_id = am_proj.project_id
            JOIN activity_metrics am_agent
              ON am_agent.agent_id = a.id
             AND am_agent.bucket_start = am_proj.bucket_start
             AND am_agent.min_frustration IS NOT NULL
            WHERE am_proj.project_id IS NOT NULL
              AND am_proj.agent_id IS NULL
              AND am_proj.total_frustration IS NOT NULL
            GROUP BY am_proj.id
        ) sub
        WHERE am.id = sub.id
    """)

    # Backfill overall rows from agent-level rows
    op.execute("""
        UPDATE activity_metrics am
        SET min_frustration = sub.min_f,
            sum_frustration_squared = sub.sum_sq
        FROM (
            SELECT am_overall.id,
                   MIN(am_agent.min_frustration) AS min_f,
                   SUM(am_agent.sum_frustration_squared)::integer AS sum_sq
            FROM activity_metrics am_overall
            JOIN activity_metrics am_agent
              ON am_agent.bucket_start = am_overall.bucket_start
             AND am_agent.agent_id IS NOT NULL
             AND am_agent.min_frustration IS NOT NULL
            WHERE am_overall.is_overall = true
              AND am_overall.total_frustration IS NOT NULL
            GROUP BY am_overall.id
        ) sub
        WHERE am.id = sub.id
    """)


def downgrade():
    op.drop_column('activity_metrics', 'sum_frustration_squared')
    op.drop_column('activity_metrics', 'min_frustration')
