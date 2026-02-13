"""add_headspace_snapshot_fks_and_activity_metric_scope_check

Revision ID: 0d9cd40eb8c8
Revises: 97b345273b89
Create Date: 2026-02-14 07:09:31.766714

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d9cd40eb8c8'
down_revision = '97b345273b89'
branch_labels = None
depends_on = None


def upgrade():
    # H1: Add project_id and agent_id FKs to headspace_snapshots
    with op.batch_alter_table('headspace_snapshots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('agent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_headspace_snapshots_project_id', 'projects',
            ['project_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_foreign_key(
            'fk_headspace_snapshots_agent_id', 'agents',
            ['agent_id'], ['id'], ondelete='SET NULL',
        )

    # C10: CheckConstraint enforcing scope consistency on activity_metrics
    op.create_check_constraint(
        'ck_activity_metrics_scope_consistency',
        'activity_metrics',
        "(is_overall = true AND agent_id IS NULL AND project_id IS NULL) OR "
        "(is_overall = false AND agent_id IS NOT NULL AND project_id IS NULL) OR "
        "(is_overall = false AND project_id IS NOT NULL AND agent_id IS NULL)",
    )


def downgrade():
    op.drop_constraint('ck_activity_metrics_scope_consistency', 'activity_metrics', type_='check')

    with op.batch_alter_table('headspace_snapshots', schema=None) as batch_op:
        batch_op.drop_constraint('fk_headspace_snapshots_agent_id', type_='foreignkey')
        batch_op.drop_constraint('fk_headspace_snapshots_project_id', type_='foreignkey')
        batch_op.drop_column('agent_id')
        batch_op.drop_column('project_id')
