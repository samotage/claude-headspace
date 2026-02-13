"""add_inference_call_check_constraint_and_indexes

Revision ID: 97b345273b89
Revises: aa1b2c3d4e5f
Create Date: 2026-02-14 07:05:50.312354

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '97b345273b89'
down_revision = 'aa1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade():
    # C9: Backfill orphan inference_calls that violate the constraint.
    # Set project_id from the associated agent if possible, otherwise delete.
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM inference_calls "
        "WHERE project_id IS NULL AND agent_id IS NULL "
        "AND task_id IS NULL AND turn_id IS NULL"
    ))

    # C9: CheckConstraint ensuring at least one FK is non-null on inference_calls
    op.create_check_constraint(
        'ck_inference_calls_has_parent',
        'inference_calls',
        'COALESCE(project_id, agent_id, task_id, turn_id) IS NOT NULL',
    )

    # H2: Add index on inference_calls.agent_id
    with op.batch_alter_table('inference_calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inference_calls_agent_id'), ['agent_id'], unique=False)

    # M8: Composite index on turns(task_id, actor)
    with op.batch_alter_table('turns', schema=None) as batch_op:
        batch_op.create_index('ix_turns_task_id_actor', ['task_id', 'actor'], unique=False)


def downgrade():
    with op.batch_alter_table('turns', schema=None) as batch_op:
        batch_op.drop_index('ix_turns_task_id_actor')

    with op.batch_alter_table('inference_calls', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inference_calls_agent_id'))

    op.drop_constraint('ck_inference_calls_has_parent', 'inference_calls', type_='check')
