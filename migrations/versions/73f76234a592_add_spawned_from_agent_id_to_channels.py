"""add spawned_from_agent_id to channels

Revision ID: 73f76234a592
Revises: d4e5f6a7b8c9
Create Date: 2026-03-06 10:27:08.692029

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '73f76234a592'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('channels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('spawned_from_agent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_channels_spawned_from_agent_id',
            'agents',
            ['spawned_from_agent_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('channels', schema=None) as batch_op:
        batch_op.drop_constraint('fk_channels_spawned_from_agent_id', type_='foreignkey')
        batch_op.drop_column('spawned_from_agent_id')
