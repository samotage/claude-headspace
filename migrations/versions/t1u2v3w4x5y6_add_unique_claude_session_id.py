"""add unique index on agents.claude_session_id

Revision ID: t1u2v3w4x5y6
Revises: 6cf902e48472
Create Date: 2026-02-07 00:10:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 't1u2v3w4x5y6'
down_revision = '6cf902e48472'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_agents_claude_session_id_unique',
        'agents',
        ['claude_session_id'],
        unique=True,
        postgresql_where='claude_session_id IS NOT NULL',
    )


def downgrade():
    op.drop_index('ix_agents_claude_session_id_unique', table_name='agents')
