"""Add frustration_rolling_3hr column to headspace_snapshots table.

Session-level rolling frustration average over configurable window (default 3 hours).

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-02-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "headspace_snapshots",
        sa.Column("frustration_rolling_3hr", sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_column("headspace_snapshots", "frustration_rolling_3hr")
