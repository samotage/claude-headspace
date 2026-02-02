"""add claude_session_id column to agents

Revision ID: b4c5d6e7f8a9
Revises: a3c924522879
Create Date: 2026-01-30 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4c5d6e7f8a9'
down_revision = 'a3c924522879'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('claude_session_id', sa.String(), nullable=True))
        batch_op.create_index('ix_agents_claude_session_id', ['claude_session_id'])


def downgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_index('ix_agents_claude_session_id')
        batch_op.drop_column('claude_session_id')
