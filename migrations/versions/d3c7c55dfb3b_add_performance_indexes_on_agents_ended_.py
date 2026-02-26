"""add performance indexes on agents ended_at and inference_calls

Revision ID: d3c7c55dfb3b
Revises: e8f9a0b1c2d3
Create Date: 2026-02-26 14:09:02.559218

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3c7c55dfb3b'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade():
    # agents.ended_at — the #1 hot filter: every dashboard load, reaper pass,
    # session correlator, and card_state check filters on ended_at IS NULL.
    # 14K+ seq scans reading 11M tuples without this index.
    op.create_index(
        'ix_agents_ended_at',
        'agents',
        ['ended_at'],
        unique=False,
    )

    # Partial index for the most common query: find active (non-ended) agents.
    # This is a tiny index covering only the ~7 active rows at any time.
    op.create_index(
        'ix_agents_active',
        'agents',
        ['project_id', 'last_seen_at'],
        unique=False,
        postgresql_where=sa.text('ended_at IS NULL'),
    )

    # inference_calls: 462 seq scans reading 3.3M tuples.
    # Queries filter by project + timestamp for cost/usage dashboards.
    op.create_index(
        'ix_inference_calls_project_timestamp',
        'inference_calls',
        ['project_id', 'timestamp'],
        unique=False,
    )

    # headspace_snapshots: queried by agent_id for monitor lookups.
    op.create_index(
        'ix_headspace_snapshots_agent_id',
        'headspace_snapshots',
        ['agent_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_headspace_snapshots_agent_id', table_name='headspace_snapshots')
    op.drop_index('ix_inference_calls_project_timestamp', table_name='inference_calls')
    op.drop_index('ix_agents_active', table_name='agents')
    op.drop_index('ix_agents_ended_at', table_name='agents')
