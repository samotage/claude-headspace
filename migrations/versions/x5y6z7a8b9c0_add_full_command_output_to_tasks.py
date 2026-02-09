"""add full_command and full_output to tasks

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
Create Date: 2026-02-09 18:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'x5y6z7a8b9c0'
down_revision = 'w4x5y6z7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('full_command', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('full_output', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('tasks', 'full_output')
    op.drop_column('tasks', 'full_command')
