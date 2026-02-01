"""Tests for hook receiver service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.hook_receiver import (
    HookEventResult,
    HookEventType,
    HookMode,
    HookReceiverState,
    configure_receiver,
    get_receiver_state,
    process_notification,
    process_session_end,
    process_session_start,
    process_stop,
    process_user_prompt_submit,
)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.id = 1
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.state.value = "idle"
    agent.get_current_task.return_value = None
    return agent


@pytest.fixture
def fresh_state():
    """Reset receiver state before each test."""
    state = get_receiver_state()
    state.enabled = True
    state.last_event_at = None
    state.last_event_type = None
    state.mode = HookMode.POLLING_FALLBACK
    state.events_received = 0
    yield state


class TestHookEventType:
    """Tests for HookEventType enum."""

    def test_event_types_are_strings(self):
        """Event types should be string values."""
        assert HookEventType.SESSION_START == "session_start"
        assert HookEventType.SESSION_END == "session_end"
        assert HookEventType.USER_PROMPT_SUBMIT == "user_prompt_submit"
        assert HookEventType.STOP == "stop"
        assert HookEventType.NOTIFICATION == "notification"


class TestHookMode:
    """Tests for HookMode enum."""

    def test_mode_values(self):
        """Mode values should be strings."""
        assert HookMode.HOOKS_ACTIVE == "hooks_active"
        assert HookMode.POLLING_FALLBACK == "polling_fallback"


class TestHookReceiverState:
    """Tests for HookReceiverState."""

    def test_record_event_updates_timestamp(self, fresh_state):
        """Recording an event should update the timestamp."""
        assert fresh_state.last_event_at is None

        fresh_state.record_event(HookEventType.SESSION_START)

        assert fresh_state.last_event_at is not None
        assert fresh_state.last_event_type == HookEventType.SESSION_START
        assert fresh_state.events_received == 1

    def test_record_event_switches_to_hooks_active(self, fresh_state):
        """Recording an event should switch to hooks active mode."""
        assert fresh_state.mode == HookMode.POLLING_FALLBACK

        fresh_state.record_event(HookEventType.NOTIFICATION)

        assert fresh_state.mode == HookMode.HOOKS_ACTIVE

    def test_check_fallback_after_timeout(self, fresh_state):
        """Should fall back to polling after timeout."""
        # Set last event to be old
        fresh_state.mode = HookMode.HOOKS_ACTIVE
        fresh_state.last_event_at = datetime(2020, 1, 1, tzinfo=timezone.utc)

        fresh_state.check_fallback()

        assert fresh_state.mode == HookMode.POLLING_FALLBACK

    def test_get_polling_interval_hooks_active(self, fresh_state):
        """Should return long interval when hooks are active."""
        fresh_state.mode = HookMode.HOOKS_ACTIVE

        assert fresh_state.get_polling_interval() == 60

    def test_get_polling_interval_fallback(self, fresh_state):
        """Should return short interval in fallback mode."""
        fresh_state.mode = HookMode.POLLING_FALLBACK

        assert fresh_state.get_polling_interval() == 2


class TestConfigureReceiver:
    """Tests for configure_receiver function."""

    def test_configure_enabled(self, fresh_state):
        """Test configuring enabled state."""
        configure_receiver(enabled=False)
        assert fresh_state.enabled is False

        configure_receiver(enabled=True)
        assert fresh_state.enabled is True

    def test_configure_polling_interval(self, fresh_state):
        """Test configuring polling interval."""
        configure_receiver(polling_interval_with_hooks=120)
        assert fresh_state.polling_interval_with_hooks == 120

    def test_configure_fallback_timeout(self, fresh_state):
        """Test configuring fallback timeout."""
        configure_receiver(fallback_timeout=600)
        assert fresh_state.fallback_timeout == 600


class TestProcessSessionStart:
    """Tests for process_session_start function."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_session_start(self, mock_db, mock_agent, fresh_state):
        """Test successful session start processing."""
        result = process_session_start(mock_agent, "session-123")

        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is False
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_session_start_updates_timestamp(self, mock_db, mock_agent, fresh_state):
        """Session start should update agent timestamp."""
        old_time = mock_agent.last_seen_at

        process_session_start(mock_agent, "session-123")

        assert mock_agent.last_seen_at >= old_time

    @patch("claude_headspace.services.hook_receiver.db")
    def test_session_start_records_event(self, mock_db, mock_agent, fresh_state):
        """Session start should record the event."""
        process_session_start(mock_agent, "session-123")

        assert fresh_state.last_event_type == HookEventType.SESSION_START
        assert fresh_state.events_received == 1


class TestProcessSessionEnd:
    """Tests for process_session_end function."""

    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_session_end(self, mock_db, mock_get_bridge, mock_agent, fresh_state):
        """Test successful session end processing."""
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        # Mock the bridge
        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_session_end.return_value = TurnProcessingResult(
            success=True,
            task=None,
        )

        result = process_session_end(mock_agent, "session-123")

        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is True
        mock_db.session.commit.assert_called_once()


class TestProcessUserPromptSubmit:
    """Tests for process_user_prompt_submit function."""

    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_task_when_none_exists(
        self, mock_db, mock_get_bridge, mock_agent, fresh_state
    ):
        """Should create task when no current task exists via bridge."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        # Mock the bridge
        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge

        # Create a mock task
        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING

        mock_bridge.process_user_prompt_submit.return_value = TurnProcessingResult(
            success=True,
            task=mock_task,
            new_task_created=True,
        )

        result = process_user_prompt_submit(mock_agent, "session-123")

        assert result.success is True
        mock_bridge.process_user_prompt_submit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_transitions_existing_task(self, mock_db, mock_get_bridge, mock_agent, fresh_state):
        """Should transition existing task to processing via bridge."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        # Mock the bridge
        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge

        # Create a mock task
        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING

        mock_bridge.process_user_prompt_submit.return_value = TurnProcessingResult(
            success=True,
            task=mock_task,
        )

        result = process_user_prompt_submit(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True


class TestProcessStop:
    """Tests for process_stop function."""

    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_stop(self, mock_db, mock_get_bridge, mock_agent, fresh_state):
        """Test stop transitions task to COMPLETE via bridge."""
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_stop.return_value = TurnProcessingResult(
            success=True,
            task=None,
        )

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "complete"
        mock_bridge.process_stop.assert_called_once_with(mock_agent, "session-123")


class TestProcessNotification:
    """Tests for process_notification function."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_with_processing_task_transitions(self, mock_db, mock_agent, fresh_state):
        """Notification with a PROCESSING task should transition to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "AWAITING_INPUT"
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_without_active_task_does_not_broadcast(self, mock_db, mock_agent, fresh_state):
        """Notification with no active task should not broadcast AWAITING_INPUT."""
        mock_agent.get_current_task.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_after_task_complete_does_not_override(self, mock_db, mock_agent, fresh_state):
        """Notification arriving after stop (task COMPLETE) should not override to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        # Agent has no current (incomplete) task — get_current_task returns None after completion
        mock_agent.get_current_task.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_with_awaiting_input_task_is_noop(self, mock_db, mock_agent, fresh_state):
        """Notification when task is already AWAITING_INPUT should not re-transition."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        # Task state should remain AWAITING_INPUT (not re-set)
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_updates_timestamp_and_commits(
        self, mock_db, mock_agent, fresh_state
    ):
        """Notification should update timestamp and commit DB state."""
        process_notification(mock_agent, "session-123")

        mock_db.session.commit.assert_called_once()


class TestHookEventResult:
    """Tests for HookEventResult named tuple."""

    def test_success_result(self):
        """Test creating a success result."""
        result = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="processing",
        )

        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is True
        assert result.new_state == "processing"

    def test_error_result(self):
        """Test creating an error result."""
        result = HookEventResult(
            success=False,
            error_message="Something went wrong",
        )

        assert result.success is False
        assert result.error_message == "Something went wrong"
