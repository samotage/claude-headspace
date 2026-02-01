"""Tests for hook receiver service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from claude_headspace.services.hook_receiver import (
    HookEventResult,
    HookEventType,
    HookMode,
    HookReceiverState,
    _extract_question_text,
    configure_receiver,
    get_receiver_state,
    process_notification,
    process_permission_request,
    process_pre_tool_use,
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
        assert HookEventType.PRE_TOOL_USE == "pre_tool_use"
        assert HookEventType.PERMISSION_REQUEST == "permission_request"


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
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_task = MagicMock()
        mock_task.state = TaskState.COMPLETE

        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_stop.return_value = TurnProcessingResult(
            success=True,
            task=mock_task,
        )

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "complete"
        mock_bridge.process_stop.assert_called_once_with(mock_agent, "session-123")

    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_stop_with_question_detected_returns_awaiting_input(
        self, mock_db, mock_get_bridge, mock_agent, fresh_state
    ):
        """Test stop returns AWAITING_INPUT when bridge detects a question."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT

        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_stop.return_value = TurnProcessingResult(
            success=True,
            task=mock_task,
        )

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "awaiting_input"

    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_stop_with_no_task_is_noop(
        self, mock_db, mock_get_bridge, mock_agent, fresh_state
    ):
        """Test stop is a no-op when bridge returns no task (no broadcast)."""
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_stop.return_value = TurnProcessingResult(
            success=True,
            task=None,
        )

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None


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

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_sends_os_notification_on_transition(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """Notification should send OS notification with context when transitioning to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = "Fix auth bug"
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input",
            title="Question",
        )

        assert result.state_changed is True
        mock_svc.notify_awaiting_input.assert_called_once_with(
            agent_id=str(mock_agent.id),
            agent_name="test-agent",
            project="test-project",
            task_instruction="Fix auth bug",
            turn_text="Need your input",
        )

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_does_not_send_os_notification_without_transition(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """Notification should not send OS notification when no transition occurs."""
        mock_agent.get_current_task.return_value = None

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        result = process_notification(mock_agent, "session-123")

        assert result.state_changed is False
        mock_svc.notify_awaiting_input.assert_not_called()

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_falls_back_to_command_turn_for_instruction(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """Notification should fall back to first USER COMMAND turn text when instruction is None."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_command_turn = MagicMock()
        mock_command_turn.actor = TurnActor.USER
        mock_command_turn.intent = TurnIntent.COMMAND
        mock_command_turn.text = "Fix the login bug"

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = None  # Not yet summarised
        mock_task.turns = [mock_command_turn]
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        result = process_notification(
            mock_agent, "session-123",
            message="Need input",
        )

        assert result.state_changed is True
        mock_svc.notify_awaiting_input.assert_called_once_with(
            agent_id=str(mock_agent.id),
            agent_name="test-agent",
            project="test-project",
            task_instruction="Fix the login bug",
            turn_text="Need input",
        )


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


class TestProcessPreToolUse:
    """Tests for process_pre_tool_use function."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_processing_task_transitions_to_awaiting_input(self, mock_db, mock_agent, fresh_state):
        """PreToolUse with a PROCESSING task should transition to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_agent.get_current_task.return_value = mock_task

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "AWAITING_INPUT"
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_active_task_is_noop(self, mock_db, mock_agent, fresh_state):
        """PreToolUse with no active task should not transition."""
        mock_agent.get_current_task.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_already_awaiting_input_is_noop(self, mock_db, mock_agent, fresh_state):
        """PreToolUse when task is already AWAITING_INPUT should not re-transition."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_agent.get_current_task.return_value = mock_task

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is False
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_updates_timestamp_and_commits(self, mock_db, mock_agent, fresh_state):
        """PreToolUse should update timestamp and commit DB state."""
        process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_records_event(self, mock_db, mock_agent, fresh_state):
        """PreToolUse should record the event in receiver state."""
        process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert fresh_state.last_event_type == HookEventType.PRE_TOOL_USE
        assert fresh_state.events_received == 1

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_sends_os_notification_on_transition(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """PreToolUse should send OS notification with context when transitioning to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = "Implement dark mode"
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        tool_input = {
            "questions": [{"question": "Which approach do you prefer?", "header": "Approach", "options": [], "multiSelect": False}]
        }
        result = process_pre_tool_use(
            mock_agent, "session-123",
            tool_name="AskUserQuestion",
            tool_input=tool_input,
        )

        assert result.state_changed is True
        mock_svc.notify_awaiting_input.assert_called_once_with(
            agent_id=str(mock_agent.id),
            agent_name="test-agent",
            project="test-project",
            task_instruction="Implement dark mode",
            turn_text="Which approach do you prefer?",
        )

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_does_not_send_os_notification_without_transition(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """PreToolUse should not send OS notification when no transition occurs."""
        mock_agent.get_current_task.return_value = None

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is False
        mock_svc.notify_awaiting_input.assert_not_called()


class TestProcessPermissionRequest:
    """Tests for process_permission_request function."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_processing_task_transitions_to_awaiting_input(self, mock_db, mock_agent, fresh_state):
        """PermissionRequest with a PROCESSING task should transition to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "AWAITING_INPUT"
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_active_task_is_noop(self, mock_db, mock_agent, fresh_state):
        """PermissionRequest with no active task should not transition."""
        mock_agent.get_current_task.return_value = None

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_already_awaiting_input_is_noop(self, mock_db, mock_agent, fresh_state):
        """PermissionRequest when task is already AWAITING_INPUT should not re-transition."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_updates_timestamp_and_commits(self, mock_db, mock_agent, fresh_state):
        """PermissionRequest should update timestamp and commit DB state."""
        process_permission_request(mock_agent, "session-123")

        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_records_event(self, mock_db, mock_agent, fresh_state):
        """PermissionRequest should record the event in receiver state."""
        process_permission_request(mock_agent, "session-123")

        assert fresh_state.last_event_type == HookEventType.PERMISSION_REQUEST
        assert fresh_state.events_received == 1

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_sends_os_notification_on_transition(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """PermissionRequest should send OS notification with context when transitioning to AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = "Add user auth"
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash",
            tool_input={"command": "npm install"},
        )

        assert result.state_changed is True
        mock_svc.notify_awaiting_input.assert_called_once_with(
            agent_id=str(mock_agent.id),
            agent_name="test-agent",
            project="test-project",
            task_instruction="Add user auth",
            turn_text="Permission needed: Bash",
        )

    @patch("claude_headspace.services.notification_service.get_notification_service")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_does_not_send_os_notification_without_transition(
        self, mock_db, mock_get_notif, mock_agent, fresh_state
    ):
        """PermissionRequest should not send OS notification when no transition occurs."""
        mock_agent.get_current_task.return_value = None

        mock_svc = MagicMock()
        mock_get_notif.return_value = mock_svc

        result = process_permission_request(mock_agent, "session-123")

        assert result.state_changed is False
        mock_svc.notify_awaiting_input.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_agent_question_turn_with_tool_input(self, mock_db, mock_agent, fresh_state):
        """PermissionRequest should create an AGENT QUESTION turn with extracted text."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash",
            tool_input={"command": "rm -rf /tmp/test"},
        )

        assert result.success is True
        assert result.state_changed is True
        # Verify a Turn was added to db.session
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.text == "Permission needed: Bash"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created_on_transition(
        self, mock_db, mock_broadcast_turn, mock_agent, fresh_state
    ):
        """PermissionRequest should broadcast turn_created when transitioning."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash",
        )

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[0] == mock_agent
        assert call_args[1] == "Permission needed: Bash"


class TestExtractQuestionText:
    """Tests for _extract_question_text helper."""

    def test_ask_user_question_structure(self):
        """Should extract question from AskUserQuestion tool_input."""
        tool_input = {
            "questions": [
                {
                    "question": "Which database should we use?",
                    "header": "Database",
                    "options": [
                        {"label": "PostgreSQL", "description": "Relational DB"},
                        {"label": "MongoDB", "description": "Document DB"},
                    ],
                    "multiSelect": False,
                }
            ]
        }
        result = _extract_question_text("AskUserQuestion", tool_input)
        assert result == "Which database should we use?"

    def test_fallback_to_tool_name(self):
        """Should fall back to 'Permission needed: <tool_name>' when no question found."""
        result = _extract_question_text("Bash", {"command": "ls"})
        assert result == "Permission needed: Bash"

    def test_fallback_no_tool_name(self):
        """Should return generic text when no tool_name or question."""
        result = _extract_question_text(None, None)
        assert result == "Awaiting input"

    def test_empty_questions_list(self):
        """Should fall back when questions list is empty."""
        result = _extract_question_text("AskUserQuestion", {"questions": []})
        assert result == "Permission needed: AskUserQuestion"

    def test_none_tool_input(self):
        """Should handle None tool_input gracefully."""
        result = _extract_question_text("Bash", None)
        assert result == "Permission needed: Bash"

    def test_non_dict_tool_input(self):
        """Should handle non-dict tool_input gracefully."""
        result = _extract_question_text("Bash", "string_value")
        assert result == "Permission needed: Bash"


class TestPreToolUseTurnCreation:
    """Tests for turn creation and broadcasting in process_pre_tool_use."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_agent_question_turn_with_ask_user_question(self, mock_db, mock_agent, fresh_state):
        """PreToolUse should create AGENT QUESTION turn with extracted question text."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        tool_input = {
            "questions": [{"question": "Which approach do you prefer?", "header": "Approach", "options": [], "multiSelect": False}]
        }

        result = process_pre_tool_use(
            mock_agent, "session-123",
            tool_name="AskUserQuestion",
            tool_input=tool_input,
        )

        assert result.success is True
        assert result.state_changed is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.text == "Which approach do you prefer?"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        """PreToolUse should broadcast turn_created when creating a turn."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_pre_tool_use(
            mock_agent, "session-123",
            tool_name="AskUserQuestion",
        )

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[0] == mock_agent
        assert call_args[1] == "Permission needed: AskUserQuestion"
        assert call_args[2] == mock_task

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_broadcast_without_transition(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        """PreToolUse should not broadcast when no transition occurs."""
        mock_agent.get_current_task.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is False
        mock_broadcast_turn.assert_not_called()


class TestNotificationTurnDedup:
    """Tests for notification turn dedup logic."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_skips_turn_creation_when_recent_question_exists(self, mock_db, mock_agent, fresh_state):
        """Notification should skip turn creation if a recent AGENT QUESTION turn exists."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10

        # Simulate a recent AGENT QUESTION turn (from pre_tool_use)
        recent_turn = MagicMock()
        recent_turn.actor = TurnActor.AGENT
        recent_turn.intent = TurnIntent.QUESTION
        recent_turn.text = "Which approach do you prefer?"
        recent_turn.timestamp = datetime.now(timezone.utc) - timedelta(seconds=2)
        mock_task.turns = [recent_turn]

        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(
            mock_agent, "session-123",
            message="Input needed",
            title="Question",
        )

        assert result.success is True
        assert result.state_changed is True
        # Should NOT have added a new turn (dedup)
        mock_db.session.add.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_turn_when_no_recent_question(self, mock_db, mock_agent, fresh_state):
        """Notification should create turn when no recent AGENT QUESTION exists."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.turns = []  # No existing turns
        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input",
            title="Question",
        )

        assert result.success is True
        assert result.state_changed is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.text == "[Question] Need your input"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created_on_transition(
        self, mock_db, mock_broadcast_turn, mock_agent, fresh_state
    ):
        """Notification should broadcast turn_created when transitioning."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input",
        )

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[1] == "Need your input"


class TestStopTurnBroadcast:
    """Tests for turn broadcasting in process_stop."""

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_when_awaiting_input(
        self, mock_db, mock_get_bridge, mock_broadcast_turn, mock_agent, fresh_state
    ):
        """Stop should broadcast turn_created when result is AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnActor, TurnIntent
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        # Set up a mock turn on the task
        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.text = "Do you want to proceed?"

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [mock_turn]

        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_stop.return_value = TurnProcessingResult(
            success=True,
            task=mock_task,
        )

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_broadcast_turn.assert_called_once_with(mock_agent, "Do you want to proceed?", mock_task)

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.get_hook_bridge")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_turn_broadcast_when_complete(
        self, mock_db, mock_get_bridge, mock_broadcast_turn, mock_agent, fresh_state
    ):
        """Stop should not broadcast turn_created when result is COMPLETE."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_task = MagicMock()
        mock_task.state = TaskState.COMPLETE
        mock_task.turns = []

        mock_bridge = MagicMock()
        mock_get_bridge.return_value = mock_bridge
        mock_bridge.process_stop.return_value = TurnProcessingResult(
            success=True,
            task=mock_task,
        )

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_broadcast_turn.assert_not_called()
