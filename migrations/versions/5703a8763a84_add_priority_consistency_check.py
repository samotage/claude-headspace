"""add_priority_consistency_check

Revision ID: 5703a8763a84
Revises: 0d9cd40eb8c8
Create Date: 2026-02-14 07:12:36.166991

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '5703a8763a84'
down_revision = '0d9cd40eb8c8'
branch_labels = None
depends_on = None


def upgrade():
    # L9: CheckConstraint ensuring priority fields are all-null or all-non-null
    op.create_check_constraint(
        'ck_agents_priority_consistency',
        'agents',
        "(priority_score IS NULL AND priority_reason IS NULL AND priority_updated_at IS NULL) OR "
        "(priority_score IS NOT NULL AND priority_reason IS NOT NULL AND priority_updated_at IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint('ck_agents_priority_consistency', 'agents', type_='check')
