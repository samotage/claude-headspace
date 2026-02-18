"""Tests for full_command and full_output capture (e5-s9).

Tests cover:
- Command model fields (nullable, creation)
- CommandLifecycleManager.process_turn() persists full_command
- CommandLifecycleManager.complete_command() persists full_output
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from claude_headspace.models.agent import Agent
from claude_headspace.models.command import Command, CommandState
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent
from claude_headspace.services.event_writer import EventWriter, WriteResult
from claude_headspace.services.command_lifecycle import CommandLifecycleManager


class TestCommandModelFullTextFields:
    """Unit tests for Command model new fields."""

    def test_full_command_field_exists(self):
        """Command model should have full_command field."""
        cmd = Command.__table__
        assert "full_command" in cmd.columns

    def test_full_output_field_exists(self):
        """Command model should have full_output field."""
        cmd = Command.__table__
        assert "full_output" in cmd.columns

    def test_full_command_is_nullable(self):
        """full_command should be nullable."""
        col = Command.__table__.columns["full_command"]
        assert col.nullable is True

    def test_full_output_is_nullable(self):
        """full_output should be nullable."""
        col = Command.__table__.columns["full_output"]
        assert col.nullable is True

    def test_full_command_defaults_to_none(self):
        """full_command should default to None on new Command."""
        command = Command(agent_id=1, state=CommandState.COMMANDED)
        assert command.full_command is None

    def test_full_output_defaults_to_none(self):
        """full_output should default to None on new Command."""
        command = Command(agent_id=1, state=CommandState.COMMANDED)
        assert command.full_output is None


class TestProcessTurnFullCommand:
    """Task 3.2: process_turn() persists full_command on new commands."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def mock_event_writer(self):
        writer = MagicMock(spec=EventWriter)
        writer.write_event.return_value = WriteResult(success=True, event_id=1)
        return writer

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock(spec=Agent)
        agent.id = 1
        return agent

    def _setup_no_current_command(self, mock_session):
        """Configure mock session to return no current command."""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

    def test_full_command_persisted_on_new_command(self, mock_session, mock_event_writer, mock_agent):
        """User command should persist full text to command.full_command."""
        manager = CommandLifecycleManager(session=mock_session, event_writer=mock_event_writer)
        self._setup_no_current_command(mock_session)

        command_text = "Please refactor the authentication module to use JWT tokens instead of session cookies"

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=command_text,
        )

        assert result.success is True
        assert result.new_command_created is True

        # Find the Command object that was added to session
        command_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Command)]
        assert len(command_adds) == 1
        cmd = command_adds[0][0][0]
        assert cmd.full_command == command_text

    def test_full_command_not_set_when_text_is_none(self, mock_session, mock_event_writer, mock_agent):
        """full_command should not be set when text is None (hook path)."""
        manager = CommandLifecycleManager(session=mock_session, event_writer=mock_event_writer)
        self._setup_no_current_command(mock_session)

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=None,
        )

        assert result.success is True
        # Command was created but full_command stays at default (None)
        command_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Command)]
        assert len(command_adds) == 1
        cmd = command_adds[0][0][0]
        assert cmd.full_command is None

    def test_full_command_preserves_long_text(self, mock_session, mock_event_writer, mock_agent):
        """full_command should preserve very long command text without truncation."""
        manager = CommandLifecycleManager(session=mock_session, event_writer=mock_event_writer)
        self._setup_no_current_command(mock_session)

        long_text = "Fix the bug " * 500  # ~6500 chars

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=long_text,
        )

        assert result.success is True
        command_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Command)]
        cmd = command_adds[0][0][0]
        assert cmd.full_command == long_text


class TestCompleteCommandFullOutput:
    """Task 3.3: complete_command() persists full_output."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def mock_event_writer(self):
        writer = MagicMock(spec=EventWriter)
        writer.write_event.return_value = WriteResult(success=True, event_id=1)
        return writer

    @pytest.fixture
    def mock_command(self):
        cmd = MagicMock(spec=Command)
        cmd.id = 1
        cmd.agent_id = 1
        cmd.agent = MagicMock(spec=Agent)
        cmd.agent.id = 1
        cmd.state = CommandState.PROCESSING
        cmd.completed_at = None
        cmd.full_output = None
        return cmd

    def test_full_output_persisted_on_completion(self, mock_session, mock_event_writer, mock_command):
        """complete_command should persist agent_text to command.full_output."""
        manager = CommandLifecycleManager(session=mock_session, event_writer=mock_event_writer)

        agent_text = "Done. I've refactored the auth module to use JWT. Changes:\n1. Added jwt_utils.py\n2. Updated middleware"

        manager.complete_command(mock_command, agent_text=agent_text)

        assert mock_command.full_output == agent_text
        assert mock_command.state == CommandState.COMPLETE

    def test_full_output_not_set_when_agent_text_empty(self, mock_session, mock_event_writer, mock_command):
        """full_output should not be set when agent_text is empty string."""
        manager = CommandLifecycleManager(session=mock_session, event_writer=mock_event_writer)

        manager.complete_command(mock_command, agent_text="")

        # Empty string is falsy, so full_output won't be set
        assert mock_command.full_output is None
        assert mock_command.state == CommandState.COMPLETE

    def test_full_output_preserves_long_text(self, mock_session, mock_event_writer, mock_command):
        """full_output should preserve very long output text."""
        manager = CommandLifecycleManager(session=mock_session, event_writer=mock_event_writer)

        long_output = "I've completed the implementation. " * 500

        manager.complete_command(mock_command, agent_text=long_output)

        assert mock_command.full_output == long_output
