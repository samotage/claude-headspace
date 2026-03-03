"""Tests for flask channel CLI commands."""

import os
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
    """Create standard test data and set HEADSPACE_AGENT_ID."""
    role = Role(name="developer")
    db_session.add(role)
    db_session.flush()

    pt_internal = db_session.get(PersonaType, 1)

    persona_a = Persona(
        name="Alice", role_id=role.id, role=role,
        persona_type_id=pt_internal.id, status="active",
    )
    persona_b = Persona(
        name="Bob", role_id=role.id, role=role,
        persona_type_id=pt_internal.id, status="active",
    )
    db_session.add_all([persona_a, persona_b])
    db_session.flush()

    project = Project(name="test-project", slug="test-project", path="/tmp/test")
    db_session.add(project)
    db_session.flush()

    agent_a = Agent(
        session_uuid=uuid4(), project_id=project.id,
        persona_id=persona_a.id,
    )
    agent_b = Agent(
        session_uuid=uuid4(), project_id=project.id,
        persona_id=persona_b.id,
    )
    db_session.add_all([agent_a, agent_b])
    db_session.commit()

    # Refresh to get generated slugs
    db_session.refresh(persona_a)
    db_session.refresh(persona_b)

    # Set env var so caller resolution works
    os.environ["HEADSPACE_AGENT_ID"] = str(agent_a.id)

    yield {
        "persona_a": persona_a,
        "persona_b": persona_b,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "project": project,
    }

    os.environ.pop("HEADSPACE_AGENT_ID", None)


class TestChannelCreate:
    """Test flask channel create command (SC-1)."""

    def test_create_channel(self, runner, setup_data):
        """Create a channel via CLI."""
        result = runner.invoke(
            args=["channel", "create", "my-channel", "--type", "workshop"]
        )
        assert result.exit_code == 0
        assert "Channel created:" in result.output
        assert "workshop" in result.output

    def test_create_with_description(self, runner, setup_data):
        """Create a channel with description."""
        result = runner.invoke(
            args=["channel", "create", "desc-chan", "--type", "review",
                  "--description", "Test desc"]
        )
        assert result.exit_code == 0
        assert "Test desc" in result.output


class TestChannelList:
    """Test flask channel list command (SC-2, SC-3)."""

    def test_list_my_channels(self, runner, setup_data):
        """List channels the caller is a member of."""
        # Create a channel first
        runner.invoke(
            args=["channel", "create", "list-test", "--type", "workshop"]
        )
        result = runner.invoke(args=["channel", "list"])
        assert result.exit_code == 0
        assert "list-test" in result.output

    def test_list_all(self, runner, setup_data):
        """List all non-archived channels with --all."""
        runner.invoke(
            args=["channel", "create", "all-test", "--type", "workshop"]
        )
        result = runner.invoke(args=["channel", "list", "--all"])
        assert result.exit_code == 0
        assert "all-test" in result.output

    def test_list_empty(self, runner, setup_data):
        """Empty list shows message."""
        result = runner.invoke(args=["channel", "list"])
        assert result.exit_code == 0
        assert "No channels found" in result.output


class TestChannelShow:
    """Test flask channel show command (SC-4)."""

    def test_show_channel(self, runner, setup_data):
        """Show channel details."""
        runner.invoke(
            args=["channel", "create", "show-test", "--type", "workshop"]
        )
        # Get the slug from the channel
        channel = Channel.query.filter(Channel.name == "show-test").first()
        result = runner.invoke(args=["channel", "show", channel.slug])
        assert result.exit_code == 0
        assert "show-test" in result.output
        assert "workshop" in result.output
        assert "Alice" in result.output

    def test_show_not_found(self, runner, setup_data):
        """Show non-existent channel fails."""
        result = runner.invoke(args=["channel", "show", "nonexistent"])
        assert result.exit_code == 1


class TestChannelMembers:
    """Test flask channel members command (FR5b)."""

    def test_members(self, runner, setup_data):
        """List channel members."""
        runner.invoke(
            args=["channel", "create", "members-test", "--type", "workshop"]
        )
        channel = Channel.query.filter(Channel.name == "members-test").first()
        result = runner.invoke(args=["channel", "members", channel.slug])
        assert result.exit_code == 0
        assert "Alice" in result.output
        assert "yes" in result.output  # chair marker


class TestChannelAdd:
    """Test flask channel add command (SC-5)."""

    def test_add_member(self, runner, setup_data):
        """Add a persona to a channel."""
        runner.invoke(
            args=["channel", "create", "add-test", "--type", "workshop"]
        )
        channel = Channel.query.filter(Channel.name == "add-test").first()
        result = runner.invoke(
            args=["channel", "add", channel.slug,
                  "--persona", setup_data["persona_b"].slug]
        )
        assert result.exit_code == 0
        assert "Added Bob" in result.output

    def test_add_not_found(self, runner, setup_data):
        """Add non-existent persona fails."""
        runner.invoke(
            args=["channel", "create", "add-fail", "--type", "workshop"]
        )
        channel = Channel.query.filter(Channel.name == "add-fail").first()
        result = runner.invoke(
            args=["channel", "add", channel.slug, "--persona", "nonexistent"]
        )
        assert result.exit_code == 1


class TestChannelLeave:
    """Test flask channel leave command (SC-7)."""

    def test_leave_channel(self, runner, setup_data):
        """Leave a channel."""
        runner.invoke(
            args=["channel", "create", "leave-test", "--type", "workshop"]
        )
        channel = Channel.query.filter(Channel.name == "leave-test").first()
        result = runner.invoke(args=["channel", "leave", channel.slug])
        assert result.exit_code == 0
        assert "Left" in result.output


class TestChannelComplete:
    """Test flask channel complete command (SC-9)."""

    def test_complete_channel(self, runner, setup_data):
        """Complete a channel."""
        runner.invoke(
            args=["channel", "create", "comp-test", "--type", "workshop"]
        )
        channel = Channel.query.filter(Channel.name == "comp-test").first()
        result = runner.invoke(args=["channel", "complete", channel.slug])
        assert result.exit_code == 0
        assert "completed" in result.output

    def test_complete_non_chair(self, runner, setup_data):
        """Non-chair cannot complete."""
        runner.invoke(
            args=["channel", "create", "comp-fail", "--type", "workshop",
                  "--members", setup_data["persona_b"].slug]
        )
        channel = Channel.query.filter(Channel.name == "comp-fail").first()
        # Switch to agent B
        os.environ["HEADSPACE_AGENT_ID"] = str(setup_data["agent_b"].id)
        result = runner.invoke(args=["channel", "complete", channel.slug])
        assert result.exit_code == 1
        # Restore
        os.environ["HEADSPACE_AGENT_ID"] = str(setup_data["agent_a"].id)


class TestChannelTransferChair:
    """Test flask channel transfer-chair command (SC-10)."""

    def test_transfer_chair(self, runner, setup_data):
        """Transfer chair to another member."""
        runner.invoke(
            args=["channel", "create", "xfer-test", "--type", "workshop",
                  "--members", setup_data["persona_b"].slug]
        )
        channel = Channel.query.filter(Channel.name == "xfer-test").first()
        result = runner.invoke(
            args=["channel", "transfer-chair", channel.slug,
                  "--to", setup_data["persona_b"].slug]
        )
        assert result.exit_code == 0
        assert "transferred" in result.output


class TestChannelMuteUnmute:
    """Test flask channel mute and unmute commands (SC-11)."""

    def test_mute_and_unmute(self, runner, setup_data):
        """Mute and unmute a channel."""
        runner.invoke(
            args=["channel", "create", "mute-test", "--type", "workshop"]
        )
        channel = Channel.query.filter(Channel.name == "mute-test").first()

        result = runner.invoke(args=["channel", "mute", channel.slug])
        assert result.exit_code == 0
        assert "Muted" in result.output

        result = runner.invoke(args=["channel", "unmute", channel.slug])
        assert result.exit_code == 0
        assert "Unmuted" in result.output


class TestCallerIdentityErrors:
    """Test caller identity resolution errors (SC-20)."""

    def test_no_agent_resolution(self, runner, setup_data):
        """Error when agent cannot be resolved."""
        os.environ.pop("HEADSPACE_AGENT_ID", None)
        with patch(
            "claude_headspace.services.caller_identity.resolve_caller"
        ) as mock_resolve:
            from claude_headspace.services.caller_identity import CallerResolutionError
            mock_resolve.side_effect = CallerResolutionError(
                "Error: Cannot identify calling agent."
            )
            result = runner.invoke(
                args=["channel", "create", "fail", "--type", "workshop"]
            )
            assert result.exit_code == 1
            assert "Cannot identify" in result.output
        # Restore
        os.environ["HEADSPACE_AGENT_ID"] = str(setup_data["agent_a"].id)


class TestChannelErrorDisplay:
    """Test ChannelError display in CLI."""

    def test_channel_error_to_stderr(self, runner, setup_data):
        """ChannelError message displayed to user."""
        result = runner.invoke(
            args=["channel", "show", "does-not-exist"]
        )
        assert result.exit_code == 1
