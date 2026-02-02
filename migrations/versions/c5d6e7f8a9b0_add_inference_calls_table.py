"""Add inference_calls table for LLM call logging

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-01-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('inference_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('input_hash', sa.String(length=64), nullable=True),
        sa.Column('result_text', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('cached', sa.Boolean(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('turn_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['turn_id'], ['turns.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inference_calls_timestamp', 'inference_calls', ['timestamp'])
    op.create_index('ix_inference_calls_level', 'inference_calls', ['level'])
    op.create_index('ix_inference_calls_input_hash', 'inference_calls', ['input_hash'])
    op.create_index('ix_inference_calls_project_id', 'inference_calls', ['project_id'])
    op.create_index('ix_inference_calls_level_timestamp', 'inference_calls', ['level', 'timestamp'])
    op.create_index('ix_inference_calls_model_timestamp', 'inference_calls', ['model', 'timestamp'])


def downgrade():
    op.drop_index('ix_inference_calls_model_timestamp', table_name='inference_calls')
    op.drop_index('ix_inference_calls_level_timestamp', table_name='inference_calls')
    op.drop_index('ix_inference_calls_project_id', table_name='inference_calls')
    op.drop_index('ix_inference_calls_input_hash', table_name='inference_calls')
    op.drop_index('ix_inference_calls_level', table_name='inference_calls')
    op.drop_index('ix_inference_calls_timestamp', table_name='inference_calls')
    op.drop_table('inference_calls')
