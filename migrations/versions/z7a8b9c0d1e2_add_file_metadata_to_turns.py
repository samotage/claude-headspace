"""add file_metadata JSONB column to turns

Revision ID: z7a8b9c0d1e2
Revises: y6z7a8b9c0d1
Create Date: 2026-02-11 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'z7a8b9c0d1e2'
down_revision = 'y6z7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('turns', sa.Column('file_metadata', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('turns', 'file_metadata')
