"""Make all datetime columns timezone-aware

Revision ID: a1b2c3d4e5f6
Revises: 5c4d4f13bcfb
Create Date: 2026-01-30 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '5c4d4f13bcfb'
branch_labels = None
depends_on = None

# All datetime columns that need to be converted from
# sa.DateTime() to sa.DateTime(timezone=True), which maps to
# PostgreSQL's TIMESTAMP WITH TIME ZONE.
COLUMNS_TO_ALTER = [
    ('objectives', 'set_at', False),
    ('projects', 'created_at', False),
    ('agents', 'started_at', False),
    ('agents', 'last_seen_at', False),
    ('objective_histories', 'started_at', False),
    ('objective_histories', 'ended_at', True),
    ('tasks', 'started_at', False),
    ('tasks', 'completed_at', True),
    ('turns', 'timestamp', False),
    ('events', 'timestamp', False),
]


def upgrade():
    # Add the ended_at column to agents (added in model but missing migration)
    op.add_column('agents', sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True))

    for table, column, nullable in COLUMNS_TO_ALTER:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade():
    for table, column, nullable in COLUMNS_TO_ALTER:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=nullable,
        )

    # Remove the ended_at column from agents
    op.drop_column('agents', 'ended_at')
