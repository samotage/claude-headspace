"""Tests for task lifecycle manager service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project
from claude_headspace.models.task import Task, TaskState
from claude_headspace.models.turn import TurnActor, TurnIntent
from claude_headspace.services.event_writer import EventWriter, WriteResult
from claude_headspace.services.state_machine import StateMachine, TransitionResult
from claude_headspace.services.task_lifecycle import TaskLifecycleManager, TurnProcessingResult


class TestTaskLifecycleManagerUnit:
    """Unit tests for TaskLifecycleManager (mocked dependencies)."""

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
    def mock_task(self, mock_agent):
        """Create a mock Task."""
        task = MagicMock(spec=Task)
        task.id = 1
        task.agent_id = mock_agent.id
        task.agent = mock_agent
        task.state = TaskState.COMMANDED
        task.completed_at = None
        return task

    def test_create_task(self, mock_session, mock_event_writer, mock_agent):
        """create_task should create a task with COMMANDED state."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        # Mock the flush to set an ID
        def set_id(obj):
            if isinstance(obj, Task):
                obj.id = 42

        mock_session.add.side_effect = lambda obj: setattr(obj, 'id', 42)
        mock_session.flush.side_effect = lambda: None

        task = manager.create_task(mock_agent)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert task.agent_id == mock_agent.id
        assert task.state == TaskState.COMMANDED

    def test_create_task_writes_event(self, mock_session, mock_event_writer, mock_agent):
        """create_task should write a state_transition event."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.create_task(mock_agent)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args[1]
        assert call_kwargs["event_type"] == "state_transition"
        assert call_kwargs["payload"]["from_state"] == "idle"
        assert call_kwargs["payload"]["to_state"] == "commanded"

    def test_get_current_task(self, mock_session, mock_agent, mock_task):
        """get_current_task should return the most recent incomplete task."""
        manager = TaskLifecycleManager(session=mock_session)

        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.get_current_task(mock_agent)

        assert result == mock_task

    def test_get_current_task_none_when_all_complete(self, mock_session, mock_agent):
        """get_current_task should return None when all tasks are complete."""
        manager = TaskLifecycleManager(session=mock_session)

        # Mock query chain returning None
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        result = manager.get_current_task(mock_agent)

        assert result is None

    def test_derive_agent_state_with_active_task(self, mock_session, mock_agent, mock_task):
        """derive_agent_state should return task state when active task exists."""
        manager = TaskLifecycleManager(session=mock_session)

        mock_task.state = TaskState.PROCESSING

        # Mock get_current_task
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        state = manager.derive_agent_state(mock_agent)

        assert state == TaskState.PROCESSING

    def test_derive_agent_state_idle_when_no_task(self, mock_session, mock_agent):
        """derive_agent_state should return IDLE when no active task."""
        manager = TaskLifecycleManager(session=mock_session)

        # Mock get_current_task returning None
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        state = manager.derive_agent_state(mock_agent)

        assert state == TaskState.IDLE

    def test_update_task_state(self, mock_session, mock_event_writer, mock_task):
        """update_task_state should update task and write event."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.COMMANDED
        result = manager.update_task_state(
            task=mock_task,
            to_state=TaskState.PROCESSING,
            trigger="agent:progress",
        )

        assert result is True
        assert mock_task.state == TaskState.PROCESSING
        mock_event_writer.write_event.assert_called_once()

    def test_complete_task(self, mock_session, mock_event_writer, mock_task):
        """complete_task should set state to COMPLETE and timestamp."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.PROCESSING
        mock_task.completed_at = None

        result = manager.complete_task(mock_task)

        assert result is True
        assert mock_task.state == TaskState.COMPLETE
        assert mock_task.completed_at is not None

    def test_process_turn_user_command_idle(self, mock_session, mock_event_writer, mock_agent):
        """User command from IDLE should create new task."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        # Mock no current task
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
        assert result.new_task_created is True
        assert result.intent.intent == TurnIntent.COMMAND

    def test_process_turn_agent_progress(self, mock_session, mock_event_writer, mock_agent, mock_task):
        """Agent progress should transition from COMMANDED to PROCESSING."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.COMMANDED

        # Mock current task exists
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="I'm now working on the fix.",
        )

        assert result.success is True
        assert result.transition.valid is True
        assert result.transition.to_state == TaskState.PROCESSING

    def test_process_turn_agent_question(self, mock_session, mock_event_writer, mock_agent, mock_task):
        """Agent question should transition to AWAITING_INPUT."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.PROCESSING

        # Mock current task
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Should I add error handling?",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.QUESTION
        assert result.transition.to_state == TaskState.AWAITING_INPUT

    def test_process_turn_user_answer(self, mock_session, mock_event_writer, mock_agent, mock_task):
        """User answer should transition from AWAITING_INPUT to PROCESSING."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.AWAITING_INPUT

        # Mock current task
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Yes, please add error handling.",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.ANSWER
        assert result.transition.to_state == TaskState.PROCESSING

    def test_process_turn_agent_completion(self, mock_session, mock_event_writer, mock_agent, mock_task):
        """Agent completion should transition to COMPLETE."""
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.PROCESSING
        mock_task.completed_at = None

        # Mock current task
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Done. All changes have been applied.",
        )

        assert result.success is True
        assert result.intent.intent == TurnIntent.COMPLETION
        assert mock_task.state == TaskState.COMPLETE

    def test_process_turn_user_while_awaiting_treated_as_answer(self, mock_session, mock_event_writer, mock_agent, mock_task):
        """User turn while AWAITING_INPUT is treated as ANSWER (transitions to PROCESSING).

        Note: In Epic 1 with regex-based intent detection, all user turns while
        awaiting_input are treated as answers. In Epic 3 with LLM detection, we
        could distinguish between answers and new commands.
        """
        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        mock_task.state = TaskState.AWAITING_INPUT

        # Mock current task
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text="Never mind, do this instead.",
        )

        # User turn is treated as answer, transitions to PROCESSING
        assert result.success is True
        assert result.intent.intent == TurnIntent.ANSWER
        assert result.transition.to_state == TaskState.PROCESSING
        assert result.new_task_created is False

    def test_process_turn_invalid_transition(self, mock_session, mock_agent, mock_task):
        """Invalid transition should fail gracefully."""
        manager = TaskLifecycleManager(session=mock_session)

        mock_task.state = TaskState.IDLE  # Invalid state for agent action

        # Mock current task
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.AGENT,
            text="Progress update...",
        )

        assert result.success is False
        assert "Invalid transition" in result.error

    def test_process_turn_no_task_not_command(self, mock_session, mock_agent):
        """Agent turn with no active task should fail."""
        manager = TaskLifecycleManager(session=mock_session)

        # Mock no current task
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
        assert "No active task" in result.error


class TestTurnProcessingResultDataclass:
    """Tests for TurnProcessingResult dataclass."""

    def test_success_result(self):
        """Success result should have all fields."""
        result = TurnProcessingResult(
            success=True,
            event_written=True,
            new_task_created=False,
        )
        assert result.success is True
        assert result.event_written is True
        assert result.task is None  # Optional

    def test_failure_result(self):
        """Failure result should have error field."""
        result = TurnProcessingResult(
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestStateTransitionEventPayload:
    """Tests for state_transition event payload format."""

    def test_event_payload_format(self):
        """State transition event should have correct payload fields."""
        mock_session = MagicMock(spec=Session)
        mock_event_writer = MagicMock(spec=EventWriter)
        mock_event_writer.write_event.return_value = WriteResult(success=True, event_id=1)

        mock_agent = MagicMock(spec=Agent)
        mock_agent.id = 1

        mock_task = MagicMock(spec=Task)
        mock_task.id = 2
        mock_task.agent_id = 1
        mock_task.agent = mock_agent
        mock_task.state = TaskState.PROCESSING
        mock_task.completed_at = None

        manager = TaskLifecycleManager(
            session=mock_session,
            event_writer=mock_event_writer,
        )

        manager.update_task_state(
            task=mock_task,
            to_state=TaskState.AWAITING_INPUT,
            trigger="agent:question",
            confidence=0.95,
        )

        call_kwargs = mock_event_writer.write_event.call_args[1]

        # Verify payload structure
        assert call_kwargs["event_type"] == "state_transition"
        assert call_kwargs["agent_id"] == 1
        assert call_kwargs["task_id"] == 2

        payload = call_kwargs["payload"]
        assert payload["from_state"] == "processing"
        assert payload["to_state"] == "awaiting_input"
        assert payload["trigger"] == "agent:question"
        assert payload["confidence"] == 0.95
