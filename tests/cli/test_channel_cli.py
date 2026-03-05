"""Tests for flask channel CLI commands.

After agent-channel-security change:
- HEADSPACE_AGENT_ID env var is no longer used for identity resolution
- Mutating channel commands are restricted to operators only
- Read-only commands (list, show, members) remain accessible
- resolve_caller_persona() falls back to operator persona when not in agent tmux
- Tests mock tmux pane detection for caller identity
"""

from unittest.mock import patch
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

    # Agent personas (agent/internal type)
    persona_a = Persona(
        name="Alice",
        role_id=role.id,
        role=role,
        persona_type_id=pt_agent_internal.id,
        status="active",
    )
    persona_b = Persona(
        name="Bob",
        role_id=role.id,
        role=role,
        persona_type_id=pt_agent_internal.id,
        status="active",
    )
    db_session.add_all([persona_a, persona_b])
    db_session.flush()

    project = Project(name="test-project", slug="test-project", path="/tmp/test")
    db_session.add(project)
    db_session.flush()

    agent_a = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=persona_a.id,
        tmux_pane_id="%99",
    )
    agent_b = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=persona_b.id,
        tmux_pane_id="%100",
    )
    db_session.add_all([agent_a, agent_b])
    db_session.commit()

    # Refresh to get generated slugs
    db_session.refresh(operator)
    db_session.refresh(persona_a)
    db_session.refresh(persona_b)

    yield {
        "operator": operator,
        "persona_a": persona_a,
        "persona_b": persona_b,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "project": project,
    }


class TestChannelCreate:
    """Test flask channel create command (SC-1)."""

    def test_create_channel(self, runner, setup_data):
        """Create a channel via CLI (operator context)."""
        with mock_tmux_fails():
            result = runner.invoke(
                args=["channel", "create", "my-channel", "--type", "workshop"]
            )
        assert result.exit_code == 0, result.output
        assert "Channel created:" in result.output
        assert "workshop" in result.output

    def test_create_with_description(self, runner, setup_data):
        """Create a channel with description."""
        with mock_tmux_fails():
            result = runner.invoke(
                args=[
                    "channel",
                    "create",
                    "desc-chan",
                    "--type",
                    "review",
                    "--description",
                    "Test desc",
                ]
            )
        assert result.exit_code == 0, result.output
        assert "Test desc" in result.output

    def test_create_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot create channels via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(
                args=["channel", "create", "sneaky-channel", "--type", "workshop"]
            )
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestChannelList:
    """Test flask channel list command (SC-2, SC-3).

    List is read-only — no agent context restriction. Uses operator
    fallback when not in agent tmux context.
    """

    def test_list_my_channels(self, runner, setup_data):
        """List channels the caller is a member of."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "list-test", "--type", "workshop"])
            result = runner.invoke(args=["channel", "list"])
        assert result.exit_code == 0
        assert "list-test" in result.output

    def test_list_all(self, runner, setup_data):
        """List all non-archived channels with --all."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "all-test", "--type", "workshop"])
            result = runner.invoke(args=["channel", "list", "--all"])
        assert result.exit_code == 0
        assert "all-test" in result.output

    def test_list_empty(self, runner, setup_data):
        """Empty list shows message."""
        with mock_tmux_fails():
            result = runner.invoke(args=["channel", "list"])
        assert result.exit_code == 0
        assert "No channels found" in result.output


class TestChannelShow:
    """Test flask channel show command (SC-4).

    Show is read-only — no agent context restriction. Does not require
    caller identity resolution.
    """

    def test_show_channel(self, runner, setup_data):
        """Show channel details."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "show-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "show-test").first()
        result = runner.invoke(args=["channel", "show", channel.slug])
        assert result.exit_code == 0
        assert "show-test" in result.output
        assert "workshop" in result.output

    def test_show_not_found(self, runner, setup_data):
        """Show non-existent channel fails."""
        result = runner.invoke(args=["channel", "show", "nonexistent"])
        assert result.exit_code == 1


class TestChannelMembers:
    """Test flask channel members command (FR5b).

    Members is read-only — no agent context restriction.
    """

    def test_members(self, runner, setup_data):
        """List channel members."""
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "members-test", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "members-test").first()
        result = runner.invoke(args=["channel", "members", channel.slug])
        assert result.exit_code == 0


class TestChannelAdd:
    """Test flask channel add command (SC-5)."""

    def test_add_member(self, runner, setup_data):
        """Add a persona to a channel (operator context)."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "add-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "add-test").first()
        with mock_tmux_fails():
            result = runner.invoke(
                args=[
                    "channel",
                    "add",
                    channel.slug,
                    "--persona",
                    setup_data["persona_b"].slug,
                ]
            )
        assert result.exit_code == 0, result.output
        assert "Added Bob" in result.output

    def test_add_not_found(self, runner, setup_data):
        """Add non-existent persona fails."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "add-fail", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "add-fail").first()
        with mock_tmux_fails():
            result = runner.invoke(
                args=["channel", "add", channel.slug, "--persona", "nonexistent"]
            )
        assert result.exit_code == 1

    def test_add_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot add members via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "add-agent", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "add-agent").first()
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(
                args=[
                    "channel",
                    "add",
                    channel.slug,
                    "--persona",
                    setup_data["persona_b"].slug,
                ]
            )
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestChannelLeave:
    """Test flask channel leave command (SC-7)."""

    def test_leave_channel(self, runner, setup_data):
        """Leave a channel (operator context)."""
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "leave-test", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "leave-test").first()
        with mock_tmux_fails():
            result = runner.invoke(args=["channel", "leave", channel.slug])
        assert result.exit_code == 0
        assert "Left" in result.output

    def test_leave_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot leave channels via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "leave-agent", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "leave-agent").first()
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(args=["channel", "leave", channel.slug])
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestChannelComplete:
    """Test flask channel complete command (SC-9)."""

    def test_complete_channel(self, runner, setup_data):
        """Complete a channel (operator context)."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "comp-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "comp-test").first()
        with mock_tmux_fails():
            result = runner.invoke(args=["channel", "complete", channel.slug])
        assert result.exit_code == 0
        assert "completed" in result.output

    def test_complete_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot complete channels via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "comp-agent", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "comp-agent").first()
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(args=["channel", "complete", channel.slug])
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestChannelTransferChair:
    """Test flask channel transfer-chair command (SC-10)."""

    def test_transfer_chair(self, runner, setup_data):
        """Transfer chair to another member (operator context)."""
        with mock_tmux_fails():
            runner.invoke(
                args=[
                    "channel",
                    "create",
                    "xfer-test",
                    "--type",
                    "workshop",
                    "--members",
                    setup_data["persona_b"].slug,
                ]
            )
        channel = Channel.query.filter(Channel.name == "xfer-test").first()
        with mock_tmux_fails():
            result = runner.invoke(
                args=[
                    "channel",
                    "transfer-chair",
                    channel.slug,
                    "--to",
                    setup_data["persona_b"].slug,
                ]
            )
        assert result.exit_code == 0, result.output
        assert "transferred" in result.output

    def test_transfer_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot transfer chair via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_fails():
            runner.invoke(
                args=[
                    "channel",
                    "create",
                    "xfer-agent",
                    "--type",
                    "workshop",
                    "--members",
                    setup_data["persona_b"].slug,
                ]
            )
        channel = Channel.query.filter(Channel.name == "xfer-agent").first()
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(
                args=[
                    "channel",
                    "transfer-chair",
                    channel.slug,
                    "--to",
                    setup_data["persona_b"].slug,
                ]
            )
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestChannelMuteUnmute:
    """Test flask channel mute and unmute commands (SC-11)."""

    def test_mute_and_unmute(self, runner, setup_data):
        """Mute and unmute a channel (operator context)."""
        with mock_tmux_fails():
            runner.invoke(args=["channel", "create", "mute-test", "--type", "workshop"])
        channel = Channel.query.filter(Channel.name == "mute-test").first()

        with mock_tmux_fails():
            result = runner.invoke(args=["channel", "mute", channel.slug])
        assert result.exit_code == 0
        assert "Muted" in result.output

        with mock_tmux_fails():
            result = runner.invoke(args=["channel", "unmute", channel.slug])
        assert result.exit_code == 0
        assert "Unmuted" in result.output

    def test_mute_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot mute channels via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "mute-agent", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "mute-agent").first()
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(args=["channel", "mute", channel.slug])
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output

    def test_unmute_rejected_in_agent_context(self, runner, setup_data):
        """Agent cannot unmute channels via CLI."""
        agent = setup_data["agent_a"]
        with mock_tmux_fails():
            runner.invoke(
                args=["channel", "create", "unmute-agent", "--type", "workshop"]
            )
        channel = Channel.query.filter(Channel.name == "unmute-agent").first()
        # Mute first as operator
        with mock_tmux_fails():
            runner.invoke(args=["channel", "mute", channel.slug])
        with mock_tmux_resolves_agent(agent):
            result = runner.invoke(args=["channel", "unmute", channel.slug])
        assert result.exit_code == 1
        assert "restricted to operators only" in result.output


class TestCallerIdentityErrors:
    """Test caller identity resolution errors (SC-20)."""

    def test_no_agent_resolution(self, runner, setup_data):
        """Error when agent cannot be resolved and no operator exists.

        When both tmux resolution and operator fallback fail, the command
        should exit with code 1.
        """
        with (
            mock_tmux_fails(),
            patch(
                "claude_headspace.models.persona.Persona.get_operator",
                return_value=None,
            ),
        ):
            result = runner.invoke(
                args=["channel", "create", "fail", "--type", "workshop"]
            )
            assert result.exit_code == 1
            assert "Cannot identify caller" in result.output


class TestChannelErrorDisplay:
    """Test ChannelError display in CLI."""

    def test_channel_error_to_stderr(self, runner, setup_data):
        """ChannelError message displayed to user."""
        result = runner.invoke(args=["channel", "show", "does-not-exist"])
        assert result.exit_code == 1
