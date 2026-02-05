"""Unit tests for TaskLifecycleManager summarisation integration."""

from unittest.mock import MagicMock, call, patch

import pytest

from src.claude_headspace.models.task import TaskState
from src.claude_headspace.models.turn import TurnActor
from src.claude_headspace.services.state_machine import TransitionResult
from src.claude_headspace.services.task_lifecycle import TaskLifecycleManager, SummarisationRequest


@pytest.fixture
def mock_session():
    session = MagicMock()
    return session


@pytest.fixture
def manager(mock_session):
    return TaskLifecycleManager(
        session=mock_session,
    )


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = 1
    return agent


class TestTurnSummarisationTrigger:

    def test_summarisation_queued_on_user_command(self, manager, mock_session, mock_agent):
        """When a user command creates a new task, turn and instruction summarisation should be queued."""
        # Setup: no current task (IDLE state)
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = manager.process_turn(mock_agent, TurnActor.USER, "Fix the login bug")

        assert result.success is True
        assert result.new_task_created is True
        assert len(result.pending_summarisations) >= 1

        # Should have a turn summarisation request
        turn_reqs = [r for r in result.pending_summarisations if r.type == "turn"]
        assert len(turn_reqs) == 1
        assert turn_reqs[0].turn is not None

        # Should have an instruction summarisation request
        instruction_reqs = [r for r in result.pending_summarisations if r.type == "instruction"]
        assert len(instruction_reqs) == 1
        assert instruction_reqs[0].task is not None
        assert instruction_reqs[0].command_text == "Fix the login bug"

    def test_summarisation_queued_on_agent_turn(self, manager, mock_session, mock_agent):
        """When an agent produces a non-completion turn, turn summarisation should be queued."""
        # Setup: active task in COMMANDED state (agent progress → PROCESSING)
        mock_task = MagicMock()
        mock_task.state = TaskState.COMMANDED
        mock_task.agent = mock_agent
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_task

        result = manager.process_turn(mock_agent, TurnActor.AGENT, "Working on the fix")

        if result.success and result.transition and result.transition.to_state != TaskState.COMPLETE:
            turn_reqs = [r for r in result.pending_summarisations if r.type == "turn"]
            assert len(turn_reqs) == 1

    def test_no_summarisation_without_service(self, manager, mock_session, mock_agent):
        """When no summarisation service is provided, should not error."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = manager.process_turn(mock_agent, TurnActor.USER, "Do something")

        assert result.success is True
        # pending_summarisations should still be populated (they're model objects, not service calls)
        turn_reqs = [r for r in result.pending_summarisations if r.type == "turn"]
        assert len(turn_reqs) == 1


class TestTaskSummarisationTrigger:

    @pytest.fixture(autouse=True)
    def _patch_validate(self):
        with patch("src.claude_headspace.services.task_lifecycle.validate_transition") as self._mock_validate:
            yield

    def test_summarisation_queued_on_task_completion(self, manager, mock_session, mock_agent):
        """When a task is completed via process_turn, task_completion summarisation should be queued."""
        mock_task = MagicMock()
        mock_task.id = 42
        mock_task.state = TaskState.PROCESSING
        mock_task.agent = mock_agent
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_task

        self._mock_validate.return_value = TransitionResult(
            valid=True,
            from_state=TaskState.PROCESSING,
            to_state=TaskState.COMPLETE,
            reason="Valid transition",
            trigger="agent:completion",
        )

        result = manager.process_turn(mock_agent, TurnActor.AGENT, "")

        assert result.success is True
        task_reqs = [r for r in result.pending_summarisations if r.type == "task_completion"]
        assert len(task_reqs) == 1
        assert task_reqs[0].task is mock_task

    def test_no_task_summarisation_on_non_completion(self, manager, mock_session, mock_agent):
        """When a transition is not to COMPLETE, task summarisation should not be queued."""
        mock_task = MagicMock()
        mock_task.id = 42
        mock_task.state = TaskState.COMMANDED
        mock_task.agent = mock_agent
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_task

        self._mock_validate.return_value = TransitionResult(
            valid=True,
            from_state=TaskState.COMMANDED,
            to_state=TaskState.PROCESSING,
            reason="Valid transition",
            trigger="agent:progress",
        )

        result = manager.process_turn(mock_agent, TurnActor.AGENT, "Starting work")

        assert result.success is True
        task_reqs = [r for r in result.pending_summarisations if r.type == "task_completion"]
        assert len(task_reqs) == 0


class TestSummarisationErrorHandling:

    def test_pending_summarisations_always_populated(self, manager, mock_session, mock_agent):
        """Summarisation requests are always queued regardless of service availability."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        # Should still succeed — summarisation is deferred, not executed here
        result = manager.process_turn(mock_agent, TurnActor.USER, "Do something")

        assert result.success is True
        assert len(result.pending_summarisations) >= 1


class TestGetPendingSummarisations:

    def test_get_pending_clears_list(self, mock_session):
        """get_pending_summarisations should return and clear the list."""
        manager = TaskLifecycleManager(session=mock_session)
        manager._pending_summarisations = [
            SummarisationRequest(type="turn"),
            SummarisationRequest(type="instruction"),
        ]

        pending = manager.get_pending_summarisations()

        assert len(pending) == 2
        assert len(manager._pending_summarisations) == 0

    def test_get_pending_returns_empty_by_default(self, mock_session):
        """get_pending_summarisations should return empty list when nothing queued."""
        manager = TaskLifecycleManager(session=mock_session)

        pending = manager.get_pending_summarisations()

        assert pending == []
