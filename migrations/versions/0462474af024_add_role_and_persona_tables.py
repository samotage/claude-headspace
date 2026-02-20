"""add role and persona tables

Revision ID: 0462474af024
Revises: a0b1c2d3e4f5
Create Date: 2026-02-20 17:35:20.921575

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0462474af024'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('personas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=128), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )


def downgrade():
    op.drop_table('personas')
    op.drop_table('roles')
