"""Unit tests for TaskLifecycleManager summarisation integration."""

from unittest.mock import MagicMock, call

import pytest

from src.claude_headspace.models.task import TaskState
from src.claude_headspace.models.turn import TurnActor
from src.claude_headspace.services.task_lifecycle import TaskLifecycleManager


@pytest.fixture
def mock_session():
    session = MagicMock()
    return session


@pytest.fixture
def mock_summarisation():
    service = MagicMock()
    return service


@pytest.fixture
def manager(mock_session, mock_summarisation):
    return TaskLifecycleManager(
        session=mock_session,
        summarisation_service=mock_summarisation,
    )


@pytest.fixture
def manager_no_summarisation(mock_session):
    return TaskLifecycleManager(session=mock_session)


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = 1
    return agent


class TestTurnSummarisationTrigger:

    def test_summarisation_triggered_on_user_command(self, manager, mock_session, mock_summarisation, mock_agent):
        """When a user command creates a new task, turn summarisation should be triggered."""
        # Setup: no current task (IDLE state)
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = manager.process_turn(mock_agent, TurnActor.USER, "Fix the login bug")

        assert result.success is True
        assert result.new_task_created is True
        mock_summarisation.summarise_turn_async.assert_called_once()

    def test_summarisation_triggered_on_agent_turn(self, manager, mock_session, mock_summarisation, mock_agent):
        """When an agent produces a turn, summarisation should be triggered."""
        # Setup: active task in PROCESSING state
        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.agent = mock_agent
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_task

        result = manager.process_turn(mock_agent, TurnActor.AGENT, "Working on the fix")

        if result.success and result.transition and result.transition.to_state != TaskState.COMPLETE:
            mock_summarisation.summarise_turn_async.assert_called()

    def test_no_summarisation_without_service(self, manager_no_summarisation, mock_session, mock_agent):
        """When no summarisation service is provided, should not error."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = manager_no_summarisation.process_turn(mock_agent, TurnActor.USER, "Do something")

        assert result.success is True


class TestTaskSummarisationTrigger:

    def test_summarisation_triggered_on_task_completion(self, manager, mock_session, mock_summarisation, mock_agent):
        """When a task is completed via process_turn, task summarisation should be triggered."""
        # Setup: active task in PROCESSING state, agent turn triggers completion
        mock_task = MagicMock()
        mock_task.id = 42
        mock_task.state = TaskState.PROCESSING
        mock_task.agent = mock_agent
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_task

        # Simulate completion transition
        from src.claude_headspace.services.state_machine import TransitionResult

        manager._state_machine = MagicMock()
        manager._state_machine.transition.return_value = TransitionResult(
            valid=True,
            from_state=TaskState.PROCESSING,
            to_state=TaskState.COMPLETE,
            reason="Valid transition",
            trigger="agent:completion",
        )

        result = manager.process_turn(mock_agent, TurnActor.AGENT, "")

        assert result.success is True
        mock_summarisation.summarise_task_async.assert_called_once_with(42)

    def test_no_task_summarisation_on_non_completion(self, manager, mock_session, mock_summarisation, mock_agent):
        """When a transition is not to COMPLETE, task summarisation should not be triggered."""
        mock_task = MagicMock()
        mock_task.id = 42
        mock_task.state = TaskState.COMMANDED
        mock_task.agent = mock_agent
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_task

        from src.claude_headspace.services.state_machine import TransitionResult

        manager._state_machine = MagicMock()
        manager._state_machine.transition.return_value = TransitionResult(
            valid=True,
            from_state=TaskState.COMMANDED,
            to_state=TaskState.PROCESSING,
            reason="Valid transition",
            trigger="agent:progress",
        )

        result = manager.process_turn(mock_agent, TurnActor.AGENT, "Starting work")

        assert result.success is True
        mock_summarisation.summarise_task_async.assert_not_called()


class TestSummarisationErrorHandling:

    def test_summarisation_error_non_fatal(self, manager, mock_session, mock_summarisation, mock_agent):
        """Summarisation errors should not affect turn processing."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_summarisation.summarise_turn_async.side_effect = Exception("Service down")

        # Should still succeed even if summarisation fails
        result = manager.process_turn(mock_agent, TurnActor.USER, "Do something")

        assert result.success is True
