"""Add persona_id, position_id, previous_agent_id to agents table.

Revision ID: b5c9d3e6f7a8
Revises: a3b8c1d2e4f5
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "b5c9d3e6f7a8"
down_revision = "a3b8c1d2e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("persona_id", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("position_id", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("previous_agent_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_agents_persona_id", "agents", "personas",
        ["persona_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_agents_position_id", "agents", "positions",
        ["position_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_agents_previous_agent_id", "agents", "agents",
        ["previous_agent_id"], ["id"], ondelete="CASCADE"
    )


def downgrade():
    op.drop_constraint("fk_agents_previous_agent_id", "agents", type_="foreignkey")
    op.drop_constraint("fk_agents_position_id", "agents", type_="foreignkey")
    op.drop_constraint("fk_agents_persona_id", "agents", type_="foreignkey")
    op.drop_column("agents", "previous_agent_id")
    op.drop_column("agents", "position_id")
    op.drop_column("agents", "persona_id")
