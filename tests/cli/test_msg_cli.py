"""Tests for flask msg CLI commands.

After agent-channel-security change:
- HEADSPACE_AGENT_ID env var is no longer used for identity resolution
- `flask msg send` is restricted to operators only (reject_if_agent_context)
- `flask msg history` remains accessible (read-only)
- resolve_caller_persona() falls back to operator persona when not in agent tmux
- Tests mock tmux pane detection for caller identity
"""

from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.channel import Channel
from claude_headspace.models.persona import Persona
from claude_headspace.models.persona_type import PersonaType
from claude_headspace.models.project import Project
from claude_headspace.models.role import Role

from .conftest import mock_tmux_fails, mock_tmux_resolves_agent


@pytest.fixture
def db_session(app):
    """Provide a database session with rollback isolation."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def setup_data(app, db_session):
    """Create standard test data including operator persona."""
    role = Role(name="developer")
    db_session.add(role)
    db_session.flush()

    pt_agent_internal = db_session.get(PersonaType, 1)
    pt_person_internal = db_session.get(PersonaType, 3)

    # Operator persona (person/internal type) — used by operator fallback
    operator = Persona(
        name="Sam",
        role_id=role.id,
        role=role,
        persona_type_id=pt_person_internal.id,
        status="active",
    )
    db_session.add(operator)
    db_session.flush()

    # Agent persona (agent/internal type)
    persona = Persona(
        name="Alice",
        role_id=role.id,
        role=role,
        persona_type_id=pt_agent_internal.id,
        status="active",
    )
    db_session.add(persona)
    db_session.flush()

    project = Project(name="test-project", slug="test-project", path="/tmp/test")
    db_session.add(project)
    db_session.flush()

    agent = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=persona.id,
        tmux_pane_id="%99",
    )
    db_session.add(agent)
    db_session.commit()

    db_session.refresh(operator)
    db_session.refresh(persona)

    yield {
        "operator": operator,
        "persona": persona,
        "agent": agent,
        "project": project,
    }


class TestMsgSend:
    """Test flask msg send command (SC-12).

    After agent-channel-security: msg send is operator-only.
    Operator context = tmux resolution fails, fallback to operator persona.
    """

    def test_send_message(self, runner, setup_data):
        """Send a message to a channel (operator context)."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "msg-test", "--type", "workshop"])

        channel = Channel.query.filter(Channel.name == "msg-test").first()

        with mock_tmux_fails():
            result = runner.invoke(args=["msg", "send", channel.slug, "Hello world!"])
        assert result.exit_code == 0, result.output
        assert "Message sent" in result.output

    def test_send_to_nonexistent_channel(self, runner, setup_data):
        """Send to non-existent channel fails."""
        with mock_tmux_fails():
            result = runner.invoke(args=["msg", "send", "nonexistent", "Hello"])
        assert result.exit_code == 1

    def test_send_rejected_in_agent_context(self, runner, setup_data):
        """flask msg send is rejected when called from an agent tmux context."""
        agent = setup_data["agent"]

        # First create a channel as operator
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "agent-test", "--type", "workshop"]
            )

        channel = Channel.query.filter(Channel.name == "agent-test").first()

        # Now try to send as agent — should be rejected
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(args=["msg", "send", channel.slug, "Sneaky message"])

        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestMsgHistory:
    """Test flask msg history command (SC-14, SC-15).

    History is read-only — no agent context restriction.
    """

    def test_history_envelope_format(self, runner, setup_data):
        """History in envelope format shows headers and content."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "hist-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "hist-test").first()
        with mock_tmux_fails():
            runner.invoke(args=["msg", "send", channel.slug, "Test message content"])

        with mock_tmux_fails():
            result = runner.invoke(args=["msg", "history", channel.slug])
        assert result.exit_code == 0
        assert "Test message content" in result.output

    def test_history_yaml_format(self, runner, setup_data):
        """History in YAML format shows structured output."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "yaml-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "yaml-test").first()
        with mock_tmux_fails():
            runner.invoke(args=["msg", "send", channel.slug, "YAML test"])

        with mock_tmux_fails():
            result = runner.invoke(
                args=["msg", "history", channel.slug, "--format", "yaml"]
            )
        assert result.exit_code == 0
        assert "content:" in result.output or "YAML test" in result.output
        assert "message_type:" in result.output

    def test_history_empty(self, runner, setup_data):
        """Empty history shows message."""
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "empty-hist", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "empty-hist").first()

        with mock_tmux_fails():
            result = runner.invoke(args=["msg", "history", channel.slug])
        assert result.exit_code == 0
        # Might have system messages or "No messages" text
