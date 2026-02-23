"""Fix CASCADE to SET NULL on nullable foreign keys.

Persona_id on agents and self-referential FKs on positions are nullable,
meaning the absence of a reference is a valid state. CASCADE would
incorrectly delete the child record when the referenced row is removed.
SET NULL preserves the child record and clears the reference.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-02-23
"""

from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade():
    # agents.persona_id: CASCADE -> SET NULL
    op.drop_constraint("fk_agents_persona_id", "agents", type_="foreignkey")
    op.create_foreign_key(
        "fk_agents_persona_id", "agents", "personas",
        ["persona_id"], ["id"], ondelete="SET NULL"
    )

    # positions.reports_to_id: CASCADE -> SET NULL
    # (unnamed FK from create_table — drop by column reference)
    op.drop_constraint(
        "positions_reports_to_id_fkey", "positions", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_positions_reports_to_id", "positions", "positions",
        ["reports_to_id"], ["id"], ondelete="SET NULL"
    )

    # positions.escalates_to_id: CASCADE -> SET NULL
    op.drop_constraint(
        "positions_escalates_to_id_fkey", "positions", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_positions_escalates_to_id", "positions", "positions",
        ["escalates_to_id"], ["id"], ondelete="SET NULL"
    )


def downgrade():
    # Revert agents.persona_id back to CASCADE
    op.drop_constraint("fk_agents_persona_id", "agents", type_="foreignkey")
    op.create_foreign_key(
        "fk_agents_persona_id", "agents", "personas",
        ["persona_id"], ["id"], ondelete="CASCADE"
    )

    # Revert positions.reports_to_id back to CASCADE
    op.drop_constraint(
        "fk_positions_reports_to_id", "positions", type_="foreignkey"
    )
    op.create_foreign_key(
        "positions_reports_to_id_fkey", "positions", "positions",
        ["reports_to_id"], ["id"], ondelete="CASCADE"
    )

    # Revert positions.escalates_to_id back to CASCADE
    op.drop_constraint(
        "fk_positions_escalates_to_id", "positions", type_="foreignkey"
    )
    op.create_foreign_key(
        "positions_escalates_to_id_fkey", "positions", "positions",
        ["escalates_to_id"], ["id"], ondelete="CASCADE"
    )
