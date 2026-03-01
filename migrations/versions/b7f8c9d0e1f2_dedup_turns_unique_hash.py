"""Deduplicate turns by jsonl_entry_hash and add partial unique constraint.

Removes duplicate Turn records sharing the same (command_id, jsonl_entry_hash)
— keeping the row with the lowest id (earliest created) — then adds a partial
unique index to prevent future duplicates.  The index is partial (WHERE
jsonl_entry_hash IS NOT NULL) because many turns have no hash (user turns,
notification-created turns, older turns) and PostgreSQL correctly treats
multiple NULLs as distinct.

Root cause: TOCTOU race in _capture_progress_text_impl allowed concurrent
hook requests (post_tool_use + pre_tool_use) to both create PROGRESS turns
from the same JSONL entry.

Revision ID: b7f8c9d0e1f2
Revises: 9dbdc359da80
Create Date: 2026-03-01
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7f8c9d0e1f2"
down_revision = "9dbdc359da80"
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Remove duplicates — keep the row with lowest id per group.
    op.execute("""
        DELETE FROM turns
        WHERE jsonl_entry_hash IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM turns
              WHERE jsonl_entry_hash IS NOT NULL
              GROUP BY command_id, jsonl_entry_hash
          )
    """)

    # Step 2: Add partial unique index.
    op.execute("""
        CREATE UNIQUE INDEX uq_turns_command_hash
        ON turns (command_id, jsonl_entry_hash)
        WHERE jsonl_entry_hash IS NOT NULL
    """)


def downgrade():
    op.drop_index("uq_turns_command_hash", table_name="turns")
