"""add organisation table

Revision ID: 77a46a29dc5e
Revises: 0462474af024
Create Date: 2026-02-20 17:47:51.933506

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77a46a29dc5e'
down_revision = '0462474af024'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('organisations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Seed data: one Development organisation
    op.execute(
        "INSERT INTO organisations (name, status, created_at) "
        "VALUES ('Development', 'active', NOW())"
    )


def downgrade():
    # Delete seed data before dropping the table
    op.execute("DELETE FROM organisations WHERE name = 'Development'")
    op.drop_table('organisations')
