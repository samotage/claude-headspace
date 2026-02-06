"""add max_frustration_at to activity_metrics

Revision ID: 6cf902e48472
Revises: s1t2u3v4w5x6
Create Date: 2026-02-06 17:07:42.729519

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6cf902e48472'
down_revision = 's1t2u3v4w5x6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('activity_metrics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_frustration_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('activity_metrics', schema=None) as batch_op:
        batch_op.drop_column('max_frustration_at')
