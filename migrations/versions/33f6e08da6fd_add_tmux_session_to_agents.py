"""add tmux_session to agents

Revision ID: 33f6e08da6fd
Revises: 4b52fbd01be0
Create Date: 2026-02-15 17:21:18.280466

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '33f6e08da6fd'
down_revision = '4b52fbd01be0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tmux_session', sa.String(length=128), nullable=True))


def downgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_column('tmux_session')
