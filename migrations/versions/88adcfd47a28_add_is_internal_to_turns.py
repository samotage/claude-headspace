"""add is_internal to turns

Revision ID: 88adcfd47a28
Revises: 33f6e08da6fd
Create Date: 2026-02-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '88adcfd47a28'
down_revision = '33f6e08da6fd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('turns', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'is_internal', sa.Boolean(),
            nullable=False, server_default=sa.text('false'),
        ))


def downgrade():
    with op.batch_alter_table('turns', schema=None) as batch_op:
        batch_op.drop_column('is_internal')
