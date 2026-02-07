"""add scope CHECK constraint to activity_metrics

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-02-07 00:11:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'u2v3w4x5y6z7'
down_revision = 't1u2v3w4x5y6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE activity_metrics ADD CONSTRAINT ck_activity_metrics_scope "
        "CHECK ((agent_id IS NOT NULL)::int + (project_id IS NOT NULL)::int + is_overall::int = 1)"
    )


def downgrade():
    op.execute(
        "ALTER TABLE activity_metrics DROP CONSTRAINT ck_activity_metrics_scope"
    )
