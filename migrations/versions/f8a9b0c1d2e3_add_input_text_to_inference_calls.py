"""Add input_text column to inference_calls table.

Revision ID: f8a9b0c1d2e3
Revises: a5b6c7d8e9f0
Create Date: 2026-02-01

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f8a9b0c1d2e3"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inference_calls", sa.Column("input_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("inference_calls", "input_text")
