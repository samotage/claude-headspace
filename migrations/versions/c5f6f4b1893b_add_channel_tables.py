"""add channel tables — Channel, ChannelMembership, Message, Turn.source_message_id

Revision ID: c5f6f4b1893b
Revises: ed3c7ae48539
Create Date: 2026-03-03 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c5f6f4b1893b'
down_revision = 'ed3c7ae48539'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Create channels table (channeltype enum auto-created by sa.Enum)
    op.create_table(
        'channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('slug', sa.String(128), nullable=False),
        sa.Column('channel_type', sa.Enum(
            'workshop', 'delegation', 'review', 'standup', 'broadcast',
            name='channeltype'
        ), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('intent_override', sa.Text(), nullable=True),
        sa.Column('organisation_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('created_by_persona_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_persona_id'], ['personas.id'],
                                ondelete='SET NULL'),
    )

    # Step 2: Create channel_memberships table with uq_channel_persona constraint
    op.create_table(
        'channel_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('persona_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('position_assignment_id', sa.Integer(), nullable=True),
        sa.Column('is_chair', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'],
                                ondelete='SET NULL'),
        sa.UniqueConstraint('channel_id', 'persona_id', name='uq_channel_persona'),
    )
    op.create_index('ix_channel_memberships_channel_id', 'channel_memberships', ['channel_id'])
    op.create_index('ix_channel_memberships_persona_id', 'channel_memberships', ['persona_id'])
    op.create_index('ix_channel_memberships_agent_id', 'channel_memberships', ['agent_id'])

    # Step 3: Create partial unique index for one-agent-one-channel enforcement
    op.execute(
        "CREATE UNIQUE INDEX uq_active_agent_one_channel "
        "ON channel_memberships (agent_id) "
        "WHERE status = 'active' AND agent_id IS NOT NULL"
    )

    # Step 4: Create messages table (messagetype enum auto-created by sa.Enum)
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('persona_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', sa.Enum(
            'message', 'system', 'delegation', 'escalation',
            name='messagetype'
        ), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('attachment_path', sa.String(1024), nullable=True),
        sa.Column('source_turn_id', sa.Integer(), nullable=True),
        sa.Column('source_command_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_turn_id'], ['turns.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_command_id'], ['commands.id'],
                                ondelete='SET NULL'),
    )
    op.create_index('ix_messages_channel_id', 'messages', ['channel_id'])
    op.create_index('ix_messages_persona_id', 'messages', ['persona_id'])
    op.create_index('ix_messages_agent_id', 'messages', ['agent_id'])

    # Step 5: Add source_message_id FK to turns table
    op.add_column('turns', sa.Column('source_message_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_turns_source_message_id',
        'turns',
        'messages',
        ['source_message_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    # Step 1: Drop source_message_id from turns
    op.drop_constraint('fk_turns_source_message_id', 'turns', type_='foreignkey')
    op.drop_column('turns', 'source_message_id')

    # Step 2: Drop messages table
    op.drop_index('ix_messages_agent_id', table_name='messages')
    op.drop_index('ix_messages_persona_id', table_name='messages')
    op.drop_index('ix_messages_channel_id', table_name='messages')
    op.drop_table('messages')

    # Step 3: Drop partial unique index
    op.execute("DROP INDEX IF EXISTS uq_active_agent_one_channel")

    # Step 4: Drop channel_memberships table
    op.drop_index('ix_channel_memberships_agent_id', table_name='channel_memberships')
    op.drop_index('ix_channel_memberships_persona_id', table_name='channel_memberships')
    op.drop_index('ix_channel_memberships_channel_id', table_name='channel_memberships')
    op.drop_table('channel_memberships')

    # Step 5: Drop channels table
    op.drop_table('channels')

    # Step 6: Drop enums
    sa.Enum(name='messagetype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='channeltype').drop(op.get_bind(), checkfirst=True)
