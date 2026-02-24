"""add prompt_injected_at column to agents

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-02-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e8f9a0b1c2d3'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents', sa.Column('prompt_injected_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('agents', 'prompt_injected_at')
