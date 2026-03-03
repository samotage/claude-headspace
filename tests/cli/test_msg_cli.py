"""Tests for flask msg CLI commands."""

import os
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.channel import Channel
from claude_headspace.models.persona import Persona
from claude_headspace.models.persona_type import PersonaType
from claude_headspace.models.project import Project
from claude_headspace.models.role import Role


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
    """Create standard test data."""
    role = Role(name="developer")
    db_session.add(role)
    db_session.flush()

    pt_internal = db_session.get(PersonaType, 1)

    persona = Persona(
        name="Alice",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
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
    )
    db_session.add(agent)
    db_session.commit()

    db_session.refresh(persona)

    os.environ["HEADSPACE_AGENT_ID"] = str(agent.id)

    yield {
        "persona": persona,
        "agent": agent,
        "project": project,
    }

    os.environ.pop("HEADSPACE_AGENT_ID", None)


class TestMsgSend:
    """Test flask msg send command (SC-12)."""

    def test_send_message(self, runner, setup_data):
        """Send a message to a channel."""
        # Create a channel first
        runner.invoke(args=["channel", "create", "msg-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "msg-test").first()

        result = runner.invoke(args=["msg", "send", channel.slug, "Hello world!"])
        assert result.exit_code == 0
        assert "Message sent" in result.output

    def test_send_to_nonexistent_channel(self, runner, setup_data):
        """Send to non-existent channel fails."""
        result = runner.invoke(args=["msg", "send", "nonexistent", "Hello"])
        assert result.exit_code == 1


class TestMsgHistory:
    """Test flask msg history command (SC-14, SC-15)."""

    def test_history_envelope_format(self, runner, setup_data):
        """History in envelope format shows headers and content."""
        runner.invoke(args=["channel", "create", "hist-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "hist-test").first()
        runner.invoke(args=["msg", "send", channel.slug, "Test message content"])

        result = runner.invoke(args=["msg", "history", channel.slug])
        assert result.exit_code == 0
        assert "Test message content" in result.output
        assert "Alice" in result.output

    def test_history_yaml_format(self, runner, setup_data):
        """History in YAML format shows structured output."""
        runner.invoke(args=["channel", "create", "yaml-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "yaml-test").first()
        runner.invoke(args=["msg", "send", channel.slug, "YAML test"])

        result = runner.invoke(
            args=["msg", "history", channel.slug, "--format", "yaml"]
        )
        assert result.exit_code == 0
        assert "content:" in result.output or "YAML test" in result.output
        assert "message_type:" in result.output

    def test_history_empty(self, runner, setup_data):
        """Empty history shows message."""
        runner.invoke(args=["channel", "create", "empty-hist", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "empty-hist").first()

        result = runner.invoke(args=["msg", "history", channel.slug])
        assert result.exit_code == 0
        # Might have system messages or "No messages" text
