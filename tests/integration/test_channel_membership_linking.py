"""Integration tests for agent-to-membership linking on session start (FR14, FR14a)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.channel import Channel, ChannelType
from claude_headspace.models.channel_membership import ChannelMembership
from claude_headspace.models.message import Message, MessageType
from claude_headspace.models.persona import Persona
from claude_headspace.models.persona_type import PersonaType
from claude_headspace.models.project import Project
from claude_headspace.models.role import Role
from claude_headspace.services.hook_receiver import process_session_start


@pytest.fixture
def db_session(app):
    """Provide a database session with cleanup."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def setup_data(app, db_session):
    """Create test data with a pending membership (agent_id=NULL)."""
    role = Role(name="developer")
    db_session.add(role)
    db_session.flush()

    pt_internal = db_session.get(PersonaType, 1)

    # Creator persona with agent
    creator_persona = Persona(
        name="Creator",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    # Target persona (will get a new agent via session-start)
    target_persona = Persona(
        name="Target",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    db_session.add_all([creator_persona, target_persona])
    db_session.flush()

    project = Project(name="test-project", slug="test-project", path="/tmp/test")
    db_session.add(project)
    db_session.flush()

    # Creator's agent
    creator_agent = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=creator_persona.id,
    )
    db_session.add(creator_agent)
    db_session.flush()

    # Channel
    channel = Channel(
        name="link-test",
        channel_type=ChannelType.WORKSHOP,
        created_by_persona_id=creator_persona.id,
        status="active",
    )
    db_session.add(channel)
    db_session.flush()

    # Creator membership
    creator_membership = ChannelMembership(
        channel_id=channel.id,
        persona_id=creator_persona.id,
        agent_id=creator_agent.id,
        is_chair=True,
        status="active",
    )
    # Target membership with NULL agent_id (pending from add_member spin-up)
    target_membership = ChannelMembership(
        channel_id=channel.id,
        persona_id=target_persona.id,
        agent_id=None,
        is_chair=False,
        status="active",
    )
    db_session.add_all([creator_membership, target_membership])

    # Add a message so context briefing has content
    msg = Message(
        channel_id=channel.id,
        persona_id=creator_persona.id,
        agent_id=creator_agent.id,
        content="Welcome to the channel!",
        message_type=MessageType.MESSAGE,
    )
    db_session.add(msg)
    db_session.commit()

    # Refresh slugs
    db_session.refresh(creator_persona)
    db_session.refresh(target_persona)
    db_session.refresh(channel)

    yield {
        "creator_persona": creator_persona,
        "target_persona": target_persona,
        "creator_agent": creator_agent,
        "channel": channel,
        "target_membership": target_membership,
        "project": project,
    }


class TestAgentMembershipLinking:
    """Test FR14: agent_id updated on session start."""

    @patch("claude_headspace.services.hook_receiver.broadcast_card_refresh")
    def test_links_agent_to_pending_membership(self, mock_broadcast, app, setup_data):
        """Agent registration links to pending ChannelMembership."""
        target_membership_id = setup_data["target_membership"].id

        with app.app_context():
            # Create a new agent for the target persona
            new_agent = Agent(
                session_uuid=uuid4(),
                project_id=setup_data["project"].id,
                persona_id=setup_data["target_persona"].id,
                tmux_pane_id="%42",
            )
            db.session.add(new_agent)
            db.session.commit()
            new_agent_id = new_agent.id

            # Process session start (this should link the agent)
            result = process_session_start(
                agent=new_agent,
                claude_session_id="test-session-123",
                persona_slug=setup_data["target_persona"].slug,
                tmux_pane_id="%42",
            )

            assert result.success

            # Re-query the membership (may have been committed in a different session scope)
            membership = db.session.get(ChannelMembership, target_membership_id)
            assert membership.agent_id == new_agent_id


class TestContextBriefingDelivery:
    """Test FR14a: context briefing delivered after linking."""

    @patch("claude_headspace.services.hook_receiver.broadcast_card_refresh")
    def test_context_briefing_delivered(self, mock_broadcast, app, setup_data):
        """Context briefing delivered via tmux after agent links to membership."""
        channel_id = setup_data["channel"].id

        with app.app_context():
            # Mock the channel service's context briefing delivery
            mock_channel_svc = MagicMock()
            app.extensions["channel_service"] = mock_channel_svc

            # Create a new agent for the target persona
            new_agent = Agent(
                session_uuid=uuid4(),
                project_id=setup_data["project"].id,
                persona_id=setup_data["target_persona"].id,
                tmux_pane_id="%42",
            )
            db.session.add(new_agent)
            db.session.commit()
            new_agent_id = new_agent.id

            # Process session start
            result = process_session_start(
                agent=new_agent,
                claude_session_id="test-session-456",
                persona_slug=setup_data["target_persona"].slug,
                tmux_pane_id="%42",
            )

            assert result.success

            # Check _deliver_context_briefing was called
            mock_channel_svc._deliver_context_briefing.assert_called_once()
            call_args = mock_channel_svc._deliver_context_briefing.call_args
            assert call_args[0][0].id == channel_id
            assert call_args[0][1].id == new_agent_id
