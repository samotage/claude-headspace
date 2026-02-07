"""add temporal CHECK constraints on tasks and agents

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-02-07 00:12:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'v3w4x5y6z7a8'
down_revision = 'u2v3w4x5y6z7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE tasks ADD CONSTRAINT ck_tasks_completed_after_started "
        "CHECK (completed_at >= started_at)"
    )
    op.execute(
        "ALTER TABLE agents ADD CONSTRAINT ck_agents_ended_after_started "
        "CHECK (ended_at >= started_at)"
    )


def downgrade():
    op.execute("ALTER TABLE agents DROP CONSTRAINT ck_agents_ended_after_started")
    op.execute("ALTER TABLE tasks DROP CONSTRAINT ck_tasks_completed_after_started")
