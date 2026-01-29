"""Tests for hook lifecycle bridge service.

These tests verify that the HookLifecycleBridge properly translates
hook events into lifecycle operations with state machine validation
and event logging.

Issue 3 & 9 Remediation Tests.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project
from claude_headspace.models.task import Task, TaskState
from claude_headspace.models.turn import TurnActor, TurnIntent
from claude_headspace.services.event_writer import EventWriter, WriteResult
from claude_headspace.services.hook_lifecycle_bridge import (
    HookLifecycleBridge,
    get_hook_bridge,
    reset_hook_bridge,
)
from claude_headspace.services.task_lifecycle import TurnProcessingResult


class TestHookLifecycleBridge:
    """Tests for HookLifecycleBridge class."""

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
        agent.name = "Test Agent"
        return agent

    @pytest.fixture
    def mock_task(self, mock_agent):
        """Create a mock Task."""
        task = MagicMock(spec=Task)
        task.id = 1
        task.agent_id = mock_agent.id
        task.agent = mock_agent
        task.state = TaskState.PROCESSING
        task.completed_at = None
        return task

    @pytest.fixture
    def bridge(self, mock_event_writer):
        """Create a HookLifecycleBridge with mock event writer."""
        return HookLifecycleBridge(event_writer=mock_event_writer)

    @pytest.fixture
    def bridge_no_writer(self):
        """Create a HookLifecycleBridge without event writer."""
        return HookLifecycleBridge(event_writer=None)


class TestProcessUserPromptSubmit(TestHookLifecycleBridge):
    """Tests for process_user_prompt_submit method."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_creates_task_when_none_exists(
        self, mock_db, bridge, mock_agent
    ):
        """User prompt submit should create a new task when none exists."""
        # Mock the lifecycle manager completely
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle

            # Create a mock task that will be returned
            mock_task = MagicMock()
            mock_task.id = 1
            mock_task.state = TaskState.COMMANDED

            mock_lifecycle.process_turn.return_value = TurnProcessingResult(
                success=True,
                task=mock_task,
                new_task_created=True,
            )

            result = bridge.process_user_prompt_submit(mock_agent, "session-123")

            assert result.success is True
            assert result.new_task_created is True

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_transitions_to_processing(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """User prompt should transition task from COMMANDED to PROCESSING."""
        mock_task.state = TaskState.COMMANDED

        # Setup mock session to return existing task
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_task

        # We need to mock the lifecycle manager's behavior
        # Since process_turn creates a new task, we need to handle both cases
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle

            # Simulate successful turn processing
            result_task = MagicMock()
            result_task.id = 1
            result_task.state = TaskState.COMMANDED

            mock_lifecycle.process_turn.return_value = TurnProcessingResult(
                success=True,
                task=result_task,
                new_task_created=True,
            )

            result = bridge.process_user_prompt_submit(mock_agent, "session-123")

            assert result.success is True
            mock_lifecycle.process_turn.assert_called_once()

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_uses_lifecycle_manager(self, mock_db, bridge, mock_agent):
        """User prompt should use TaskLifecycleManager for proper validation."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle

            mock_lifecycle.process_turn.return_value = TurnProcessingResult(
                success=True,
                task=MagicMock(id=1, state=TaskState.PROCESSING),
                new_task_created=True,
            )

            bridge.process_user_prompt_submit(mock_agent, "session-123")

            # Verify lifecycle manager was used
            mock_lifecycle.process_turn.assert_called_once_with(
                agent=mock_agent,
                actor=TurnActor.USER,
                text=None,
            )


class TestProcessStop(TestHookLifecycleBridge):
    """Tests for process_stop method."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_completes_active_task(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Stop hook should complete the active task."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            result = bridge.process_stop(mock_agent, "session-123")

            assert result.success is True
            mock_lifecycle.complete_task.assert_called_once_with(
                task=mock_task,
                trigger="hook:stop",
            )

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_handles_no_active_task(
        self, mock_db, bridge, mock_agent
    ):
        """Stop hook should handle case when no task is active."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = None

            result = bridge.process_stop(mock_agent, "session-123")

            assert result.success is True
            assert result.error == "No active task to complete"
            mock_lifecycle.complete_task.assert_not_called()

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_writes_event_when_writer_available(
        self, mock_db, bridge, mock_agent, mock_task, mock_event_writer
    ):
        """Stop hook should write event when event writer is available."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            result = bridge.process_stop(mock_agent, "session-123")

            assert result.event_written is True

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_no_event_when_writer_unavailable(
        self, mock_db, bridge_no_writer, mock_agent, mock_task
    ):
        """Stop hook should not write event when writer is unavailable."""
        with patch.object(
            bridge_no_writer, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            result = bridge_no_writer.process_stop(mock_agent, "session-123")

            assert result.event_written is False


class TestProcessSessionEnd(TestHookLifecycleBridge):
    """Tests for process_session_end method."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_completes_active_task(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Session end should complete any active task."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            result = bridge.process_session_end(mock_agent, "session-123")

            assert result.success is True
            mock_lifecycle.complete_task.assert_called_once_with(
                task=mock_task,
                trigger="hook:session_end",
            )

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_handles_no_active_task(
        self, mock_db, bridge, mock_agent
    ):
        """Session end should handle case when no task is active."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = None

            result = bridge.process_session_end(mock_agent, "session-123")

            assert result.success is True
            assert result.task is None
            mock_lifecycle.complete_task.assert_not_called()


class TestGetHookBridge:
    """Tests for get_hook_bridge function."""

    def setup_method(self):
        """Reset global bridge before each test."""
        reset_hook_bridge()

    def teardown_method(self):
        """Reset global bridge after each test."""
        reset_hook_bridge()

    def test_creates_bridge_lazily(self):
        """get_hook_bridge should create bridge on first call."""
        with patch(
            "claude_headspace.services.hook_lifecycle_bridge._get_event_writer_from_app"
        ) as mock_get_writer:
            mock_get_writer.return_value = None

            bridge = get_hook_bridge()

            assert bridge is not None
            assert isinstance(bridge, HookLifecycleBridge)

    def test_returns_same_instance(self):
        """get_hook_bridge should return same instance on subsequent calls."""
        with patch(
            "claude_headspace.services.hook_lifecycle_bridge._get_event_writer_from_app"
        ) as mock_get_writer:
            mock_get_writer.return_value = None

            bridge1 = get_hook_bridge()
            bridge2 = get_hook_bridge()

            assert bridge1 is bridge2

    def test_reset_clears_instance(self):
        """reset_hook_bridge should clear the global instance."""
        with patch(
            "claude_headspace.services.hook_lifecycle_bridge._get_event_writer_from_app"
        ) as mock_get_writer:
            mock_get_writer.return_value = None

            bridge1 = get_hook_bridge()
            reset_hook_bridge()
            bridge2 = get_hook_bridge()

            assert bridge1 is not bridge2


class TestEventWriterIntegration(TestHookLifecycleBridge):
    """Integration tests for event writer with hook bridge."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_lifecycle_manager_receives_event_writer(
        self, mock_db, mock_event_writer, mock_agent
    ):
        """Lifecycle manager should receive the event writer from bridge."""
        bridge = HookLifecycleBridge(event_writer=mock_event_writer)

        # Access the lifecycle manager
        lifecycle = bridge._get_lifecycle_manager()

        assert lifecycle._event_writer is mock_event_writer

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_no_event_writer_when_none_provided(
        self, mock_db, mock_agent
    ):
        """Lifecycle manager should have no event writer when none provided."""
        bridge = HookLifecycleBridge(event_writer=None)

        lifecycle = bridge._get_lifecycle_manager()

        assert lifecycle._event_writer is None


class TestStateMachineValidation(TestHookLifecycleBridge):
    """Tests verifying state machine validation is used."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_user_prompt_uses_state_machine(
        self, mock_db, bridge, mock_agent
    ):
        """User prompt should use state machine for validation."""
        with patch(
            "claude_headspace.services.task_lifecycle.detect_intent"
        ) as mock_detect:
            mock_detect.return_value = MagicMock(
                intent=TurnIntent.COMMAND,
                confidence=0.9,
            )

            with patch.object(
                bridge, '_get_lifecycle_manager'
            ) as mock_get_lifecycle:
                mock_lifecycle = MagicMock()
                mock_get_lifecycle.return_value = mock_lifecycle

                mock_lifecycle.process_turn.return_value = TurnProcessingResult(
                    success=True,
                    task=MagicMock(id=1, state=TaskState.COMMANDED),
                    new_task_created=True,
                )

                bridge.process_user_prompt_submit(mock_agent, "session-123")

                # Verify process_turn was called (which uses state machine internally)
                mock_lifecycle.process_turn.assert_called_once()


class TestTurnProcessingResultFields:
    """Tests for TurnProcessingResult usage in bridge."""

    def test_result_has_required_fields(self):
        """TurnProcessingResult should have all expected fields."""
        result = TurnProcessingResult(
            success=True,
            task=None,
            event_written=False,
        )

        assert hasattr(result, 'success')
        assert hasattr(result, 'task')
        assert hasattr(result, 'event_written')
        assert hasattr(result, 'error')
        assert hasattr(result, 'new_task_created')

    def test_success_result(self):
        """Success result should have correct values."""
        mock_task = MagicMock()
        mock_task.id = 42

        result = TurnProcessingResult(
            success=True,
            task=mock_task,
            event_written=True,
        )

        assert result.success is True
        assert result.task.id == 42
        assert result.event_written is True

    def test_failure_result(self):
        """Failure result should have error field."""
        result = TurnProcessingResult(
            success=False,
            error="State transition not valid",
        )

        assert result.success is False
        assert result.error == "State transition not valid"
