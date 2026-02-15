"""add context columns to agents

Revision ID: bb2c3d4e5f6g
Revises: 5703a8763a84
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bb2c3d4e5f6g'
down_revision = '5703a8763a84'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents', sa.Column('context_percent_used', sa.Integer(), nullable=True))
    op.add_column('agents', sa.Column('context_remaining_tokens', sa.String(length=32), nullable=True))
    op.add_column('agents', sa.Column('context_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('agents', 'context_updated_at')
    op.drop_column('agents', 'context_remaining_tokens')
    op.drop_column('agents', 'context_percent_used')
