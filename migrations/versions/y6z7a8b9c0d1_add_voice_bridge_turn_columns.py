"""add voice bridge columns to turns

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
Create Date: 2026-02-09 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'y6z7a8b9c0d1'
down_revision = 'x5y6z7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('turns', sa.Column('question_text', sa.Text(), nullable=True))
    op.add_column('turns', sa.Column('question_options', postgresql.JSONB(), nullable=True))
    op.add_column('turns', sa.Column('question_source_type', sa.String(30), nullable=True))
    op.add_column('turns', sa.Column('answered_by_turn_id', sa.Integer(), sa.ForeignKey('turns.id', ondelete='SET NULL'), nullable=True))


def downgrade():
    op.drop_column('turns', 'answered_by_turn_id')
    op.drop_column('turns', 'question_source_type')
    op.drop_column('turns', 'question_options')
    op.drop_column('turns', 'question_text')
