"""add position table

Revision ID: a3b8c1d2e4f5
Revises: 77a46a29dc5e
Create Date: 2026-02-20 19:27:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b8c1d2e4f5'
down_revision = '77a46a29dc5e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('reports_to_id', sa.Integer(), nullable=True),
        sa.Column('escalates_to_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('is_cross_cutting', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reports_to_id'], ['positions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['escalates_to_id'], ['positions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('positions')
