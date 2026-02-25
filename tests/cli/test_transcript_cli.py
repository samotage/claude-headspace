"""Tests for the transcript CLI command."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.cli.transcript_cli import format_transcript


class TestFormatTranscript:
    """Tests for the transcript formatting logic."""

    def _make_agent(
        self,
        agent_id=1,
        project_name="test-project",
        persona_name=None,
        started_at=None,
        ended_at=None,
        commands=None,
    ):
        """Helper to create a mock agent."""
        agent = MagicMock()
        agent.id = agent_id
        agent.session_uuid = uuid4()
        agent.started_at = started_at or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        agent.ended_at = ended_at

        project = MagicMock()
        project.name = project_name
        agent.project = project

        if persona_name:
            persona = MagicMock()
            persona.name = persona_name
            agent.persona = persona
        else:
            agent.persona = None

        agent.commands = commands if commands is not None else []
        return agent

    def _make_command(self, instruction="Do something", state="complete",
                      started_at=None, completed_at=None, turns=None,
                      full_command=None, completion_summary=None):
        """Helper to create a mock command."""
        cmd = MagicMock()
        cmd.instruction = instruction
        cmd.full_command = full_command
        cmd.state = MagicMock()
        cmd.state.value = state
        cmd.started_at = started_at or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        cmd.completed_at = completed_at
        cmd.completion_summary = completion_summary
        cmd.turns = turns if turns is not None else []
        cmd.id = 1
        return cmd

    def _make_turn(self, actor="user", text="Hello", timestamp=None):
        """Helper to create a mock turn."""
        from claude_headspace.models.turn import TurnActor

        turn = MagicMock()
        turn.actor = TurnActor.USER if actor == "user" else TurnActor.AGENT
        turn.text = text
        turn.timestamp = timestamp or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return turn

    def test_header_includes_agent_id(self):
        agent = self._make_agent(agent_id=42)
        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            output = format_transcript(agent)
        assert "# Transcript for Agent #42" in output

    def test_header_includes_project_name(self):
        agent = self._make_agent(project_name="my-project")
        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            output = format_transcript(agent)
        assert "**Project:** my-project" in output

    def test_header_includes_persona_name(self):
        agent = self._make_agent(persona_name="TestPersona")
        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            output = format_transcript(agent)
        assert "**Persona:** TestPersona" in output

    def test_no_commands_message(self):
        agent = self._make_agent()
        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            output = format_transcript(agent)
        assert "No commands found" in output

    def test_command_heading_uses_instruction(self):
        cmd = self._make_command(instruction="Fix the login bug")
        agent = self._make_agent()

        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            # First query returns commands, second returns turns
            query_mock = mock_db.session.query.return_value
            filter_mock = query_mock.filter.return_value
            order_mock = filter_mock.order_by.return_value

            # Use side_effect to return different results for commands vs turns queries
            call_count = [0]
            def all_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return [cmd]  # Commands query
                return []  # Turns query
            order_mock.all.side_effect = all_side_effect

            output = format_transcript(agent)

        assert "## Command: Fix the login bug" in output

    def test_turns_prefixed_with_actor(self):
        from claude_headspace.models.turn import TurnActor

        user_turn = self._make_turn(actor="user", text="Please fix this")
        agent_turn = self._make_turn(actor="agent", text="I will fix it")

        cmd = self._make_command(instruction="Fix bug", turns=[user_turn, agent_turn])
        agent = self._make_agent()

        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            query_mock = mock_db.session.query.return_value
            filter_mock = query_mock.filter.return_value
            order_mock = filter_mock.order_by.return_value

            call_count = [0]
            def all_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return [cmd]
                return [user_turn, agent_turn]
            order_mock.all.side_effect = all_side_effect

            output = format_transcript(agent)

        assert "**User:**" in output
        assert "**Agent:**" in output
        assert "Please fix this" in output
        assert "I will fix it" in output

    def test_ended_at_shown_when_set(self):
        ended = datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        agent = self._make_agent(ended_at=ended)
        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            output = format_transcript(agent)
        assert "**Ended:**" in output

    def test_completion_summary_included(self):
        cmd = self._make_command(
            instruction="Build feature",
            completion_summary="Feature built successfully"
        )
        agent = self._make_agent()

        with patch("claude_headspace.cli.transcript_cli.db") as mock_db:
            query_mock = mock_db.session.query.return_value

            # Need to handle the chaining properly for multiple filter() calls
            # Commands query: .filter(agent_id).order_by(started_at).all()
            # Turns query: .filter(cmd_id, text not null, text != "").order_by(timestamp).all()
            call_count = [0]
            def filter_side_effect(*args, **kwargs):
                call_count[0] += 1
                filter_result = MagicMock()
                if call_count[0] == 1:
                    # Commands filter
                    filter_result.order_by.return_value.all.return_value = [cmd]
                else:
                    # Turns filter — return another chainable mock
                    filter_result2 = MagicMock()
                    filter_result2.order_by.return_value.all.return_value = []
                    filter_result.filter.return_value = filter_result2
                return filter_result

            query_mock.filter.side_effect = filter_side_effect

            output = format_transcript(agent)

        assert "Feature built successfully" in output


class TestTranscriptCLI:
    """Tests for the CLI command invocation."""

    def test_agent_not_found(self, runner, app):
        """Test that non-existent agent ID produces an error."""
        result = runner.invoke(args=["transcript", "show", "999999"])
        # The exit code should be non-zero (SystemExit(1))
        assert result.exit_code != 0

    def test_show_command_exists(self, runner, app):
        """Test that the 'transcript show' command is registered."""
        result = runner.invoke(args=["transcript", "--help"])
        assert result.exit_code == 0
        assert "show" in result.output.lower()
