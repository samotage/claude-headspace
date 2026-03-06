"""Tests for E9-S11 channel creation redesign — ChannelService additions.

Covers:
- create_channel_from_personas()
- link_agent_to_pending_membership()
- check_channel_ready()
- _spin_up_agent_for_persona() S11 changes (always-fresh, project_id required)
- add_member() project_id parameter
"""

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
from claude_headspace.services.channel_service import (
    PersonaNotFoundError,
    ProjectNotFoundError,
)


@pytest.fixture
def db_session(app):
    """Provide a database session with table creation and cleanup."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def channel_service(app, db_session):
    """Get the ChannelService from app extensions."""
    return app.extensions["channel_service"]


@pytest.fixture
def setup_data(app, db_session):
    """Create test data: role, personas, project."""
    role = Role(name="developer-s11")
    db.session.add(role)
    db.session.flush()

    pt_internal = db.session.get(PersonaType, 1)
    pt_external = db.session.get(PersonaType, 2)

    # Operator persona (can_create_channel must be True — use internal type)
    operator = Persona(
        name="Operator",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    persona_b = Persona(
        name="Robbo",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    persona_c = Persona(
        name="Con",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    db.session.add_all([operator, persona_b, persona_c])
    db.session.flush()

    project = Project(
        name="s11-test-project", slug="s11-test-project", path="/tmp/s11-test"
    )
    db.session.add(project)
    db.session.commit()

    db.session.refresh(operator)
    db.session.refresh(persona_b)
    db.session.refresh(persona_c)

    return {
        "operator": operator,
        "persona_b": persona_b,
        "persona_c": persona_c,
        "project": project,
        "role": role,
    }


class TestCreateChannelFromPersonas:
    def test_creates_pending_channel(self, channel_service, setup_data):
        """Channel is created with status=pending."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[
                    setup_data["persona_b"].slug,
                    setup_data["persona_c"].slug,
                ],
            )

        assert channel.id is not None
        assert channel.status == "pending"

    def test_auto_generates_name_from_personas(self, channel_service, setup_data):
        """Channel name is built from persona names joined by ' + '."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[
                    setup_data["persona_b"].slug,
                    setup_data["persona_c"].slug,
                ],
            )

        assert "Robbo" in channel.name
        assert "Con" in channel.name
        assert "+" in channel.name

    def test_creates_null_agent_memberships(self, channel_service, setup_data):
        """Non-chair memberships are created with agent_id=None."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[
                    setup_data["persona_b"].slug,
                    setup_data["persona_c"].slug,
                ],
            )

        non_chair = ChannelMembership.query.filter_by(
            channel_id=channel.id, is_chair=False
        ).all()
        assert len(non_chair) == 2
        for m in non_chair:
            assert m.agent_id is None

    def test_injects_initiation_system_message(self, channel_service, setup_data):
        """A 'Channel initiating...' system message is posted."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[setup_data["persona_b"].slug],
            )

        messages = Message.query.filter_by(channel_id=channel.id).all()
        system_messages = [m for m in messages if m.message_type == MessageType.SYSTEM]
        assert any("initiating" in (m.content or "").lower() for m in system_messages)

    def test_raises_project_not_found(self, channel_service, setup_data):
        """ProjectNotFoundError raised if project_id doesn't exist."""
        with pytest.raises(ProjectNotFoundError):
            channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=999999,
                persona_slugs=[setup_data["persona_b"].slug],
            )

    def test_raises_persona_not_found(self, channel_service, setup_data):
        """PersonaNotFoundError raised if a slug doesn't resolve."""
        with pytest.raises(PersonaNotFoundError):
            channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=["no-such-persona"],
            )

    def test_spins_up_one_agent_per_persona(self, channel_service, setup_data):
        """_spin_up_agent_for_persona called once per persona slug."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[
                    setup_data["persona_b"].slug,
                    setup_data["persona_c"].slug,
                ],
            )

        assert mock_spinup.call_count == 2
        # Each call should include the correct project_id
        for call in mock_spinup.call_args_list:
            assert call.kwargs.get("project_id") == setup_data["project"].id


class TestLinkAgentToPendingMembership:
    def test_links_agent_to_pending_membership(self, channel_service, setup_data):
        """Agent is linked to the oldest pending membership for its persona."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[setup_data["persona_b"].slug],
            )

        # Create a fresh agent for persona_b
        agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=setup_data["persona_b"].id,
        )
        db.session.add(agent)
        db.session.commit()

        with patch.object(channel_service, "check_channel_ready") as mock_ready:
            channel_service.link_agent_to_pending_membership(agent)

        # Membership should now have agent_id set
        membership = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=setup_data["persona_b"].id, is_chair=False
        ).first()
        assert membership is not None
        assert membership.agent_id == agent.id
        mock_ready.assert_called_once_with(channel.id)

    def test_no_op_if_agent_has_no_persona(self, channel_service, setup_data):
        """Method returns early without error if agent has no persona."""
        agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=None,
        )
        db.session.add(agent)
        db.session.commit()

        # Should not raise
        channel_service.link_agent_to_pending_membership(agent)

    def test_no_op_if_no_pending_membership(self, channel_service, setup_data):
        """Method is a no-op if no pending membership exists for the persona."""
        agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=setup_data["persona_b"].id,
        )
        db.session.add(agent)
        db.session.commit()

        with patch.object(channel_service, "check_channel_ready") as mock_ready:
            channel_service.link_agent_to_pending_membership(agent)

        mock_ready.assert_not_called()


class TestCheckChannelReady:
    def test_returns_false_when_not_all_connected(self, channel_service, setup_data):
        """Returns False when some memberships still have agent_id=None."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[
                    setup_data["persona_b"].slug,
                    setup_data["persona_c"].slug,
                ],
            )

        with patch.object(channel_service, "_broadcast_update"):
            result = channel_service.check_channel_ready(channel.id)

        assert result is False
        db.session.refresh(channel)
        assert channel.status == "pending"

    def test_returns_true_and_transitions_when_all_connected(
        self, channel_service, setup_data
    ):
        """Returns True and transitions channel to active when all agents linked."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[setup_data["persona_b"].slug],
            )

        # Link agents to all non-chair memberships
        membership = ChannelMembership.query.filter_by(
            channel_id=channel.id, is_chair=False
        ).first()
        agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=setup_data["persona_b"].id,
        )
        db.session.add(agent)
        db.session.flush()
        membership.agent_id = agent.id
        db.session.commit()

        with patch.object(channel_service, "_broadcast_update") as mock_broadcast:
            result = channel_service.check_channel_ready(channel.id)

        assert result is True
        db.session.refresh(channel)
        assert channel.status == "active"

        # channel_ready SSE should be broadcast
        broadcast_types = [call.args[1] for call in mock_broadcast.call_args_list]
        assert "channel_ready" in broadcast_types

    def test_returns_false_for_non_pending_channel(self, channel_service, setup_data):
        """Returns False if channel is already active (not pending)."""
        with patch.object(channel_service, "_spin_up_agent_for_persona") as mock_spinup:
            mock_spinup.return_value = None
            channel = channel_service.create_channel_from_personas(
                creator_persona=setup_data["operator"],
                channel_type="workshop",
                project_id=setup_data["project"].id,
                persona_slugs=[setup_data["persona_b"].slug],
            )

        channel.status = "active"
        db.session.commit()

        result = channel_service.check_channel_ready(channel.id)
        assert result is False


class TestSpinUpAgentForPersonaS11:
    def test_returns_none_when_project_id_is_none(self, channel_service, setup_data):
        """Returns None immediately if project_id is None (S11 requirement)."""
        result = channel_service._spin_up_agent_for_persona(
            setup_data["persona_b"], project_id=None
        )
        assert result is None

    def test_calls_create_agent_with_project_id(self, channel_service, setup_data):
        """Passes project_id to create_agent."""
        mock_result = MagicMock()
        mock_result.success = True

        # create_agent is imported locally inside _spin_up_agent_for_persona;
        # patch it at its source module (agent_lifecycle).
        with patch(
            "claude_headspace.services.agent_lifecycle.create_agent",
            return_value=mock_result,
        ) as mock_create:
            channel_service._spin_up_agent_for_persona(
                setup_data["persona_b"], project_id=setup_data["project"].id
            )

        mock_create.assert_called_once_with(
            project_id=setup_data["project"].id,
            persona_slug=setup_data["persona_b"].slug,
        )

    def test_does_not_reuse_existing_agent(self, channel_service, setup_data):
        """S11: always creates a fresh agent, never returns existing active agent."""
        # Create an existing active agent
        existing_agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=setup_data["persona_b"].id,
        )
        db.session.add(existing_agent)
        db.session.commit()

        mock_result = MagicMock()
        mock_result.success = True

        # create_agent is imported locally; patch at its source module.
        with patch(
            "claude_headspace.services.agent_lifecycle.create_agent",
            return_value=mock_result,
        ) as mock_create:
            result = channel_service._spin_up_agent_for_persona(
                setup_data["persona_b"], project_id=setup_data["project"].id
            )

        # Should have called create_agent (not returned existing agent)
        mock_create.assert_called_once()
        # Returns None (async spin-up)
        assert result is None
