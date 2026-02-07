"""remove redundant created_at from headspace_snapshots

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-02-07 00:13:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'w4x5y6z7a8b9'
down_revision = 'v3w4x5y6z7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('headspace_snapshots', 'created_at')


def downgrade():
    op.add_column(
        'headspace_snapshots',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
