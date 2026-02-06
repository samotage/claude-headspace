"""Tests for hook receiver service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from claude_headspace.services.hook_receiver import (
    HookEventResult,
    HookEventType,
    HookMode,
    HookReceiverState,
    _awaiting_tool_for_agent,
    _extract_question_text,
    _extract_structured_options,
    _synthesize_permission_options,
    configure_receiver,
    get_receiver_state,
    process_notification,
    process_permission_request,
    process_pre_tool_use,
    process_session_end,
    process_session_start,
    process_stop,
    process_user_prompt_submit,
    process_post_tool_use,
)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.id = 1
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None
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
    _awaiting_tool_for_agent.clear()
    yield state


class TestHookEventType:
    def test_event_types_are_strings(self):
        assert HookEventType.SESSION_START == "session_start"
        assert HookEventType.SESSION_END == "session_end"
        assert HookEventType.USER_PROMPT_SUBMIT == "user_prompt_submit"
        assert HookEventType.STOP == "stop"
        assert HookEventType.NOTIFICATION == "notification"
        assert HookEventType.PRE_TOOL_USE == "pre_tool_use"
        assert HookEventType.PERMISSION_REQUEST == "permission_request"


class TestHookMode:
    def test_mode_values(self):
        assert HookMode.HOOKS_ACTIVE == "hooks_active"
        assert HookMode.POLLING_FALLBACK == "polling_fallback"


class TestHookReceiverState:
    def test_record_event_updates_timestamp(self, fresh_state):
        assert fresh_state.last_event_at is None
        fresh_state.record_event(HookEventType.SESSION_START)
        assert fresh_state.last_event_at is not None
        assert fresh_state.last_event_type == HookEventType.SESSION_START
        assert fresh_state.events_received == 1

    def test_record_event_switches_to_hooks_active(self, fresh_state):
        assert fresh_state.mode == HookMode.POLLING_FALLBACK
        fresh_state.record_event(HookEventType.NOTIFICATION)
        assert fresh_state.mode == HookMode.HOOKS_ACTIVE

    def test_check_fallback_after_timeout(self, fresh_state):
        fresh_state.mode = HookMode.HOOKS_ACTIVE
        fresh_state.last_event_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        fresh_state.check_fallback()
        assert fresh_state.mode == HookMode.POLLING_FALLBACK

    def test_get_polling_interval_hooks_active(self, fresh_state):
        fresh_state.mode = HookMode.HOOKS_ACTIVE
        assert fresh_state.get_polling_interval() == 60

    def test_get_polling_interval_fallback(self, fresh_state):
        fresh_state.mode = HookMode.POLLING_FALLBACK
        assert fresh_state.get_polling_interval() == 2


class TestConfigureReceiver:
    def test_configure_enabled(self, fresh_state):
        configure_receiver(enabled=False)
        assert fresh_state.enabled is False
        configure_receiver(enabled=True)
        assert fresh_state.enabled is True

    def test_configure_polling_interval(self, fresh_state):
        configure_receiver(polling_interval_with_hooks=120)
        assert fresh_state.polling_interval_with_hooks == 120

    def test_configure_fallback_timeout(self, fresh_state):
        configure_receiver(fallback_timeout=600)
        assert fresh_state.fallback_timeout == 600


class TestProcessSessionStart:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_session_start(self, mock_db, mock_agent, fresh_state):
        result = process_session_start(mock_agent, "session-123")
        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is False
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_session_start_updates_timestamp(self, mock_db, mock_agent, fresh_state):
        old_time = mock_agent.last_seen_at
        process_session_start(mock_agent, "session-123")
        assert mock_agent.last_seen_at >= old_time

    @patch("claude_headspace.services.hook_receiver.db")
    def test_session_start_records_event(self, mock_db, mock_agent, fresh_state):
        process_session_start(mock_agent, "session-123")
        assert fresh_state.last_event_type == HookEventType.SESSION_START
        assert fresh_state.events_received == 1

    @patch("claude_headspace.services.hook_receiver.db")
    def test_session_start_clears_ended_at(self, mock_db, mock_agent, fresh_state):
        """session_start should clear agent.ended_at for the new session."""
        mock_agent.ended_at = datetime.now(timezone.utc)
        process_session_start(mock_agent, "session-123")
        assert mock_agent.ended_at is None


class TestProcessSessionEnd:
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_session_end(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = None
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_session_end(mock_agent, "session-123")

        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is True
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_completes_active_task(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        mock_task = MagicMock()
        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_session_end(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.complete_task.assert_called_once_with(mock_task, trigger="hook:session_end")


class TestProcessUserPromptSubmit:
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_task_when_none_exists(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING

        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, task=mock_task, new_task_created=True,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_user_prompt_submit(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.process_turn.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_transitions_to_processing(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle

        mock_task = MagicMock()
        mock_task.state = TaskState.COMMANDED

        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, task=mock_task,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_user_prompt_submit(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        # Should auto-transition COMMANDED → PROCESSING
        mock_lifecycle.update_task_state.assert_called_once()


class TestProcessStop:
    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_stop(self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnIntent

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.turns = []

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Done. Changes applied."
        mock_detect.return_value = MagicMock(intent=TurnIntent.COMPLETION, confidence=0.9)

        # complete_task sets state to COMPLETE
        def set_complete(task, **kwargs):
            task.state = TaskState.COMPLETE
            return True
        mock_lifecycle.complete_task.side_effect = set_complete

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "complete"
        mock_lifecycle.complete_task.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_stop_with_question_detected(self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnIntent

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.turns = []

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Would you like me to proceed?"
        mock_detect.return_value = MagicMock(intent=TurnIntent.QUESTION, confidence=0.95)

        # update_task_state sets to AWAITING_INPUT
        def set_awaiting(task, **kwargs):
            task.state = TaskState.AWAITING_INPUT
            return True
        mock_lifecycle.update_task_state.side_effect = set_awaiting

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "awaiting_input"
        mock_lifecycle.complete_task.assert_not_called()
        mock_lifecycle.update_task_state.assert_called_once()
        mock_db.session.add.assert_called_once()  # QUESTION turn added

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_stop_with_no_task_is_noop(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = None

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_end_of_task_detected(self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnIntent

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        eot_text = "Here's a summary of changes."
        mock_extract.return_value = eot_text
        mock_detect.return_value = MagicMock(intent=TurnIntent.END_OF_TASK, confidence=1.0)

        def set_complete(task, **kwargs):
            task.state = TaskState.COMPLETE
            return True
        mock_lifecycle.complete_task.side_effect = set_complete

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.complete_task.assert_called_once_with(
            task=mock_task, trigger="hook:stop:end_of_task",
            agent_text=eot_text, intent=TurnIntent.END_OF_TASK,
        )


class TestProcessNotification:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_with_processing_task_transitions(self, mock_db, mock_agent, fresh_state):
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
        mock_agent.get_current_task.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_after_task_complete_does_not_override(self, mock_db, mock_agent, fresh_state):
        mock_agent.get_current_task.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_with_awaiting_input_task_is_noop(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert mock_task.state == TaskState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_updates_timestamp_and_commits(self, mock_db, mock_agent, fresh_state):
        process_notification(mock_agent, "session-123")
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_sends_os_notification_on_transition(
        self, mock_db, mock_get_lifecycle, mock_agent, fresh_state
    ):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = "Fix auth bug"
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_lifecycle = MagicMock()
        mock_get_lifecycle.return_value = mock_lifecycle

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input", title="Question",
        )

        assert result.state_changed is True
        mock_lifecycle.update_task_state.assert_called_once_with(
            mock_task, TaskState.AWAITING_INPUT,
            trigger="notification", confidence=1.0,
        )

    @patch("claude_headspace.services.hook_receiver._send_notification")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_does_not_send_os_notification_without_transition(
        self, mock_db, mock_send_notif, mock_agent, fresh_state
    ):
        mock_agent.get_current_task.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.state_changed is False
        mock_send_notif.assert_not_called()


class TestHookEventResult:
    def test_success_result(self):
        result = HookEventResult(success=True, agent_id=1, state_changed=True, new_state="processing")
        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is True
        assert result.new_state == "processing"

    def test_error_result(self):
        result = HookEventResult(success=False, error_message="Something went wrong")
        assert result.success is False
        assert result.error_message == "Something went wrong"


class TestProcessPreToolUse:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_processing_task_transitions_to_awaiting_input(self, mock_db, mock_agent, fresh_state):
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
        mock_agent.get_current_task.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_already_awaiting_input_is_noop(self, mock_db, mock_agent, fresh_state):
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
        process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_records_event(self, mock_db, mock_agent, fresh_state):
        process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")
        assert fresh_state.last_event_type == HookEventType.PRE_TOOL_USE
        assert fresh_state.events_received == 1

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_sends_os_notification_on_transition(self, mock_db, mock_get_lifecycle, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = "Implement dark mode"
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_lifecycle = MagicMock()
        mock_get_lifecycle.return_value = mock_lifecycle

        tool_input = {
            "questions": [{"question": "Which approach do you prefer?", "header": "Approach", "options": [], "multiSelect": False}]
        }
        result = process_pre_tool_use(
            mock_agent, "session-123",
            tool_name="AskUserQuestion", tool_input=tool_input,
        )

        assert result.state_changed is True
        mock_lifecycle.update_task_state.assert_called_once_with(
            mock_task, TaskState.AWAITING_INPUT,
            trigger="pre_tool_use", confidence=1.0,
        )

    @patch("claude_headspace.services.hook_receiver._send_notification")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_does_not_send_os_notification_without_transition(self, mock_db, mock_send_notif, mock_agent, fresh_state):
        mock_agent.get_current_task.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is False
        mock_send_notif.assert_not_called()


class TestProcessPermissionRequest:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_processing_task_transitions_to_awaiting_input(self, mock_db, mock_agent, fresh_state):
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
        mock_agent.get_current_task.return_value = None

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_already_awaiting_input_is_noop(self, mock_db, mock_agent, fresh_state):
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
        process_permission_request(mock_agent, "session-123")
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_records_event(self, mock_db, mock_agent, fresh_state):
        process_permission_request(mock_agent, "session-123")
        assert fresh_state.last_event_type == HookEventType.PERMISSION_REQUEST
        assert fresh_state.events_received == 1

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_sends_os_notification_on_transition(self, mock_db, mock_get_lifecycle, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.instruction = "Add user auth"
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_lifecycle = MagicMock()
        mock_get_lifecycle.return_value = mock_lifecycle

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "npm install"},
        )

        assert result.state_changed is True
        mock_lifecycle.update_task_state.assert_called_once_with(
            mock_task, TaskState.AWAITING_INPUT,
            trigger="permission_request", confidence=1.0,
        )

    @patch("claude_headspace.services.hook_receiver._send_notification")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_does_not_send_os_notification_without_transition(self, mock_db, mock_send_notif, mock_agent, fresh_state):
        mock_agent.get_current_task.return_value = None

        result = process_permission_request(mock_agent, "session-123")

        assert result.state_changed is False
        mock_send_notif.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_agent_question_turn_with_tool_input(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "rm -rf /tmp/test"},
        )

        assert result.success is True
        assert result.state_changed is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.text == "Permission needed: Bash"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created_on_transition(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(mock_agent, "session-123", tool_name="Bash")

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[0] == mock_agent
        assert call_args[1] == "Permission needed: Bash"


class TestExtractQuestionText:
    def test_ask_user_question_structure(self):
        tool_input = {
            "questions": [
                {"question": "Which database should we use?", "header": "Database", "options": [], "multiSelect": False}
            ]
        }
        result = _extract_question_text("AskUserQuestion", tool_input)
        assert result == "Which database should we use?"

    def test_fallback_to_tool_name(self):
        result = _extract_question_text("Bash", {"command": "ls"})
        assert result == "Permission needed: Bash"

    def test_fallback_no_tool_name(self):
        result = _extract_question_text(None, None)
        assert result == "Awaiting input"

    def test_empty_questions_list(self):
        result = _extract_question_text("AskUserQuestion", {"questions": []})
        assert result == "Permission needed: AskUserQuestion"

    def test_none_tool_input(self):
        result = _extract_question_text("Bash", None)
        assert result == "Permission needed: Bash"

    def test_non_dict_tool_input(self):
        result = _extract_question_text("Bash", "string_value")
        assert result == "Permission needed: Bash"


class TestExtractStructuredOptions:
    def test_returns_tool_input_for_ask_user_question_with_options(self):
        tool_input = {
            "questions": [{
                "question": "Which database?",
                "header": "Database",
                "options": [
                    {"label": "PostgreSQL", "description": "Relational DB"},
                    {"label": "MongoDB", "description": "Document DB"},
                ],
                "multiSelect": False,
            }]
        }
        result = _extract_structured_options("AskUserQuestion", tool_input)
        assert result == tool_input

    def test_returns_none_for_non_ask_user_question(self):
        result = _extract_structured_options("Bash", {"command": "ls"})
        assert result is None

    def test_returns_none_for_none_tool_name(self):
        result = _extract_structured_options(None, {"questions": []})
        assert result is None

    def test_returns_none_for_empty_questions(self):
        result = _extract_structured_options("AskUserQuestion", {"questions": []})
        assert result is None

    def test_returns_none_for_no_options(self):
        tool_input = {
            "questions": [{
                "question": "Which?",
                "options": [],
            }]
        }
        result = _extract_structured_options("AskUserQuestion", tool_input)
        assert result is None

    def test_returns_none_for_none_tool_input(self):
        result = _extract_structured_options("AskUserQuestion", None)
        assert result is None

    def test_returns_none_for_non_dict_tool_input(self):
        result = _extract_structured_options("AskUserQuestion", "string")
        assert result is None


class TestPreToolUseTurnToolInput:
    """Test that pre_tool_use stores tool_input on Turn for AskUserQuestion."""

    @patch("claude_headspace.services.hook_receiver.db")
    def test_stores_tool_input_on_turn(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        tool_input = {
            "questions": [{
                "question": "Which approach?",
                "header": "Approach",
                "options": [
                    {"label": "Option A", "description": "Desc A"},
                    {"label": "Option B", "description": "Desc B"},
                ],
                "multiSelect": False,
            }]
        }

        result = process_pre_tool_use(
            mock_agent, "session-123",
            tool_name="AskUserQuestion", tool_input=tool_input,
        )

        assert result.success is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.tool_input == tool_input

    @patch("claude_headspace.services.hook_receiver.db")
    def test_tool_input_none_for_non_ask_user_question(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "ls"},
        )

        assert result.success is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.tool_input is None


class TestPreToolUseTurnCreation:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_agent_question_turn_with_ask_user_question(self, mock_db, mock_agent, fresh_state):
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
            tool_name="AskUserQuestion", tool_input=tool_input,
        )

        assert result.success is True
        assert result.state_changed is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.text == "Which approach do you prefer?"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[0] == mock_agent
        assert call_args[1] == "Permission needed: AskUserQuestion"
        assert call_args[2] == mock_task

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_broadcast_without_transition(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        mock_agent.get_current_task.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is False
        mock_broadcast_turn.assert_not_called()


class TestNotificationTurnDedup:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_skips_turn_creation_when_recent_question_exists(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10

        recent_turn = MagicMock()
        recent_turn.actor = TurnActor.AGENT
        recent_turn.intent = TurnIntent.QUESTION
        recent_turn.text = "Which approach do you prefer?"
        recent_turn.timestamp = datetime.now(timezone.utc) - timedelta(seconds=2)
        mock_task.turns = [recent_turn]

        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(
            mock_agent, "session-123",
            message="Input needed", title="Question",
        )

        assert result.success is True
        assert result.state_changed is True
        # Should NOT have added a new turn (dedup)
        mock_db.session.add.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_turn_when_no_recent_question(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input", title="Question",
        )

        assert result.success is True
        assert result.state_changed is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.text == "[Question] Need your input"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created_on_transition(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
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
    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_when_awaiting_input(
        self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_broadcast_turn, mock_agent, fresh_state
    ):
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.text = "Do you want to proceed?"
        mock_turn.tool_input = None  # Real Turn model defaults to None

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.turns = [mock_turn]

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Do you want to proceed?"
        mock_detect.return_value = MagicMock(intent=TurnIntent.QUESTION, confidence=0.95)

        def set_awaiting(task, **kwargs):
            task.state = TaskState.AWAITING_INPUT
            return True
        mock_lifecycle.update_task_state.side_effect = set_awaiting

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_broadcast_turn.assert_called_once_with(
            mock_agent, "Do you want to proceed?", mock_task, tool_input=None,
        )

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_turn_broadcast_when_complete(
        self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_broadcast_turn, mock_agent, fresh_state
    ):
        from claude_headspace.models.task import TaskState
        from claude_headspace.models.turn import TurnIntent

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.turns = []

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Done."
        mock_detect.return_value = MagicMock(intent=TurnIntent.COMPLETION, confidence=0.9)

        def set_complete(task, **kwargs):
            task.state = TaskState.COMPLETE
            return True
        mock_lifecycle.complete_task.side_effect = set_complete

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_broadcast_turn.assert_not_called()


class TestProcessPostToolUse:
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_task_when_no_active_task(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = None

        # No recently completed tasks — query returns None
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        new_task = MagicMock()
        new_task.id = 10
        new_task.state = TaskState.PROCESSING
        mock_lifecycle.create_task.return_value = new_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        mock_lifecycle.create_task.assert_called_once_with(mock_agent, TaskState.COMMANDED)
        mock_lifecycle.update_task_state.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_skips_inferred_when_recent_task_completed(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use should NOT create inferred task if previous task completed < 30s ago."""
        from claude_headspace.models.task import TaskState

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = None

        # Recent completed task — 5 seconds ago
        recent_task = MagicMock()
        recent_task.id = 50
        recent_task.completed_at = datetime.now(timezone.utc) - timedelta(seconds=5)

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = recent_task

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        mock_lifecycle.create_task.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_creates_inferred_when_old_task_completed(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use should create inferred task if previous task completed > 30s ago."""
        from claude_headspace.models.task import TaskState

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = None

        # Old completed task — 60 seconds ago
        old_task = MagicMock()
        old_task.id = 40
        old_task.completed_at = datetime.now(timezone.utc) - timedelta(seconds=60)

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = old_task

        new_task = MagicMock()
        new_task.id = 11
        new_task.state = TaskState.PROCESSING
        mock_lifecycle.create_task.return_value = new_task
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        mock_lifecycle.create_task.assert_called_once_with(mock_agent, TaskState.COMMANDED)

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_noop_when_already_processing(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.create_task.assert_not_called()
        mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_resumes_from_awaiting_input(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task

        result_task = MagicMock()
        result_task.state = TaskState.PROCESSING
        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, task=result_task,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.process_turn.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_preserves_awaiting_for_exit_plan_mode(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use(ExitPlanMode) should NOT resume from AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task

        result = process_post_tool_use(mock_agent, "session-123", tool_name="ExitPlanMode")

        assert result.success is True
        assert result.new_state == TaskState.AWAITING_INPUT.value
        # Should NOT have called process_turn (no resume)
        mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_resumes_for_normal_tools(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use for normal tools should resume from AWAITING_INPUT."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task

        result_task = MagicMock()
        result_task.state = TaskState.PROCESSING
        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, task=result_task,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123", tool_name="Bash")

        assert result.success is True
        # Should have called process_turn (resume)
        mock_lifecycle.process_turn.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_preserves_awaiting_when_different_tool(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use for a different tool than the one that triggered AWAITING_INPUT
        should preserve AWAITING_INPUT (e.g. Task completing while Bash awaits permission)."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task

        # Simulate: permission_request(Bash) set the awaiting tool
        _awaiting_tool_for_agent[mock_agent.id] = "Bash"

        # Now a Task sub-agent completes — should NOT resume
        result = process_post_tool_use(mock_agent, "session-123", tool_name="Task")

        assert result.success is True
        assert result.new_state == TaskState.AWAITING_INPUT.value
        mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_resumes_when_matching_tool(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use for the same tool that triggered AWAITING_INPUT should resume."""
        from claude_headspace.models.task import TaskState
        from claude_headspace.services.task_lifecycle import TurnProcessingResult

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_task.return_value = mock_task

        result_task = MagicMock()
        result_task.state = TaskState.PROCESSING
        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, task=result_task,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        # Simulate: permission_request(Bash) set the awaiting tool
        _awaiting_tool_for_agent[mock_agent.id] = "Bash"

        # post_tool_use(Bash) — user approved, should resume
        result = process_post_tool_use(mock_agent, "session-123", tool_name="Bash")

        assert result.success is True
        mock_lifecycle.process_turn.assert_called_once()
        # Tracking should be cleared
        assert mock_agent.id not in _awaiting_tool_for_agent

    @patch("claude_headspace.services.hook_receiver.db")
    def test_pre_tool_use_non_interactive_no_state_change(self, mock_db, mock_agent, fresh_state):
        """pre_tool_use for non-interactive tools (Read, Grep, etc.) should NOT change state."""
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_agent.get_current_task.return_value = mock_task

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="Read")

        assert result.success is True
        # State should NOT have changed
        assert mock_task.state == TaskState.PROCESSING
        assert result.state_changed is False


class TestSynthesizePermissionOptions:
    """Tests for _synthesize_permission_options function."""

    @patch("claude_headspace.services.tmux_bridge.capture_permission_options")
    def test_returns_options_when_pane_available(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = [
            {"label": "Yes"},
            {"label": "No"},
        ]

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "ls"})

        assert result is not None
        assert result["source"] == "permission_pane_capture"
        assert len(result["questions"]) == 1
        assert result["questions"][0]["question"] == "Permission needed: Bash"
        assert result["questions"][0]["options"] == [
            {"label": "Yes"},
            {"label": "No"},
        ]

    def test_returns_none_without_tmux_pane_id(self, mock_agent):
        mock_agent.tmux_pane_id = None

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "ls"})

        assert result is None

    @patch("claude_headspace.services.tmux_bridge.capture_permission_options")
    def test_returns_none_on_capture_failure(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = None

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "ls"})

        assert result is None

    @patch("claude_headspace.services.tmux_bridge.capture_permission_options")
    def test_returns_none_on_exception(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.side_effect = RuntimeError("tmux error")

        result = _synthesize_permission_options(mock_agent, "Bash", None)

        assert result is None

    @patch("claude_headspace.services.tmux_bridge.capture_permission_options")
    def test_question_text_with_no_tool_name(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = [
            {"label": "Yes"},
            {"label": "No"},
        ]

        result = _synthesize_permission_options(mock_agent, None, None)

        assert result["questions"][0]["question"] == "Permission needed"


class TestPermissionPaneCapture:
    """Integration tests for permission pane capture in the hook flow."""

    @patch("claude_headspace.services.hook_receiver._synthesize_permission_options")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_permission_request_uses_synthesized_options(
        self, mock_db, mock_synthesize, mock_agent, fresh_state
    ):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task

        synthesized = {
            "questions": [{
                "question": "Permission needed: Bash",
                "options": [{"label": "Yes"}, {"label": "No"}],
            }],
            "source": "permission_pane_capture",
        }
        mock_synthesize.return_value = synthesized

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "npm install"},
        )

        assert result.success is True
        assert result.state_changed is True
        # Verify the synthesized options were stored on the Turn
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.tool_input == synthesized

    @patch("claude_headspace.services.hook_receiver._synthesize_permission_options")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_permission_request_falls_back_when_synthesis_returns_none(
        self, mock_db, mock_synthesize, mock_agent, fresh_state
    ):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_task.turns = []
        mock_agent.get_current_task.return_value = mock_task

        mock_synthesize.return_value = None

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "ls"},
        )

        assert result.success is True
        # Turn created but without structured options
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        assert added_turn.tool_input is None

    @patch("claude_headspace.services.hook_receiver._synthesize_permission_options")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_pre_tool_use_does_not_call_synthesize(
        self, mock_db, mock_synthesize, mock_agent, fresh_state
    ):
        from claude_headspace.models.task import TaskState

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.id = 10
        mock_agent.get_current_task.return_value = mock_task

        process_pre_tool_use(
            mock_agent, "session-123",
            tool_name="AskUserQuestion",
            tool_input={
                "questions": [{
                    "question": "Which?",
                    "options": [{"label": "A"}, {"label": "B"}],
                    "header": "Choice",
                    "multiSelect": False,
                }]
            },
        )

        # _synthesize_permission_options should NOT be called for pre_tool_use
        mock_synthesize.assert_not_called()
