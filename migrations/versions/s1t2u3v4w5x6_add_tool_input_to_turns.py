"""Add tool_input JSONB column to turns.

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-02-06

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("turns", sa.Column("tool_input", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("turns", "tool_input")
