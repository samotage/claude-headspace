"""add guardrails_version_hash to agents

Revision ID: 3e6ebf247ba1
Revises: d3c7c55dfb3b
Create Date: 2026-02-26 15:25:05.490772

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e6ebf247ba1'
down_revision = 'd3c7c55dfb3b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('guardrails_version_hash', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_column('guardrails_version_hash')
