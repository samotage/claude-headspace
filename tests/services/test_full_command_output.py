"""Tests for full_command and full_output capture (e5-s9).

Tests cover:
- Task model fields (nullable, creation)
- TaskLifecycleManager.process_turn() persists full_command
- TaskLifecycleManager.complete_task() persists full_output
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from claude_headspace.models.agent import Agent
from claude_headspace.models.task import Task, TaskState
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent
from claude_headspace.services.event_writer import EventWriter, WriteResult
from claude_headspace.services.task_lifecycle import TaskLifecycleManager


class TestTaskModelFullTextFields:
    """Task 3.1: Unit tests for Task model new fields."""

    def test_full_command_field_exists(self):
        """Task model should have full_command field."""
        task = Task.__table__
        assert "full_command" in task.columns

    def test_full_output_field_exists(self):
        """Task model should have full_output field."""
        task = Task.__table__
        assert "full_output" in task.columns

    def test_full_command_is_nullable(self):
        """full_command should be nullable."""
        col = Task.__table__.columns["full_command"]
        assert col.nullable is True

    def test_full_output_is_nullable(self):
        """full_output should be nullable."""
        col = Task.__table__.columns["full_output"]
        assert col.nullable is True

    def test_full_command_defaults_to_none(self):
        """full_command should default to None on new Task."""
        task = Task(agent_id=1, state=TaskState.COMMANDED)
        assert task.full_command is None

    def test_full_output_defaults_to_none(self):
        """full_output should default to None on new Task."""
        task = Task(agent_id=1, state=TaskState.COMMANDED)
        assert task.full_output is None


class TestProcessTurnFullCommand:
    """Task 3.2: process_turn() persists full_command on new tasks."""

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

    def _setup_no_current_task(self, mock_session):
        """Configure mock session to return no current task."""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

    def test_full_command_persisted_on_new_task(self, mock_session, mock_event_writer, mock_agent):
        """User command should persist full text to task.full_command."""
        manager = TaskLifecycleManager(session=mock_session, event_writer=mock_event_writer)
        self._setup_no_current_task(mock_session)

        command_text = "Please refactor the authentication module to use JWT tokens instead of session cookies"

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=command_text,
        )

        assert result.success is True
        assert result.new_task_created is True

        # Find the Task object that was added to session
        task_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Task)]
        assert len(task_adds) == 1
        task = task_adds[0][0][0]
        assert task.full_command == command_text

    def test_full_command_not_set_when_text_is_none(self, mock_session, mock_event_writer, mock_agent):
        """full_command should not be set when text is None (hook path)."""
        manager = TaskLifecycleManager(session=mock_session, event_writer=mock_event_writer)
        self._setup_no_current_task(mock_session)

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=None,
        )

        assert result.success is True
        # Task was created but full_command stays at default (None)
        task_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Task)]
        assert len(task_adds) == 1
        task = task_adds[0][0][0]
        assert task.full_command is None

    def test_full_command_preserves_long_text(self, mock_session, mock_event_writer, mock_agent):
        """full_command should preserve very long command text without truncation."""
        manager = TaskLifecycleManager(session=mock_session, event_writer=mock_event_writer)
        self._setup_no_current_task(mock_session)

        long_text = "Fix the bug " * 500  # ~6500 chars

        result = manager.process_turn(
            agent=mock_agent,
            actor=TurnActor.USER,
            text=long_text,
        )

        assert result.success is True
        task_adds = [c for c in mock_session.add.call_args_list if isinstance(c[0][0], Task)]
        task = task_adds[0][0][0]
        assert task.full_command == long_text


class TestCompleteTaskFullOutput:
    """Task 3.3: complete_task() persists full_output."""

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
    def mock_task(self):
        task = MagicMock(spec=Task)
        task.id = 1
        task.agent_id = 1
        task.agent = MagicMock(spec=Agent)
        task.agent.id = 1
        task.state = TaskState.PROCESSING
        task.completed_at = None
        task.full_output = None
        return task

    def test_full_output_persisted_on_completion(self, mock_session, mock_event_writer, mock_task):
        """complete_task should persist agent_text to task.full_output."""
        manager = TaskLifecycleManager(session=mock_session, event_writer=mock_event_writer)

        agent_text = "Done. I've refactored the auth module to use JWT. Changes:\n1. Added jwt_utils.py\n2. Updated middleware"

        manager.complete_task(mock_task, agent_text=agent_text)

        assert mock_task.full_output == agent_text
        assert mock_task.state == TaskState.COMPLETE

    def test_full_output_not_set_when_agent_text_empty(self, mock_session, mock_event_writer, mock_task):
        """full_output should not be set when agent_text is empty string."""
        manager = TaskLifecycleManager(session=mock_session, event_writer=mock_event_writer)

        manager.complete_task(mock_task, agent_text="")

        # Empty string is falsy, so full_output won't be set
        assert mock_task.full_output is None
        assert mock_task.state == TaskState.COMPLETE

    def test_full_output_preserves_long_text(self, mock_session, mock_event_writer, mock_task):
        """full_output should preserve very long output text."""
        manager = TaskLifecycleManager(session=mock_session, event_writer=mock_event_writer)

        long_output = "I've completed the implementation. " * 500

        manager.complete_task(mock_task, agent_text=long_output)

        assert mock_task.full_output == long_output
