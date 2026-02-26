"""add api_call_logs table

Revision ID: 9dbdc359da80
Revises: 3e6ebf247ba1
Create Date: 2026-02-27 09:14:06.046174

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9dbdc359da80'
down_revision = '3e6ebf247ba1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('api_call_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('http_method', sa.String(length=10), nullable=False),
    sa.Column('endpoint_path', sa.String(length=500), nullable=False),
    sa.Column('query_string', sa.Text(), nullable=True),
    sa.Column('request_content_type', sa.String(length=200), nullable=True),
    sa.Column('request_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('request_body', sa.Text(), nullable=True),
    sa.Column('response_status_code', sa.Integer(), nullable=False),
    sa.Column('response_content_type', sa.String(length=200), nullable=True),
    sa.Column('response_body', sa.Text(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('source_ip', sa.String(length=45), nullable=True),
    sa.Column('auth_status', sa.String(length=20), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('agent_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_call_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_call_logs_agent_id'), ['agent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_api_call_logs_auth_status'), ['auth_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_api_call_logs_endpoint_path'), ['endpoint_path'], unique=False)
        batch_op.create_index('ix_api_call_logs_endpoint_timestamp', ['endpoint_path', sa.text('timestamp DESC')], unique=False)
        batch_op.create_index(batch_op.f('ix_api_call_logs_http_method'), ['http_method'], unique=False)
        batch_op.create_index(batch_op.f('ix_api_call_logs_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_api_call_logs_response_status_code'), ['response_status_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_api_call_logs_timestamp'), ['timestamp'], unique=False)


def downgrade():
    with op.batch_alter_table('api_call_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_call_logs_timestamp'))
        batch_op.drop_index(batch_op.f('ix_api_call_logs_response_status_code'))
        batch_op.drop_index(batch_op.f('ix_api_call_logs_project_id'))
        batch_op.drop_index(batch_op.f('ix_api_call_logs_http_method'))
        batch_op.drop_index('ix_api_call_logs_endpoint_timestamp')
        batch_op.drop_index(batch_op.f('ix_api_call_logs_endpoint_path'))
        batch_op.drop_index(batch_op.f('ix_api_call_logs_auth_status'))
        batch_op.drop_index(batch_op.f('ix_api_call_logs_agent_id'))

    op.drop_table('api_call_logs')
