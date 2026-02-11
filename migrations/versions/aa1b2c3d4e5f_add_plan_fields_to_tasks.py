"""add plan fields to tasks

Revision ID: aa1b2c3d4e5f
Revises: z7a8b9c0d1e2
Create Date: 2026-02-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'aa1b2c3d4e5f'
down_revision = 'z7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('plan_file_path', sa.String(length=1024), nullable=True))
    op.add_column('tasks', sa.Column('plan_content', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('plan_approved_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('tasks', 'plan_approved_at')
    op.drop_column('tasks', 'plan_content')
    op.drop_column('tasks', 'plan_file_path')
