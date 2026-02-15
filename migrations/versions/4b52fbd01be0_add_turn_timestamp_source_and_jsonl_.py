"""add turn timestamp_source and jsonl_entry_hash columns

Revision ID: 4b52fbd01be0
Revises: bb2c3d4e5f6g
Create Date: 2026-02-15 11:55:02.253375

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b52fbd01be0'
down_revision = 'bb2c3d4e5f6g'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('turns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timestamp_source', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('jsonl_entry_hash', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_turns_jsonl_entry_hash'), ['jsonl_entry_hash'], unique=False)


def downgrade():
    with op.batch_alter_table('turns', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_turns_jsonl_entry_hash'))
        batch_op.drop_column('jsonl_entry_hash')
        batch_op.drop_column('timestamp_source')
