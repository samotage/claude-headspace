"""add end_of_task to turnintent enum

Revision ID: a5b6c7d8e9f0
Revises: 4347b8a64a91
Create Date: 2026-02-01 18:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a5b6c7d8e9f0'
down_revision = '4347b8a64a91'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE turnintent ADD VALUE IF NOT EXISTS 'end_of_task'")


def downgrade():
    # PostgreSQL does not support removing enum values directly.
    # A full enum recreation would be needed, which is destructive.
    # This downgrade is intentionally left as a no-op.
    pass
