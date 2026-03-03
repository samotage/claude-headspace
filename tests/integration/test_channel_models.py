"""Integration tests for Channel, ChannelMembership, and Message models.

Verifies real Postgres constraints and behavior:
- Channel creation, slug auto-generation, ChannelType enum
- ChannelMembership creation, unique constraint, partial unique index
- Message creation, immutability (no edit/delete columns), MessageType enum
- Turn.source_message_id FK addition
- Cascade delete and SET NULL ondelete behaviours
- Relationship navigation
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from claude_headspace.models import (
    Agent,
    Channel,
    ChannelMembership,
    ChannelType,
    Command,
    CommandState,
    Message,
    MessageType,
    Organisation,
    Persona,
    PersonaType,
    Project,
    Role,
    Turn,
    TurnActor,
    TurnIntent,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def test_project(db_session):
    """Create a test Project."""
    project = Project(name="test-project", slug="test-project-ch", path="/tmp/test-project-ch")
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def test_organisation(db_session):
    """Create a test Organisation."""
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_persona_type(db_session):
    """Get or create a PersonaType (agent/internal)."""
    # Query for existing first (may exist from create_all or prior test)
    pt = db_session.query(PersonaType).filter_by(
        type_key="agent", subtype="internal"
    ).first()
    if pt is None:
        pt = PersonaType(type_key="agent", subtype="internal")
        db_session.add(pt)
        db_session.flush()
    return pt


@pytest.fixture
def test_role(db_session):
    """Create a test Role with a unique name."""
    role = Role(name=f"developer-{uuid4().hex[:8]}")
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def test_persona(db_session, test_role, test_persona_type):
    """Create a test Persona."""
    persona = Persona(name="TestAgent", role=test_role, persona_type=test_persona_type)
    db_session.add(persona)
    db_session.flush()
    return persona


@pytest.fixture
def test_persona_2(db_session, test_role, test_persona_type):
    """Create a second test Persona."""
    persona = Persona(name="TestAgent2", role=test_role, persona_type=test_persona_type)
    db_session.add(persona)
    db_session.flush()
    return persona


def _make_agent(db_session, project, **kwargs):
    """Helper to create an Agent with required fields."""
    agent = Agent(session_uuid=uuid4(), project_id=project.id, **kwargs)
    db_session.add(agent)
    db_session.flush()
    return agent


@pytest.fixture
def test_agent(db_session, test_project):
    """Create a test Agent."""
    return _make_agent(db_session, test_project)


@pytest.fixture
def test_channel(db_session, test_persona):
    """Create a test Channel."""
    channel = Channel(
        name="Test Workshop",
        channel_type=ChannelType.WORKSHOP,
        created_by_persona_id=test_persona.id,
    )
    db_session.add(channel)
    db_session.flush()
    return channel


# ── 3.1 Model Tests ──────────────────────────────────────────────────────────


class TestChannelCreation:
    """Test Channel creation with all fields and defaults."""

    def test_create_channel_all_fields(
        self, db_session, test_organisation, test_project, test_persona
    ):
        """Channel can be created with all fields populated."""
        channel = Channel(
            name="Alignment Workshop",
            channel_type=ChannelType.WORKSHOP,
            description="Persona alignment discussion",
            intent_override="Custom intent for this channel",
            organisation_id=test_organisation.id,
            project_id=test_project.id,
            created_by_persona_id=test_persona.id,
            status="active",
        )
        db_session.add(channel)
        db_session.flush()

        assert channel.id is not None
        assert channel.name == "Alignment Workshop"
        assert channel.channel_type == ChannelType.WORKSHOP
        assert channel.description == "Persona alignment discussion"
        assert channel.intent_override == "Custom intent for this channel"
        assert channel.organisation_id == test_organisation.id
        assert channel.project_id == test_project.id
        assert channel.created_by_persona_id == test_persona.id
        assert channel.status == "active"
        assert channel.created_at is not None
        assert channel.created_at.tzinfo is not None
        assert channel.completed_at is None
        assert channel.archived_at is None

    def test_create_channel_minimal_fields(self, db_session):
        """Channel can be created with only required fields."""
        channel = Channel(
            name="Minimal Channel",
            channel_type=ChannelType.DELEGATION,
        )
        db_session.add(channel)
        db_session.flush()

        assert channel.id is not None
        assert channel.status == "pending"
        assert channel.organisation_id is None
        assert channel.project_id is None
        assert channel.created_by_persona_id is None

    def test_channel_slug_auto_generation(self, db_session):
        """Channel slug is auto-generated as {channel_type}-{name}-{id}."""
        channel = Channel(
            name="Persona Alignment",
            channel_type=ChannelType.WORKSHOP,
        )
        db_session.add(channel)
        db_session.flush()

        expected_slug = f"workshop-persona-alignment-{channel.id}"
        assert channel.slug == expected_slug

    def test_channel_slug_special_characters(self, db_session):
        """Channel slug sanitizes special characters."""
        channel = Channel(
            name="Test & Review #1",
            channel_type=ChannelType.REVIEW,
        )
        db_session.add(channel)
        db_session.flush()

        expected_slug = f"review-test-review-1-{channel.id}"
        assert channel.slug == expected_slug

    def test_channel_slug_uniqueness(self, db_session):
        """Two channels with the same name get different slugs (due to different IDs)."""
        ch1 = Channel(name="Same Name", channel_type=ChannelType.STANDUP)
        ch2 = Channel(name="Same Name", channel_type=ChannelType.STANDUP)
        db_session.add(ch1)
        db_session.flush()
        db_session.add(ch2)
        db_session.flush()

        assert ch1.slug != ch2.slug
        assert ch1.id != ch2.id

    def test_channel_all_types(self, db_session):
        """All 5 ChannelType values can be used."""
        for ct in ChannelType:
            channel = Channel(name=f"Channel-{ct.value}", channel_type=ct)
            db_session.add(channel)
            db_session.flush()
            assert channel.channel_type == ct

    def test_channel_repr(self, db_session):
        """Channel has a meaningful __repr__."""
        channel = Channel(name="Repr Test", channel_type=ChannelType.BROADCAST)
        db_session.add(channel)
        db_session.flush()

        r = repr(channel)
        assert "Channel" in r
        assert str(channel.id) in r
        assert "broadcast" in r


class TestChannelMembershipCreation:
    """Test ChannelMembership creation and constraints."""

    def test_create_membership_all_fields(
        self, db_session, test_channel, test_persona, test_agent
    ):
        """ChannelMembership can be created with all fields."""
        membership = ChannelMembership(
            channel_id=test_channel.id,
            persona_id=test_persona.id,
            agent_id=test_agent.id,
            is_chair=True,
            status="active",
        )
        db_session.add(membership)
        db_session.flush()

        assert membership.id is not None
        assert membership.channel_id == test_channel.id
        assert membership.persona_id == test_persona.id
        assert membership.agent_id == test_agent.id
        assert membership.is_chair is True
        assert membership.status == "active"
        assert membership.joined_at is not None
        assert membership.joined_at.tzinfo is not None
        assert membership.left_at is None
        assert membership.position_assignment_id is None

    def test_create_membership_minimal(self, db_session, test_channel, test_persona):
        """ChannelMembership can be created with only required fields."""
        membership = ChannelMembership(
            channel_id=test_channel.id,
            persona_id=test_persona.id,
        )
        db_session.add(membership)
        db_session.flush()

        assert membership.is_chair is False
        assert membership.status == "active"
        assert membership.agent_id is None

    def test_membership_unique_constraint(
        self, db_session, test_channel, test_persona
    ):
        """Duplicate (channel_id, persona_id) raises IntegrityError."""
        m1 = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(m1)
        db_session.flush()

        m2 = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(m2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_membership_repr(self, db_session, test_channel, test_persona):
        """ChannelMembership has a meaningful __repr__."""
        membership = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(membership)
        db_session.flush()

        r = repr(membership)
        assert "ChannelMembership" in r
        assert str(membership.id) in r


class TestMessageCreation:
    """Test Message creation and immutability."""

    def test_create_message_all_fields(
        self, db_session, test_channel, test_persona, test_agent
    ):
        """Message can be created with all fields."""
        # Create a command and turn for source references
        command = Command(agent_id=test_agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Some agent output",
        )
        db_session.add(turn)
        db_session.flush()

        message = Message(
            channel_id=test_channel.id,
            persona_id=test_persona.id,
            agent_id=test_agent.id,
            content="Hello from the workshop",
            message_type=MessageType.MESSAGE,
            metadata_={"key": "value"},
            attachment_path="/uploads/test.md",
            source_turn_id=turn.id,
            source_command_id=command.id,
        )
        db_session.add(message)
        db_session.flush()

        assert message.id is not None
        assert message.channel_id == test_channel.id
        assert message.persona_id == test_persona.id
        assert message.agent_id == test_agent.id
        assert message.content == "Hello from the workshop"
        assert message.message_type == MessageType.MESSAGE
        assert message.metadata_ == {"key": "value"}
        assert message.attachment_path == "/uploads/test.md"
        assert message.source_turn_id == turn.id
        assert message.source_command_id == command.id
        assert message.sent_at is not None
        assert message.sent_at.tzinfo is not None

    def test_create_message_minimal(self, db_session, test_channel):
        """Message can be created with only required fields."""
        message = Message(
            channel_id=test_channel.id,
            content="System notification",
            message_type=MessageType.SYSTEM,
        )
        db_session.add(message)
        db_session.flush()

        assert message.id is not None
        assert message.persona_id is None
        assert message.agent_id is None
        assert message.metadata_ is None

    def test_message_immutability_no_edit_columns(self):
        """Message model has no edit/delete lifecycle columns (structural immutability)."""
        column_names = [c.name for c in Message.__table__.columns]
        assert "edited_at" not in column_names
        assert "deleted_at" not in column_names
        assert "updated_at" not in column_names

    def test_message_all_types(self, db_session, test_channel):
        """All 4 MessageType values can be used."""
        for mt in MessageType:
            message = Message(
                channel_id=test_channel.id,
                content=f"Content for {mt.value}",
                message_type=mt,
            )
            db_session.add(message)
            db_session.flush()
            assert message.message_type == mt

    def test_message_repr(self, db_session, test_channel):
        """Message has a meaningful __repr__."""
        message = Message(
            channel_id=test_channel.id,
            content="Repr test",
            message_type=MessageType.DELEGATION,
        )
        db_session.add(message)
        db_session.flush()

        r = repr(message)
        assert "Message" in r
        assert str(message.id) in r
        assert "delegation" in r


class TestTurnSourceMessageId:
    """Test Turn.source_message_id FK addition."""

    def test_turn_source_message_id_column_exists(self):
        """Turn model has source_message_id column."""
        column_names = [c.name for c in Turn.__table__.columns]
        assert "source_message_id" in column_names

    def test_turn_with_source_message(
        self, db_session, test_channel, test_project
    ):
        """Turn can reference a source Message via source_message_id."""
        agent = _make_agent(db_session, test_project)
        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        message = Message(
            channel_id=test_channel.id,
            content="Triggering message",
            message_type=MessageType.MESSAGE,
        )
        db_session.add(message)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Response to channel message",
            source_message_id=message.id,
        )
        db_session.add(turn)
        db_session.flush()

        assert turn.source_message_id == message.id
        assert turn.source_message is not None
        assert turn.source_message.id == message.id

    def test_turn_source_message_id_nullable(
        self, db_session, test_project
    ):
        """Turn.source_message_id is nullable (most turns have no source message)."""
        agent = _make_agent(db_session, test_project)
        command = Command(agent_id=agent.id, state=CommandState.IDLE)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Normal turn without message source",
        )
        db_session.add(turn)
        db_session.flush()

        assert turn.source_message_id is None
        assert turn.source_message is None


# ── 3.2 Enum Tests ───────────────────────────────────────────────────────────


class TestEnums:
    """Test ChannelType and MessageType enum completeness."""

    def test_channel_type_has_5_values(self):
        """ChannelType enum has exactly 5 values."""
        assert len(ChannelType) == 5
        expected = {"workshop", "delegation", "review", "standup", "broadcast"}
        actual = {ct.value for ct in ChannelType}
        assert actual == expected

    def test_message_type_has_4_values(self):
        """MessageType enum has exactly 4 values."""
        assert len(MessageType) == 4
        expected = {"message", "system", "delegation", "escalation"}
        actual = {mt.value for mt in MessageType}
        assert actual == expected


# ── 3.3 Relationship & Cascade Tests ─────────────────────────────────────────


class TestChannelCascadeDelete:
    """Test Channel deletion cascades to memberships and messages."""

    def test_channel_delete_cascades_memberships(
        self, db_session, test_channel, test_persona
    ):
        """Deleting a Channel cascades to delete all ChannelMembership records."""
        membership = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(membership)
        db_session.flush()

        membership_id = membership.id
        db_session.delete(test_channel)
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(ChannelMembership, membership_id)
        assert result is None

    def test_channel_delete_cascades_messages(
        self, db_session, test_channel
    ):
        """Deleting a Channel cascades to delete all Message records."""
        message = Message(
            channel_id=test_channel.id,
            content="Will be deleted",
            message_type=MessageType.MESSAGE,
        )
        db_session.add(message)
        db_session.flush()

        message_id = message.id
        db_session.delete(test_channel)
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(Message, message_id)
        assert result is None


class TestPersonaDeletionBehaviour:
    """Test Persona deletion cascades to memberships, SET NULL on messages."""

    def test_persona_delete_cascades_membership(
        self, db_session, test_channel, test_role, test_persona_type
    ):
        """Deleting a Persona cascades to delete their ChannelMembership records."""
        role2 = Role(name=f"disposable-role-{uuid4().hex[:8]}")
        db_session.add(role2)
        db_session.flush()

        persona = Persona(name="Disposable", role=role2, persona_type=test_persona_type)
        db_session.add(persona)
        db_session.flush()

        membership = ChannelMembership(
            channel_id=test_channel.id, persona_id=persona.id
        )
        db_session.add(membership)
        db_session.flush()

        membership_id = membership.id
        db_session.delete(persona)
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(ChannelMembership, membership_id)
        assert result is None

    def test_persona_delete_sets_null_on_message(
        self, db_session, test_channel, test_role, test_persona_type
    ):
        """Deleting a Persona sets Message.persona_id to NULL."""
        role2 = Role(name=f"msgsender-role-{uuid4().hex[:8]}")
        db_session.add(role2)
        db_session.flush()

        persona = Persona(name="MsgSender", role=role2, persona_type=test_persona_type)
        db_session.add(persona)
        db_session.flush()

        message = Message(
            channel_id=test_channel.id,
            persona_id=persona.id,
            content="Message from a persona",
            message_type=MessageType.MESSAGE,
        )
        db_session.add(message)
        db_session.flush()

        message_id = message.id
        db_session.delete(persona)
        db_session.flush()
        db_session.expire_all()

        # Message should still exist with persona_id = NULL
        result = db_session.get(Message, message_id)
        assert result is not None
        assert result.persona_id is None


class TestAgentDeletionBehaviour:
    """Test Agent deletion SET NULL on ChannelMembership.agent_id and Message.agent_id."""

    def test_agent_delete_sets_null_on_membership(
        self, db_session, test_channel, test_persona, test_project
    ):
        """Deleting an Agent sets ChannelMembership.agent_id to NULL."""
        agent = _make_agent(db_session, test_project)
        membership = ChannelMembership(
            channel_id=test_channel.id,
            persona_id=test_persona.id,
            agent_id=agent.id,
        )
        db_session.add(membership)
        db_session.flush()

        membership_id = membership.id
        db_session.delete(agent)
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(ChannelMembership, membership_id)
        assert result is not None
        assert result.agent_id is None

    def test_agent_delete_sets_null_on_message(
        self, db_session, test_channel, test_project
    ):
        """Deleting an Agent sets Message.agent_id to NULL."""
        agent = _make_agent(db_session, test_project)
        message = Message(
            channel_id=test_channel.id,
            agent_id=agent.id,
            content="Message from agent",
            message_type=MessageType.MESSAGE,
        )
        db_session.add(message)
        db_session.flush()

        message_id = message.id
        db_session.delete(agent)
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(Message, message_id)
        assert result is not None
        assert result.agent_id is None


class TestPartialUniqueIndex:
    """Test partial unique index uq_active_agent_one_channel."""

    def test_prevents_duplicate_active_agent(
        self, db_session, test_persona, test_persona_2, test_project
    ):
        """An agent cannot be active in two channels simultaneously."""
        agent = _make_agent(db_session, test_project)

        ch1 = Channel(name="Channel 1", channel_type=ChannelType.WORKSHOP)
        ch2 = Channel(name="Channel 2", channel_type=ChannelType.DELEGATION)
        db_session.add_all([ch1, ch2])
        db_session.flush()

        m1 = ChannelMembership(
            channel_id=ch1.id,
            persona_id=test_persona.id,
            agent_id=agent.id,
            status="active",
        )
        db_session.add(m1)
        db_session.flush()

        m2 = ChannelMembership(
            channel_id=ch2.id,
            persona_id=test_persona_2.id,
            agent_id=agent.id,
            status="active",
        )
        db_session.add(m2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_allows_null_agent_id(
        self, db_session, test_persona, test_persona_2
    ):
        """Multiple memberships with NULL agent_id are allowed."""
        ch1 = Channel(name="Ch1", channel_type=ChannelType.STANDUP)
        ch2 = Channel(name="Ch2", channel_type=ChannelType.STANDUP)
        db_session.add_all([ch1, ch2])
        db_session.flush()

        m1 = ChannelMembership(
            channel_id=ch1.id, persona_id=test_persona.id, agent_id=None, status="active"
        )
        m2 = ChannelMembership(
            channel_id=ch2.id, persona_id=test_persona_2.id, agent_id=None, status="active"
        )
        db_session.add_all([m1, m2])
        db_session.flush()

        assert m1.id is not None
        assert m2.id is not None

    def test_allows_same_agent_when_not_active(
        self, db_session, test_persona, test_persona_2, test_project
    ):
        """Same agent_id allowed in multiple channels when status != 'active'."""
        agent = _make_agent(db_session, test_project)

        ch1 = Channel(name="Ch1-left", channel_type=ChannelType.REVIEW)
        ch2 = Channel(name="Ch2-left", channel_type=ChannelType.REVIEW)
        db_session.add_all([ch1, ch2])
        db_session.flush()

        m1 = ChannelMembership(
            channel_id=ch1.id,
            persona_id=test_persona.id,
            agent_id=agent.id,
            status="left",
        )
        m2 = ChannelMembership(
            channel_id=ch2.id,
            persona_id=test_persona_2.id,
            agent_id=agent.id,
            status="left",
        )
        db_session.add_all([m1, m2])
        db_session.flush()

        assert m1.id is not None
        assert m2.id is not None

    def test_allows_active_plus_non_active_same_agent(
        self, db_session, test_persona, test_persona_2, test_project
    ):
        """One active + one non-active membership for the same agent is allowed."""
        agent = _make_agent(db_session, test_project)

        ch1 = Channel(name="Active Ch", channel_type=ChannelType.WORKSHOP)
        ch2 = Channel(name="Left Ch", channel_type=ChannelType.WORKSHOP)
        db_session.add_all([ch1, ch2])
        db_session.flush()

        m1 = ChannelMembership(
            channel_id=ch1.id,
            persona_id=test_persona.id,
            agent_id=agent.id,
            status="active",
        )
        m2 = ChannelMembership(
            channel_id=ch2.id,
            persona_id=test_persona_2.id,
            agent_id=agent.id,
            status="left",
        )
        db_session.add_all([m1, m2])
        db_session.flush()

        assert m1.id is not None
        assert m2.id is not None


class TestMessageTurnSourceSetNull:
    """Test source_turn_id and source_message_id SET NULL on delete."""

    def test_turn_delete_sets_null_on_message_source_turn(
        self, db_session, test_channel, test_project
    ):
        """Deleting a Turn sets Message.source_turn_id to NULL."""
        agent = _make_agent(db_session, test_project)
        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Source turn",
        )
        db_session.add(turn)
        db_session.flush()

        message = Message(
            channel_id=test_channel.id,
            content="Message with source turn",
            message_type=MessageType.MESSAGE,
            source_turn_id=turn.id,
        )
        db_session.add(message)
        db_session.flush()

        message_id = message.id

        # Delete the turn via raw SQL to avoid ORM cascade from Command
        db_session.execute(
            text("DELETE FROM turns WHERE id = :tid"), {"tid": turn.id}
        )
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(Message, message_id)
        assert result is not None
        assert result.source_turn_id is None

    def test_message_delete_sets_null_on_turn_source_message(
        self, db_session, test_channel, test_project
    ):
        """Deleting a Message sets Turn.source_message_id to NULL."""
        agent = _make_agent(db_session, test_project)
        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        message = Message(
            channel_id=test_channel.id,
            content="Will be deleted",
            message_type=MessageType.MESSAGE,
        )
        db_session.add(message)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Has source message",
            source_message_id=message.id,
        )
        db_session.add(turn)
        db_session.flush()

        turn_id = turn.id
        db_session.execute(
            text("DELETE FROM messages WHERE id = :mid"), {"mid": message.id}
        )
        db_session.flush()
        db_session.expire_all()

        result = db_session.get(Turn, turn_id)
        assert result is not None
        assert result.source_message_id is None


class TestRelationshipNavigation:
    """Test bidirectional relationship navigation."""

    def test_channel_memberships_relationship(
        self, db_session, test_channel, test_persona
    ):
        """Channel.memberships navigates to ChannelMembership list."""
        membership = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(membership)
        db_session.flush()

        assert len(test_channel.memberships) == 1
        assert test_channel.memberships[0].id == membership.id

    def test_channel_messages_relationship(
        self, db_session, test_channel
    ):
        """Channel.messages navigates to Message list."""
        msg = Message(
            channel_id=test_channel.id,
            content="Test message",
            message_type=MessageType.MESSAGE,
        )
        db_session.add(msg)
        db_session.flush()

        assert len(test_channel.messages) == 1
        assert test_channel.messages[0].id == msg.id

    def test_channel_organisation_relationship(
        self, db_session, test_organisation
    ):
        """Channel.organisation navigates to Organisation."""
        channel = Channel(
            name="Org Channel",
            channel_type=ChannelType.STANDUP,
            organisation_id=test_organisation.id,
        )
        db_session.add(channel)
        db_session.flush()

        assert channel.organisation is not None
        assert channel.organisation.id == test_organisation.id

    def test_channel_project_relationship(
        self, db_session, test_project
    ):
        """Channel.project navigates to Project."""
        channel = Channel(
            name="Project Channel",
            channel_type=ChannelType.REVIEW,
            project_id=test_project.id,
        )
        db_session.add(channel)
        db_session.flush()

        assert channel.project is not None
        assert channel.project.id == test_project.id

    def test_channel_created_by_persona_relationship(
        self, db_session, test_persona
    ):
        """Channel.created_by_persona navigates to Persona."""
        channel = Channel(
            name="Persona Channel",
            channel_type=ChannelType.WORKSHOP,
            created_by_persona_id=test_persona.id,
        )
        db_session.add(channel)
        db_session.flush()

        assert channel.created_by_persona is not None
        assert channel.created_by_persona.id == test_persona.id

    def test_membership_channel_relationship(
        self, db_session, test_channel, test_persona
    ):
        """ChannelMembership.channel navigates to Channel."""
        membership = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(membership)
        db_session.flush()

        assert membership.channel is not None
        assert membership.channel.id == test_channel.id

    def test_membership_persona_relationship(
        self, db_session, test_channel, test_persona
    ):
        """ChannelMembership.persona navigates to Persona."""
        membership = ChannelMembership(
            channel_id=test_channel.id, persona_id=test_persona.id
        )
        db_session.add(membership)
        db_session.flush()

        assert membership.persona is not None
        assert membership.persona.id == test_persona.id

    def test_membership_agent_relationship(
        self, db_session, test_channel, test_persona, test_agent
    ):
        """ChannelMembership.agent navigates to Agent."""
        membership = ChannelMembership(
            channel_id=test_channel.id,
            persona_id=test_persona.id,
            agent_id=test_agent.id,
        )
        db_session.add(membership)
        db_session.flush()

        assert membership.agent is not None
        assert membership.agent.id == test_agent.id

    def test_message_channel_relationship(
        self, db_session, test_channel
    ):
        """Message.channel navigates to Channel."""
        msg = Message(
            channel_id=test_channel.id,
            content="Relationship test",
            message_type=MessageType.SYSTEM,
        )
        db_session.add(msg)
        db_session.flush()

        assert msg.channel is not None
        assert msg.channel.id == test_channel.id

    def test_message_source_turn_relationship(
        self, db_session, test_channel, test_project
    ):
        """Message.source_turn navigates to Turn."""
        agent = _make_agent(db_session, test_project)
        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Source turn for message",
        )
        db_session.add(turn)
        db_session.flush()

        msg = Message(
            channel_id=test_channel.id,
            content="Has source turn",
            message_type=MessageType.MESSAGE,
            source_turn_id=turn.id,
        )
        db_session.add(msg)
        db_session.flush()

        assert msg.source_turn is not None
        assert msg.source_turn.id == turn.id

    def test_message_source_command_relationship(
        self, db_session, test_channel, test_project
    ):
        """Message.source_command navigates to Command."""
        agent = _make_agent(db_session, test_project)
        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        msg = Message(
            channel_id=test_channel.id,
            content="Has source command",
            message_type=MessageType.DELEGATION,
            source_command_id=command.id,
        )
        db_session.add(msg)
        db_session.flush()

        assert msg.source_command is not None
        assert msg.source_command.id == command.id
