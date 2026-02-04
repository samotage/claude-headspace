"""Add tmux_pane_id column to agents table.

Stores the tmux pane ID (e.g., %0, %5) for targeting send-keys commands.
Nullable field that coexists alongside iterm_pane_id.

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-02-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("tmux_pane_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "tmux_pane_id")
