"""Tests for command lifecycle manager service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project
from claude_headspace.models.command import Command, CommandState
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent
from claude_headspace.services.event_writer import EventWriter, WriteResult
from claude_headspace.services.state_machine import TransitionResult
from claude_headspace.services.command_lifecycle import (
    AnswerCompletionResult,
    CommandLifecycleManager,
    TurnProcessingResult,
    SummarisationRequest,
    complete_answer,
)


class TestCommandLifecycleManagerUnit:
    """Unit tests for CommandLifecycleManager (mocked dependencies)."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def mock_event_writer(self):
        """Create a mock EventWriter."""
        writer = MagicMock(spec=EventWriter)
        writer.write_event.return_value = WriteResult(success=True, event_id=1)
        return writer

    @pytest.fixture
    def mock_agent(self):
        """Create a mock Agent."""
        agent = MagicMock(spec=Agent)
        agent.id = 1
        return agent

    @pytest.fixture
    def mock_command(self, mock_agent):
        """Create a mock Command."""
        command = MagicMock(spec=Command)
        command.id = 1
        command.agent_id = mock_agent.id
        command.agent = mock_agent
        command.state = CommandState.COMMANDED
        command.completed_at = None
        return command

    def test_create_command(self, mock_session, mock_event_writer, mock_agent):
        """create_command should create a command with COMMANDED state."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        # Mock the flush to set an ID
        def set_id(obj):
            if isinstance(obj, Command):
                obj.id = 42

        mock_session.add.side_effect = lambda obj: setattr(obj, 'id', 42)
        mock_session.flush.side_effect = lambda: None

        command = manager.create_command(mock_agent)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert command.agent_id == mock_agent.id
        assert command.state == CommandState.COMMANDED

    def test_create_command_writes_event(self, mock_session, mock_event_writer, mock_agent):
        """create_command should write a state_transition event."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.create_command(mock_agent)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args[1]
        assert call_kwargs["event_type"] == "state_transition"
        assert call_kwargs["payload"]["from_state"] == "idle"
        assert call_kwargs["payload"]["to_state"] == "commanded"

    def test_get_current_command(self, mock_session, mock_agent, mock_command):
        """get_current_command should return the most recent incomplete command."""
        manager = CommandLifecycleManager(session=mock_session)

        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.get_current_command(mock_agent)

        assert result == mock_command

    def test_get_current_command_none_when_all_complete(self, mock_session, mock_agent):
        """get_current_command should return None when all commands are complete."""
        manager = CommandLifecycleManager(session=mock_session)

        # Mock query chain returning None
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        result = manager.get_current_command(mock_agent)

        assert result is None

    def test_derive_agent_state_with_active_command(self, mock_session, mock_agent, mock_command):
        """derive_agent_state should return command state when active command exists."""
        manager = CommandLifecycleManager(session=mock_session)

        mock_command.state = CommandState.PROCESSING

        # Mock get_current_command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        state = manager.derive_agent_state(mock_agent)

        assert state == CommandState.PROCESSING

    def test_derive_agent_state_idle_when_no_command(self, mock_session, mock_agent):
        """derive_agent_state should return IDLE when no active command."""
        manager = CommandLifecycleManager(session=mock_session)

        # Mock get_current_command returning None
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        state = manager.derive_agent_state(mock_agent)

        assert state == CommandState.IDLE

    def test_update_command_state(self, mock_session, mock_event_writer, mock_command):
        """update_command_state should update command and write event."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.COMMANDED
        result = manager.update_command_state(
            command=mock_command,
            to_state=CommandState.PROCESSING,
            trigger="agent:progress",
        )

        assert result is True
        assert mock_command.state == CommandState.PROCESSING
        mock_event_writer.write_event.assert_called_once()

    def test_complete_command(self, mock_session, mock_event_writer, mock_command):
        """complete_command should set state to COMPLETE and timestamp."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        # Mock query chain for PROGRESS dedup check — no existing progress turn
        mock_session.query.return_value.filter_by.return_value.filter.return_value.first.return_value = None

        result = manager.complete_command(mock_command, agent_text="Command completed successfully.")

        assert result is True
        assert mock_command.state == CommandState.COMPLETE
        assert mock_command.completed_at is not None

        # Verify completion turn was created
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 1
        turn = turn_adds[0][0][0]
        assert turn.actor == TurnActor.AGENT
        assert turn.intent == TurnIntent.COMPLETION
        assert turn.command_id == mock_command.id

    def test_complete_command_does_not_send_notification(self, mock_session, mock_event_writer):
        """complete_command should NOT send notifications — hook_receiver sends them after summarisation."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_command = MagicMock()
        mock_command.id = 1
        mock_command.agent_id = mock_agent.id
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None
        mock_command.instruction = "Fix notification port mismatch"

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        with patch("claude_headspace.services.notification_service.get_notification_service") as mock_get_notif:
            manager.complete_command(mock_command, agent_text="Updated config defaults")
            mock_get_notif.assert_not_called()

    @patch("claude_headspace.services.notification_service.get_notification_service")
    def test_update_command_state_sends_awaiting_input_notification(self, mock_get_notif, mock_session, mock_event_writer):
        """update_command_state should send awaiting_input notification with context when transitioning to AWAITING_INPUT."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        # Create a mock AGENT QUESTION turn
        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.text = "Which CSS framework?"
        mock_turn.summary = None

        mock_command = MagicMock()
        mock_command.id = 1
        mock_command.agent_id = mock_agent.id
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.instruction = "Implement dark mode"
        mock_command.turns = [mock_turn]

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        manager.update_command_state(
            command=mock_command,
            to_state=CommandState.AWAITING_INPUT,
            trigger="agent:question",
        )

        mock_svc.notify_awaiting_input.assert_called_once_with(
            agent_id=str(mock_agent.id),
            agent_name="test-agent",
            project="test-project",
            command_instruction="Implement dark mode",
            turn_text="Which CSS framework?",
        )

    def test_complete_command_does_not_send_notification_even_without_instruction(self, mock_session, mock_event_writer):
        """complete_command should NOT send notifications even when instruction is None — hook_receiver handles it."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_command = MagicMock()
        mock_command.id = 1
        mock_command.agent_id = mock_agent.id
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None
        mock_command.instruction = None
        mock_command.completion_summary = None
        mock_command.turns = []

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        with patch("claude_headspace.services.notification_service.get_notification_service") as mock_get_notif:
            manager.complete_command(mock_command)
            mock_get_notif.assert_not_called()

    @patch("claude_headspace.services.notification_service.get_notification_service")
    def test_update_command_state_notification_falls_back_to_command_text(self, mock_get_notif, mock_session, mock_event_writer):
        """update_command_state notification should fall back to first USER COMMAND turn text when instruction is None."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_command_turn = MagicMock()
        mock_command_turn.actor = TurnActor.USER
        mock_command_turn.intent = TurnIntent.COMMAND
        mock_command_turn.text = "Add dark mode toggle"

        mock_question_turn = MagicMock()
        mock_question_turn.actor = TurnActor.AGENT
        mock_question_turn.intent = TurnIntent.QUESTION
        mock_question_turn.text = "Which theme library?"
        mock_question_turn.summary = None

        mock_command = MagicMock()
        mock_command.id = 1
        mock_command.agent_id = mock_agent.id
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.instruction = None  # Not yet summarised
        mock_command.turns = [mock_command_turn, mock_question_turn]

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        manager.update_command_state(
            command=mock_command,
            to_state=CommandState.AWAITING_INPUT,
            trigger="agent:question",
        )

        mock_svc.notify_awaiting_input.assert_called_once_with(
            agent_id=str(mock_agent.id),
            agent_name="test-agent",
            project="test-project",
            command_instruction="Add dark mode toggle",
            turn_text="Which theme library?",
        )

    @patch("claude_headspace.services.notification_service.get_notification_service")
    def test_update_command_state_does_not_notify_for_non_awaiting_states(self, mock_get_notif, mock_session, mock_event_writer):
        """update_command_state should NOT send notification for non-AWAITING_INPUT transitions."""
        mock_agent = MagicMock()
        mock_agent.id = 1

        mock_command = MagicMock()
        mock_command.id = 1
        mock_command.agent_id = mock_agent.id
        mock_command.agent = mock_agent
        mock_command.state = CommandState.COMMANDED

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        manager.update_command_state(
            command=mock_command,
            to_state=CommandState.PROCESSING,
            trigger="agent:progress",
        )

        mock_svc.notify_awaiting_input.assert_not_called()

    def test_process_turn_user_command_idle(self, mock_session, mock_event_writer, mock_agent):
        """User command from IDLE should create new command."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        # Mock no current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Fix the bug",
        )

        assert result.success is True
        assert result.new_command_created is True
        assert result.intent.intent == TurnIntent.COMMAND

        # Verify user command turn was created
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 1
        turn = turn_adds[0][0][0]
        assert turn.actor == TurnActor.USER
        assert turn.intent == TurnIntent.COMMAND
        assert turn.text == "Fix the bug"

    def test_process_turn_agent_progress(self, mock_session, mock_event_writer, mock_agent, mock_command):
        """Agent progress should transition from COMMANDED to PROCESSING."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.COMMANDED

        # Mock current command exists
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="I'm now working on the fix.",
        )

        assert result.success is True
        assert result.transition.valid is True
        assert result.transition.to_state == CommandState.PROCESSING

        # Verify progress turn was created
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 1
        turn = turn_adds[0][0][0]
        assert turn.actor == TurnActor.AGENT
        assert turn.intent == TurnIntent.PROGRESS
        assert turn.text == "I'm now working on the fix."

    def test_process_turn_agent_question(self, mock_session, mock_event_writer, mock_agent, mock_command):
        """Agent question should transition to AWAITING_INPUT."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.PROCESSING

        # Mock current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Should I add error handling?",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.QUESTION
        assert result.transition.to_state == CommandState.AWAITING_INPUT

    def test_process_turn_user_answer(self, mock_session, mock_event_writer, mock_agent, mock_command):
        """User answer should transition from AWAITING_INPUT to PROCESSING."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.AWAITING_INPUT

        # Mock current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Yes, please add error handling.",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.ANSWER
        assert result.transition.to_state == CommandState.PROCESSING

    def test_process_turn_agent_completion(self, mock_session, mock_event_writer, mock_agent, mock_command):
        """Agent completion should transition to COMPLETE."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        # Mock current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Done. All changes have been applied.",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.COMPLETION
        assert mock_command.state == CommandState.COMPLETE

        # process_turn delegates to complete_command without agent_text (that comes
        # from the transcript, which only hook_receiver provides). No Turn is
        # created for empty agent_text — that's correct behavior.
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 0

    def test_process_turn_user_while_awaiting_treated_as_answer(self, mock_session, mock_event_writer, mock_agent, mock_command):
        """User turn while AWAITING_INPUT is treated as ANSWER (transitions to PROCESSING).

        Note: In Epic 1 with regex-based intent detection, all user turns while
        awaiting_input are treated as answers. In Epic 3 with LLM detection, we
        could distinguish between answers and new commands.
        """
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.AWAITING_INPUT

        # Mock current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Never mind, do this instead.",
        )

        # User turn is treated as answer, transitions to PROCESSING
        assert result.success is True
        assert result.intent.intent == TurnIntent.ANSWER
        assert result.transition.to_state == CommandState.PROCESSING
        assert result.new_command_created is False

    def test_process_turn_user_answer_while_processing_continues_command(self, mock_session, mock_event_writer, mock_agent, mock_command):
        """User confirmation while PROCESSING should stay PROCESSING (no new command)."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_command.state = CommandState.PROCESSING

        # Mock current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="yes",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.ANSWER
        assert result.transition.valid is True
        assert result.transition.to_state == CommandState.PROCESSING
        assert result.new_command_created is False

    def test_process_turn_creates_turn_with_empty_text_when_none(self, mock_session, mock_event_writer, mock_agent):
        """Turn text should default to empty string when None (hook path)."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        # Mock no current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=None,  # Hooks don't provide text
        )

        assert result.success is True

        # Verify turn was created with empty string, not None
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 1
        turn = turn_adds[0][0][0]
        assert turn.text == ""

    def test_process_turn_invalid_transition(self, mock_session, mock_agent, mock_command):
        """Invalid transition should fail gracefully."""
        manager = CommandLifecycleManager(session=mock_session)

        mock_command.state = CommandState.COMPLETE  # COMPLETE is terminal — no valid outgoing transitions

        # Mock current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_command

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Progress update...",
        )

        assert result.success is False
        assert "Invalid transition" in result.error

    def test_process_turn_no_command_not_user_command(self, mock_session, mock_agent):
        """Agent turn with no active command should fail."""
        manager = CommandLifecycleManager(session=mock_session)

        # Mock no current command
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Working on it...",
        )

        assert result.success is False
        assert "No active command" in result.error


class TestUserCommandWhileCommanded:
    """Tests for USER:COMMAND while command is in COMMANDED state (Bug 1 fix).

    When a user sends a follow-up message before the agent starts,
    the turn should be attached to the existing command instead of failing.
    """

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
        agent = MagicMock()
        agent.id = 1
        return agent

    @pytest.fixture
    def mock_commanded_cmd(self, mock_agent):
        command = MagicMock()
        command.id = 10
        command.agent_id = mock_agent.id
        command.agent = mock_agent
        command.state = CommandState.COMMANDED
        command.full_command = "Fix the login bug"
        command.completed_at = None
        return command

    def test_user_command_while_commanded_attaches_to_existing_command(
        self, mock_session, mock_event_writer, mock_agent, mock_commanded_cmd
    ):
        """User COMMAND while COMMANDED should attach to existing command, not fail."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_commanded_cmd

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Also fix the logout button",
        )

        assert result.success is True
        assert result.new_command_created is False
        assert result.command == mock_commanded_cmd

        # Verify turn was created and attached to existing command
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 1
        turn = turn_adds[0][0][0]
        assert turn.actor == TurnActor.USER
        assert turn.intent == TurnIntent.COMMAND
        assert turn.text == "Also fix the logout button"
        assert turn.command_id == mock_commanded_cmd.id

    def test_user_command_while_commanded_appends_full_command(
        self, mock_session, mock_event_writer, mock_agent, mock_commanded_cmd
    ):
        """Follow-up command should append to command.full_command."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_commanded_cmd

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Also fix the logout button",
        )

        assert result.success is True
        assert mock_commanded_cmd.full_command == "Fix the login bug\nAlso fix the logout button"

    def test_multiple_user_commands_while_commanded(
        self, mock_session, mock_event_writer, mock_agent, mock_commanded_cmd
    ):
        """Multiple follow-up commands should all append."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_commanded_cmd

        # First follow-up
        result1 = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Also fix the logout button",
        )
        assert result1.success is True

        # Second follow-up
        result2 = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="And add error handling",
        )
        assert result2.success is True

        assert mock_commanded_cmd.full_command == "Fix the login bug\nAlso fix the logout button\nAnd add error handling"

        # Both turns should have been added
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 2

    def test_user_command_while_commanded_queues_summarisation(
        self, mock_session, mock_event_writer, mock_agent, mock_commanded_cmd
    ):
        """Follow-up command should queue turn + instruction summarisation."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_commanded_cmd

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Also fix the logout button",
        )

        assert result.success is True
        # Should have turn + instruction summarisation requests
        summ_types = [s.type for s in result.pending_summarisations]
        assert "turn" in summ_types
        assert "instruction" in summ_types

    def test_user_command_while_commanded_no_text(
        self, mock_session, mock_event_writer, mock_agent, mock_commanded_cmd
    ):
        """Follow-up with no text should still succeed (hook path)."""
        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_commanded_cmd

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=None,
        )

        assert result.success is True
        assert result.new_command_created is False
        # full_command should remain unchanged
        assert mock_commanded_cmd.full_command == "Fix the login bug"


class TestCommandLifecycleSessionPassThrough:
    """Tests that CommandLifecycleManager passes its session to EventWriter.

    Note: Uses MagicMock() without spec=Agent/spec=Command to avoid
    Flask app context issues (MagicMock introspects all attrs on spec classes,
    triggering db.session access on Flask-SQLAlchemy models).
    """

    def test_write_transition_event_passes_session(self):
        """_write_transition_event should pass self._session to event_writer.write_event."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock()
        mock_agent.id = 1

        mock_command = MagicMock()
        mock_command.id = 2
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.COMMANDED

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager._write_transition_event(
            agent=mock_agent,
            command=mock_command,
            from_state=CommandState.IDLE,
            to_state=CommandState.COMMANDED,
            trigger="user:command",
            confidence=1.0,
        )

        call_kwargs = mock_event_writer.write_event.call_args[1]
        assert call_kwargs["session"] is mock_session

    def test_create_command_event_uses_same_session(self):
        """create_command should write event using the same session as command creation."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock()
        mock_agent.id = 1

        mock_session.add.side_effect = lambda obj: setattr(obj, 'id', 42)

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.create_command(mock_agent)

        # Verify session was passed to write_event
        call_kwargs = mock_event_writer.write_event.call_args[1]
        assert call_kwargs["session"] is mock_session

    def test_update_command_state_event_uses_same_session(self):
        """update_command_state should write event using the same session."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock()
        mock_agent.id = 1

        mock_command = MagicMock()
        mock_command.id = 2
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.COMMANDED

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.update_command_state(
            command=mock_command,
            to_state=CommandState.PROCESSING,
            trigger="agent:progress",
        )

        call_kwargs = mock_event_writer.write_event.call_args[1]
        assert call_kwargs["session"] is mock_session


class TestCompleteCommandSummarisation:
    """Tests for summarisation request queuing in complete_command.

    Note: Uses MagicMock() without spec=Agent/spec=Command to avoid
    Flask app context issues (see TestCommandLifecycleSessionPassThrough).
    """

    def test_complete_command_queues_summarisation_requests(self):
        """complete_command should queue turn and command_completion summarisation requests."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test"

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.complete_command(mock_command, agent_text="Finished refactoring.")

        pending = manager.get_pending_summarisations()
        assert len(pending) == 2
        assert pending[0].type == "turn"
        assert pending[0].turn is not None
        assert pending[1].type == "command_completion"
        assert pending[1].command is mock_command

    def test_complete_command_no_summarisation_without_service(self):
        """complete_command should not fail when no summarisation service."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test"

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        result = manager.complete_command(mock_command)
        assert result is True

    def test_complete_command_always_succeeds(self):
        """complete_command should always succeed (summarisation is deferred)."""
        mock_session = MagicMock(spec=Session)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test"

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        manager = CommandLifecycleManager(session=mock_session)

        result = manager.complete_command(mock_command)
        assert result is True
        assert mock_command.state == CommandState.COMPLETE

    def test_complete_command_no_turn_for_empty_text(self):
        """complete_command with empty agent_text should not create a Turn."""
        mock_session = MagicMock(spec=Session)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test"

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        manager = CommandLifecycleManager(session=mock_session)

        manager.complete_command(mock_command, agent_text="")

        # No Turn should be added for empty text
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 0

        # Only command_completion summarisation (no turn summarisation)
        pending = manager.get_pending_summarisations()
        assert len(pending) == 1
        assert pending[0].type == "command_completion"

    def test_complete_command_creates_turn_for_nonempty_text(self):
        """complete_command with non-empty agent_text should create a Turn."""
        mock_session = MagicMock(spec=Session)
        # Mock query chain for PROGRESS dedup check — no existing progress turn
        mock_session.query.return_value.filter_by.return_value.filter.return_value.first.return_value = None

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.name = "test"

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        manager = CommandLifecycleManager(session=mock_session)

        manager.complete_command(mock_command, agent_text="All done.")

        # Turn should be added for non-empty text
        turn_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Turn)]
        assert len(turn_adds) == 1

        # Both turn and command_completion summarisations queued
        pending = manager.get_pending_summarisations()
        assert len(pending) == 2
        assert pending[0].type == "turn"
        assert pending[1].type == "command_completion"


class TestTurnProcessingResultDataclass:
    """Tests for TurnProcessingResult dataclass."""

    def test_success_result(self):
        """Success result should have all fields."""
        result = TurnProcessingResult(
            success=True,
            event_written=True,
            new_command_created=False,
        )
        assert result.success is True
        assert result.event_written is True
        assert result.command is None  # Optional

    def test_failure_result(self):
        """Failure result should have error field."""
        result = TurnProcessingResult(
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestStateTransitionEventPayload:
    """Tests for state_transition event payload format.

    Note: Uses MagicMock() without spec=Agent/spec=Command to avoid
    Flask app context issues (see TestCommandLifecycleSessionPassThrough).
    """

    def test_event_payload_format(self):
        """State transition event should have correct payload fields."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock()
        mock_agent.id = 1

        mock_command = MagicMock()
        mock_command.id = 2
        mock_command.agent_id = 1
        mock_command.agent = mock_agent
        mock_command.state = CommandState.PROCESSING
        mock_command.completed_at = None

        manager = CommandLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.update_command_state(
            command=mock_command,
            to_state=CommandState.AWAITING_INPUT,
            trigger="agent:question",
            confidence=0.95,
        )

        call_kwargs = mock_event_writer.write_event.call_args[1]

        # Verify payload structure
        assert call_kwargs["event_type"] == "state_transition"
        assert call_kwargs["agent_id"] == 1
        assert call_kwargs["command_id"] == 2

        payload = call_kwargs["payload"]
        assert payload["from_state"] == "processing"
        assert payload["to_state"] == "awaiting_input"
        assert payload["trigger"] == "agent:question"
        assert payload["confidence"] == 0.95


class TestCompleteAnswer:
    """Tests for the complete_answer() standalone function."""

    @pytest.fixture
    def mock_db(self):
        with patch("claude_headspace.services.command_lifecycle.db") as mock:
            mock.session = MagicMock()
            yield mock

    @pytest.fixture
    def mock_hook_state(self):
        with patch("claude_headspace.services.command_lifecycle.get_agent_hook_state") as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_broadcast_card(self):
        with patch("claude_headspace.services.command_lifecycle.broadcast_card_refresh") as mock:
            yield mock

    @pytest.fixture
    def mock_broadcaster(self):
        with patch("claude_headspace.services.command_lifecycle.get_broadcaster") as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_mark_answered(self):
        with patch("claude_headspace.services.command_lifecycle.mark_question_answered") as mock:
            yield mock

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10
        return agent

    @pytest.fixture
    def mock_command(self):
        command = MagicMock()
        command.id = 100
        command.state = CommandState.AWAITING_INPUT
        command.instruction = "Fix the bug"
        # Mock question turn for answer linking
        q_turn = MagicMock()
        q_turn.id = 500
        q_turn.actor = TurnActor.AGENT
        q_turn.intent = TurnIntent.QUESTION
        command.turns = [q_turn]
        return command

    def test_happy_path(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent, mock_command,
    ):
        """complete_answer happy path: creates turn, transitions state, commits, broadcasts."""
        result = complete_answer(mock_command, mock_agent, "yes", source="test")

        assert isinstance(result, AnswerCompletionResult)
        assert result.new_state == CommandState.PROCESSING

        # Turn was added to session
        mock_db.session.add.assert_called_once()
        turn = mock_db.session.add.call_args[0][0]
        assert turn.actor == TurnActor.USER
        assert turn.intent == TurnIntent.ANSWER
        assert turn.text == "yes"
        assert turn.timestamp_source == "user"
        assert turn.answered_by_turn_id == 500
        assert turn.file_metadata is None

        # State transition applied
        assert mock_command.state == CommandState.PROCESSING

        # Question marked answered
        mock_mark_answered.assert_called_once_with(mock_command)

        # Committed
        mock_db.session.commit.assert_called_once()

        # Hook state managed
        mock_hook_state.clear_awaiting_tool.assert_called_once_with(1)
        mock_hook_state.set_respond_pending.assert_called_once_with(1)

        # Broadcasts sent
        mock_broadcast_card.assert_called_once_with(mock_agent, "test")
        assert mock_broadcaster.broadcast.call_count == 2
        broadcast_calls = [c[0][0] for c in mock_broadcaster.broadcast.call_args_list]
        assert "state_changed" in broadcast_calls
        assert "turn_created" in broadcast_calls

    def test_file_metadata_passthrough(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent, mock_command,
    ):
        """complete_answer passes file_metadata to the Turn."""
        meta = {"original_filename": "photo.png", "stored_filename": "abc123.png"}
        result = complete_answer(
            mock_command, mock_agent, "[File: photo.png]",
            file_metadata=meta, source="file_upload",
        )

        turn = mock_db.session.add.call_args[0][0]
        assert turn.file_metadata == meta
        assert turn.text == "[File: photo.png]"

    def test_force_processing_on_invalid_transition(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent,
    ):
        """complete_answer forces PROCESSING when state machine rejects transition."""
        command = MagicMock()
        command.id = 100
        command.state = CommandState.PROCESSING  # Not AWAITING_INPUT
        command.instruction = "Do stuff"
        command.turns = []

        result = complete_answer(command, mock_agent, "answer", source="test")

        # Should force PROCESSING even though transition was invalid
        assert result.new_state == CommandState.PROCESSING
        assert command.state == CommandState.PROCESSING

    def test_no_question_turn_sets_none_answered_by(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent,
    ):
        """complete_answer sets answered_by_turn_id=None when no QUESTION turn exists."""
        command = MagicMock()
        command.id = 100
        command.state = CommandState.AWAITING_INPUT
        command.instruction = "Do stuff"
        command.turns = []  # No turns at all

        result = complete_answer(command, mock_agent, "yes", source="test")

        turn = mock_db.session.add.call_args[0][0]
        assert turn.answered_by_turn_id is None

    def test_broadcast_failure_does_not_raise(
        self, mock_db, mock_hook_state, mock_broadcast_card,
        mock_mark_answered, mock_agent, mock_command,
    ):
        """complete_answer should not raise if broadcasts fail."""
        with patch("claude_headspace.services.command_lifecycle.get_broadcaster") as mock_get:
            mock_get.return_value.broadcast.side_effect = Exception("SSE down")

            # Should NOT raise
            result = complete_answer(mock_command, mock_agent, "yes", source="test")
            assert result.new_state == CommandState.PROCESSING

    def test_respond_pending_set_after_commit(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent, mock_command,
    ):
        """set_respond_pending must be called AFTER commit (not before)."""
        call_order = []
        mock_db.session.commit.side_effect = lambda: call_order.append("commit")
        mock_hook_state.set_respond_pending.side_effect = lambda _: call_order.append("set_respond_pending")

        complete_answer(mock_command, mock_agent, "yes", source="test")

        assert call_order.index("commit") < call_order.index("set_respond_pending")

    def test_state_changed_broadcast_payload(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent, mock_command,
    ):
        """state_changed broadcast should contain source as event_type."""
        complete_answer(mock_command, mock_agent, "yes", source="voice_command")

        state_call = [
            c for c in mock_broadcaster.broadcast.call_args_list
            if c[0][0] == "state_changed"
        ][0]
        payload = state_call[0][1]
        assert payload["event_type"] == "voice_command"
        assert payload["agent_id"] == 1
        assert payload["project_id"] == 10
        assert payload["new_state"] == "processing"

    def test_turn_created_broadcast_payload(
        self, mock_db, mock_hook_state, mock_broadcast_card, mock_broadcaster,
        mock_mark_answered, mock_agent, mock_command,
    ):
        """turn_created broadcast should contain turn details."""
        complete_answer(mock_command, mock_agent, "my answer", source="respond")

        turn_call = [
            c for c in mock_broadcaster.broadcast.call_args_list
            if c[0][0] == "turn_created"
        ][0]
        payload = turn_call[0][1]
        assert payload["text"] == "my answer"
        assert payload["actor"] == "user"
        assert payload["intent"] == "answer"
        assert payload["command_id"] == 100
        assert payload["command_instruction"] == "Fix the bug"
