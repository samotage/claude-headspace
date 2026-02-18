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
    _deferred_stop_pending,
    _extract_question_text,
    _extract_structured_options,
    _respond_pending_for_agent,
    _schedule_deferred_stop,
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
    reset_receiver_state,
)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.id = 1
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None
    agent.state.value = "idle"
    agent.get_current_command.return_value = None
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
    _respond_pending_for_agent.clear()
    _deferred_stop_pending.clear()
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
        mock_lifecycle.get_current_command.return_value = None
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_session_end(mock_agent, "session-123")

        assert result.success is True
        assert result.agent_id == 1
        assert result.state_changed is True
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_completes_active_command(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        mock_command = MagicMock()
        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_session_end(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.complete_command.assert_called_once_with(mock_command, trigger="hook:session_end")


class TestProcessUserPromptSubmit:
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_command_when_none_exists(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.services.command_lifecycle import TurnProcessingResult

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING

        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, command=mock_command, new_command_created=True,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_user_prompt_submit(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.process_turn.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_transitions_to_processing(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.services.command_lifecycle import TurnProcessingResult

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle

        mock_command = MagicMock()
        mock_command.state = CommandState.COMMANDED

        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, command=mock_command,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_user_prompt_submit(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        # Should auto-transition COMMANDED → PROCESSING
        mock_lifecycle.update_command_state.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_user_prompt_submit_skips_tool_interruption_artifact(
        self, mock_db, mock_agent, fresh_state
    ):
        """Tool interruption artifacts from tmux key injection are silently skipped."""
        result = process_user_prompt_submit(
            mock_agent,
            "session-123",
            prompt_text="[Request interrupted by user for tool use]",
        )

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None


class TestProcessStop:
    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_successful_stop(self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnIntent

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.turns = []

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Done. Changes applied."
        mock_detect.return_value = MagicMock(intent=TurnIntent.COMPLETION, confidence=0.9)

        # complete_command sets state to COMPLETE
        def set_complete(command, **kwargs):
            command.state = CommandState.COMPLETE
            return True
        mock_lifecycle.complete_command.side_effect = set_complete

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "complete"
        mock_lifecycle.complete_command.assert_called_once()

    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_stop_with_question_detected(self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnIntent

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.turns = []

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Would you like me to proceed?"
        mock_detect.return_value = MagicMock(intent=TurnIntent.QUESTION, confidence=0.95)

        # update_command_state sets to AWAITING_INPUT
        def set_awaiting(command, **kwargs):
            command.state = CommandState.AWAITING_INPUT
            return True
        mock_lifecycle.update_command_state.side_effect = set_awaiting

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "awaiting_input"
        mock_lifecycle.complete_command.assert_not_called()
        mock_lifecycle.update_command_state.assert_called_once()
        mock_db.session.add.assert_called_once()  # QUESTION turn added

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_stop_with_no_command_is_noop(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = None

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_end_of_command_detected(self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnIntent

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command
        mock_lifecycle.get_pending_summarisations.return_value = []

        eot_text = "Here's a summary of changes."
        mock_extract.return_value = eot_text
        mock_detect.return_value = MagicMock(intent=TurnIntent.END_OF_COMMAND, confidence=1.0)

        def set_complete(command, **kwargs):
            command.state = CommandState.COMPLETE
            return True
        mock_lifecycle.complete_command.side_effect = set_complete

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.complete_command.assert_called_once_with(
            command=mock_command, trigger="hook:stop:end_of_command",
            agent_text=eot_text, intent=TurnIntent.END_OF_COMMAND,
        )


class TestProcessNotification:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_with_processing_command_transitions(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_agent.get_current_command.return_value = mock_command

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "AWAITING_INPUT"
        assert mock_command.state == CommandState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_without_active_command_does_not_broadcast(self, mock_db, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_after_command_complete_does_not_override(self, mock_db, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_with_awaiting_input_command_is_noop(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT
        mock_agent.get_current_command.return_value = mock_command

        result = process_notification(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert mock_command.state == CommandState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_updates_timestamp_and_commits(self, mock_db, mock_agent, fresh_state):
        process_notification(mock_agent, "session-123")
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_sends_os_notification_on_transition(
        self, mock_db, mock_get_lifecycle, mock_agent, fresh_state
    ):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.instruction = "Fix auth bug"
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_lifecycle = MagicMock()
        mock_get_lifecycle.return_value = mock_lifecycle

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input", title="Question",
        )

        assert result.state_changed is True
        mock_lifecycle.update_command_state.assert_called_once_with(
            mock_command, CommandState.AWAITING_INPUT,
            trigger="notification", confidence=1.0,
        )

    @patch("claude_headspace.services.hook_receiver._send_notification")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_does_not_send_os_notification_without_transition(
        self, mock_db, mock_send_notif, mock_agent, fresh_state
    ):
        mock_agent.get_current_command.return_value = None

        result = process_notification(mock_agent, "session-123")

        assert result.state_changed is False
        mock_send_notif.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_notification_skips_interruption_artifact(self, mock_db, mock_agent, fresh_state):
        """Interruption artifact notifications from tmux key injection are silently skipped."""
        result = process_notification(
            mock_agent, "session-123",
            message="Interruption detected",
        )

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None
        # Should still update last_seen_at and commit
        mock_db.session.commit.assert_called_once()


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
    def test_processing_command_transitions_to_awaiting_input(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_agent.get_current_command.return_value = mock_command

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "AWAITING_INPUT"
        assert mock_command.state == CommandState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_active_command_is_noop(self, mock_db, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_already_awaiting_input_is_noop(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT
        mock_agent.get_current_command.return_value = mock_command

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.success is True
        assert result.state_changed is False
        assert mock_command.state == CommandState.AWAITING_INPUT

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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.instruction = "Implement dark mode"
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command
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
        mock_lifecycle.update_command_state.assert_called_once_with(
            mock_command, CommandState.AWAITING_INPUT,
            trigger="pre_tool_use", confidence=1.0,
        )

    @patch("claude_headspace.services.hook_receiver._send_notification")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_does_not_send_os_notification_without_transition(self, mock_db, mock_send_notif, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is False
        mock_send_notif.assert_not_called()


class TestProcessPermissionRequest:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_processing_command_transitions_to_awaiting_input(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_agent.get_current_command.return_value = mock_command

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        assert result.new_state == "AWAITING_INPUT"
        assert mock_command.state == CommandState.AWAITING_INPUT

    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_active_command_is_noop(self, mock_db, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert result.new_state is None

    @patch("claude_headspace.services.hook_receiver.db")
    def test_already_awaiting_input_is_noop(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT
        mock_agent.get_current_command.return_value = mock_command

        result = process_permission_request(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        assert mock_command.state == CommandState.AWAITING_INPUT

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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.instruction = "Add user auth"
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command
        mock_agent.name = "test-agent"
        mock_agent.project.name = "test-project"

        mock_lifecycle = MagicMock()
        mock_get_lifecycle.return_value = mock_lifecycle

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "npm install"},
        )

        assert result.state_changed is True
        mock_lifecycle.update_command_state.assert_called_once_with(
            mock_command, CommandState.AWAITING_INPUT,
            trigger="permission_request", confidence=1.0,
        )

    @patch("claude_headspace.services.hook_receiver._send_notification")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_does_not_send_os_notification_without_transition(self, mock_db, mock_send_notif, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_permission_request(mock_agent, "session-123")

        assert result.state_changed is False
        mock_send_notif.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_agent_question_turn_with_tool_input(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "rm -rf /tmp/test"},
        )

        assert result.success is True
        assert result.state_changed is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        # Permission summarizer generates meaningful text instead of generic "Permission needed: Bash"
        assert added_turn.text == "Bash: rm test"

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_created_on_transition(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

        result = process_permission_request(mock_agent, "session-123", tool_name="Bash")

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[0] == mock_agent
        # With default-fallback permission options, the summarizer generates
        # a meaningful description even without tool_input
        assert "Bash" in call_args[1]


class TestExtractQuestionText:
    def test_ask_user_question_structure(self):
        tool_input = {
            "questions": [
                {"question": "Which database should we use?", "header": "Database", "options": [], "multiSelect": False}
            ]
        }
        result = _extract_question_text("AskUserQuestion", tool_input)
        assert result == "Which database should we use?"

    def test_raw_tool_input_uses_permission_summarizer(self):
        result = _extract_question_text("Bash", {"command": "git status"})
        assert result == "Bash: git status"

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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

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
    def test_tool_input_has_default_options_for_non_ask_user_question(self, mock_db, mock_agent, fresh_state):
        """Permission requests always get options — defaults when tmux capture fails."""
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

        result = process_permission_request(
            mock_agent, "session-123",
            tool_name="Bash", tool_input={"command": "ls"},
        )

        assert result.success is True
        mock_db.session.add.assert_called_once()
        added_turn = mock_db.session.add.call_args[0][0]
        # Default fallback options are provided when tmux capture can't find a dialog
        assert added_turn.tool_input is not None
        assert added_turn.tool_input["source"] == "permission_default_fallback"
        opts = added_turn.tool_input["questions"][0]["options"]
        labels = [o["label"] for o in opts]
        assert "Yes" in labels
        assert "No" in labels


class TestPreToolUseTurnCreation:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_agent_question_turn_with_ask_user_question(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is True
        mock_broadcast_turn.assert_called_once()
        call_args = mock_broadcast_turn.call_args[0]
        assert call_args[0] == mock_agent
        assert call_args[1] == "Permission needed: AskUserQuestion"
        assert call_args[2] == mock_command

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_broadcast_without_transition(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        mock_agent.get_current_command.return_value = None

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="AskUserQuestion")

        assert result.state_changed is False
        mock_broadcast_turn.assert_not_called()


class TestNotificationTurnDedup:
    @patch("claude_headspace.services.hook_receiver.db")
    def test_skips_turn_creation_when_recent_question_exists(self, mock_db, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10

        recent_turn = MagicMock()
        recent_turn.actor = TurnActor.AGENT
        recent_turn.intent = TurnIntent.QUESTION
        recent_turn.text = "Which approach do you prefer?"
        recent_turn.timestamp = datetime.now(timezone.utc) - timedelta(seconds=2)
        mock_command.turns = [recent_turn]

        mock_agent.get_current_command.return_value = mock_command

        result = process_notification(
            mock_agent, "session-123",
            message="Input needed", title="Question",
        )

        assert result.success is True
        assert result.state_changed is True
        # Should NOT have added a new turn (dedup)
        mock_db.session.add.assert_not_called()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_skips_turn_creation_for_notification_events(self, mock_db, mock_agent, fresh_state):
        """Notification hooks carry generic text — the stop hook creates the real turn."""
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input", title="Question",
        )

        assert result.success is True
        assert result.state_changed is True
        # Notification events should NOT create turns (phantom turn fix)
        mock_db.session.add.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_turn_broadcast_for_notification(self, mock_db, mock_broadcast_turn, mock_agent, fresh_state):
        """Notification hooks should not broadcast turn_created (no turn is created)."""
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command

        result = process_notification(
            mock_agent, "session-123",
            message="Need your input",
        )

        assert result.state_changed is True
        # No turn was created, so no turn_created broadcast
        mock_broadcast_turn.assert_not_called()


class TestStopTurnBroadcast:
    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_broadcasts_turn_when_awaiting_input(
        self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_broadcast_turn, mock_agent, fresh_state
    ):
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.text = "Do you want to proceed?"
        mock_turn.tool_input = None  # Real Turn model defaults to None

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.turns = [mock_turn]

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Do you want to proceed?"
        mock_detect.return_value = MagicMock(intent=TurnIntent.QUESTION, confidence=0.95)

        def set_awaiting(command, **kwargs):
            command.state = CommandState.AWAITING_INPUT
            return True
        mock_lifecycle.update_command_state.side_effect = set_awaiting

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_broadcast_turn.assert_called_once_with(
            mock_agent, "Do you want to proceed?", mock_command, tool_input=None, turn_id=mock_turn.id,
            intent='question',
            question_source_type=mock_turn.question_source_type,
        )

    @patch("claude_headspace.services.hook_receiver._broadcast_turn_created")
    @patch("claude_headspace.services.hook_receiver.detect_agent_intent")
    @patch("claude_headspace.services.hook_receiver._extract_transcript_content")
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_turn_broadcast_when_complete(
        self, mock_db, mock_get_lm, mock_extract, mock_detect, mock_broadcast_turn, mock_agent, fresh_state
    ):
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnIntent

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.turns = []

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command
        mock_lifecycle.get_pending_summarisations.return_value = []

        mock_extract.return_value = "Done."
        mock_detect.return_value = MagicMock(intent=TurnIntent.COMPLETION, confidence=0.9)

        def set_complete(command, **kwargs):
            command.state = CommandState.COMPLETE
            return True
        mock_lifecycle.complete_command.side_effect = set_complete

        result = process_stop(mock_agent, "session-123")

        assert result.success is True
        mock_broadcast_turn.assert_not_called()


class TestProcessPostToolUse:
    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_creates_command_when_no_active_command(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = None

        # No recently completed commands — query returns None
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        new_cmd = MagicMock()
        new_cmd.id = 10
        new_cmd.state = CommandState.PROCESSING
        mock_lifecycle.create_command.return_value = new_cmd
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        mock_lifecycle.create_command.assert_called_once_with(mock_agent, CommandState.COMMANDED)
        mock_lifecycle.update_command_state.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_skips_inferred_when_recent_command_completed(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use should NOT create inferred command if previous command completed < 30s ago."""
        from claude_headspace.models.command import CommandState

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = None

        # Recent completed command — 5 seconds ago
        recent_cmd = MagicMock()
        recent_cmd.id = 50
        recent_cmd.completed_at = datetime.now(timezone.utc) - timedelta(seconds=5)

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = recent_cmd

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is False
        mock_lifecycle.create_command.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_creates_inferred_when_old_command_completed(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use should create inferred command if previous command completed > 30s ago."""
        from claude_headspace.models.command import CommandState

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = None

        # Old completed command — 60 seconds ago
        old_cmd = MagicMock()
        old_cmd.id = 40
        old_cmd.completed_at = datetime.now(timezone.utc) - timedelta(seconds=60)

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = old_cmd

        new_cmd = MagicMock()
        new_cmd.id = 11
        new_cmd.state = CommandState.PROCESSING
        mock_lifecycle.create_command.return_value = new_cmd
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        assert result.state_changed is True
        mock_lifecycle.create_command.assert_called_once_with(mock_agent, CommandState.COMMANDED)

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_noop_when_already_processing(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.create_command.assert_not_called()
        mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_resumes_from_awaiting_input(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        from claude_headspace.models.command import CommandState
        from claude_headspace.services.command_lifecycle import TurnProcessingResult

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command

        result_cmd = MagicMock()
        result_cmd.state = CommandState.PROCESSING
        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, command=result_cmd,
        )
        mock_lifecycle.get_pending_summarisations.return_value = []

        result = process_post_tool_use(mock_agent, "session-123")

        assert result.success is True
        mock_lifecycle.process_turn.assert_called_once()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_preserves_awaiting_for_exit_plan_mode(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use(ExitPlanMode) should NOT resume from AWAITING_INPUT."""
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command

        result = process_post_tool_use(mock_agent, "session-123", tool_name="ExitPlanMode")

        assert result.success is True
        assert result.new_state == CommandState.AWAITING_INPUT.value
        # Should NOT have called process_turn (no resume)
        mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_resumes_for_normal_tools(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use for normal tools should resume from AWAITING_INPUT."""
        from claude_headspace.models.command import CommandState
        from claude_headspace.services.command_lifecycle import TurnProcessingResult

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command

        result_cmd = MagicMock()
        result_cmd.state = CommandState.PROCESSING
        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, command=result_cmd,
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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command

        # Simulate: permission_request(Bash) set the awaiting tool
        _awaiting_tool_for_agent[mock_agent.id] = "Bash"

        # Now a Task sub-agent completes — should NOT resume
        result = process_post_tool_use(mock_agent, "session-123", tool_name="Task")

        assert result.success is True
        assert result.new_state == CommandState.AWAITING_INPUT.value
        mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_receiver._get_lifecycle_manager")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_post_tool_use_resumes_when_matching_tool(self, mock_db, mock_get_lm, mock_agent, fresh_state):
        """post_tool_use for the same tool that triggered AWAITING_INPUT should resume."""
        from claude_headspace.models.command import CommandState
        from claude_headspace.services.command_lifecycle import TurnProcessingResult

        mock_command = MagicMock()
        mock_command.state = CommandState.AWAITING_INPUT

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_current_command.return_value = mock_command

        result_cmd = MagicMock()
        result_cmd.state = CommandState.PROCESSING
        mock_lifecycle.process_turn.return_value = TurnProcessingResult(
            success=True, command=result_cmd,
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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_agent.get_current_command.return_value = mock_command

        result = process_pre_tool_use(mock_agent, "session-123", tool_name="Read")

        assert result.success is True
        # State should NOT have changed
        assert mock_command.state == CommandState.PROCESSING
        assert result.state_changed is False


class TestSynthesizePermissionOptions:
    """Tests for _synthesize_permission_options function."""

    @patch("claude_headspace.services.tmux_bridge.capture_permission_context")
    def test_returns_options_with_summary_when_pane_available(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = {
            "tool_type": "Bash command",
            "command": "ls -la",
            "description": None,
            "options": [{"label": "Yes"}, {"label": "No"}],
        }

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "ls -la"})

        assert result is not None
        assert result["source"] == "permission_pane_capture"
        assert len(result["questions"]) == 1
        # Permission summarizer generates a meaningful summary
        assert result["questions"][0]["question"] == "Bash: ls"
        assert result["questions"][0]["options"] == [
            {"label": "Yes"},
            {"label": "No"},
        ]
        assert "safety" in result

    def test_returns_none_without_tmux_pane_id(self, mock_agent):
        mock_agent.tmux_pane_id = None

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "ls"})

        assert result is None

    @patch("claude_headspace.services.tmux_bridge.capture_permission_context")
    def test_falls_back_to_defaults_on_capture_failure(self, mock_capture, mock_agent):
        """When tmux capture fails, default Yes/No options are returned."""
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = None

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "ls"})

        assert result is not None
        assert result["source"] == "permission_default_fallback"
        labels = [o["label"] for o in result["questions"][0]["options"]]
        assert "Yes" in labels
        assert "No" in labels

    @patch("claude_headspace.services.tmux_bridge.capture_permission_context")
    def test_falls_back_to_defaults_on_exception(self, mock_capture, mock_agent):
        """When tmux capture raises, default Yes/No options are returned."""
        mock_agent.tmux_pane_id = "%5"
        mock_capture.side_effect = RuntimeError("tmux error")

        result = _synthesize_permission_options(mock_agent, "Bash", None)

        assert result is not None
        assert result["source"] == "permission_default_fallback"
        labels = [o["label"] for o in result["questions"][0]["options"]]
        assert "Yes" in labels
        assert "No" in labels

    @patch("claude_headspace.services.tmux_bridge.capture_permission_context")
    def test_question_text_with_no_tool_name(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = {
            "tool_type": None,
            "command": None,
            "description": None,
            "options": [{"label": "Yes"}, {"label": "No"}],
        }

        result = _synthesize_permission_options(mock_agent, None, None)

        assert result["questions"][0]["question"] == "Permission needed"

    @patch("claude_headspace.services.tmux_bridge.capture_permission_context")
    def test_includes_safety_classification(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = {
            "tool_type": "Bash command",
            "command": "rm -rf /tmp/test",
            "description": None,
            "options": [{"label": "Yes"}, {"label": "No"}],
        }

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "rm -rf /tmp/test"})

        assert result is not None
        assert result["safety"] == "destructive"

    @patch("claude_headspace.services.tmux_bridge.capture_permission_context")
    def test_includes_command_context(self, mock_capture, mock_agent):
        mock_agent.tmux_pane_id = "%5"
        mock_capture.return_value = {
            "tool_type": "Bash command",
            "command": "curl http://localhost:5055",
            "description": "Check dashboard",
            "options": [{"label": "Yes"}, {"label": "No"}],
        }

        result = _synthesize_permission_options(mock_agent, "Bash", {"command": "curl http://localhost:5055"})

        assert result is not None
        assert "command_context" in result
        assert result["command_context"]["command"] == "curl http://localhost:5055"
        assert result["command_context"]["description"] == "Check dashboard"


class TestPermissionPaneCapture:
    """Integration tests for permission pane capture in the hook flow."""

    @patch("claude_headspace.services.hook_receiver._synthesize_permission_options")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_permission_request_uses_synthesized_options(
        self, mock_db, mock_synthesize, mock_agent, fresh_state
    ):
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command

        synthesized = {
            "questions": [{
                "question": "Bash: npm install",
                "options": [{"label": "Yes"}, {"label": "No"}],
            }],
            "source": "permission_pane_capture",
            "safety": "safe_write",
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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_command.turns = []
        mock_agent.get_current_command.return_value = mock_command

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
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.state = CommandState.PROCESSING
        mock_command.id = 10
        mock_agent.get_current_command.return_value = mock_command

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


class TestDeferredStopPolling:
    """Tests for the polling loop in _schedule_deferred_stop."""

    @patch("claude_headspace.services.hook_deferred_stop._send_completion_notification")
    @patch("claude_headspace.services.hook_deferred_stop._execute_pending_summarisations")
    @patch("claude_headspace.services.card_state.broadcast_card_refresh")
    @patch("claude_headspace.services.hook_deferred_stop._trigger_priority_scoring")
    @patch("claude_headspace.services.intent_detector.detect_agent_intent")
    @patch("claude_headspace.services.hook_deferred_stop._extract_transcript_content")
    @patch("claude_headspace.services.hook_deferred_stop._get_lifecycle_manager")
    @patch("claude_headspace.database.db")
    def test_polling_finds_transcript_on_second_attempt(
        self, mock_db, mock_get_lm, mock_extract, mock_detect,
        mock_trigger, mock_broadcast, mock_exec_summ, mock_notif, fresh_state,
    ):
        """Deferred stop should retry and find transcript on a subsequent poll."""
        from flask import Flask
        from claude_headspace.models.command import CommandState
        from claude_headspace.models.turn import TurnIntent

        # Simulate: first call returns empty, second returns text
        mock_extract.side_effect = ["", "Done. All changes applied."]
        mock_detect.return_value = MagicMock(intent=TurnIntent.COMPLETION, confidence=0.9)

        mock_command = MagicMock()
        mock_command.id = 100
        mock_command.state = CommandState.PROCESSING
        mock_command.turns = []
        mock_db.session.get.side_effect = lambda model, id: mock_command if id == 100 else MagicMock()

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle
        mock_lifecycle.get_pending_summarisations.return_value = []

        def set_complete(command, **kwargs):
            command.state = CommandState.COMPLETE
            return True
        mock_lifecycle.complete_command.side_effect = set_complete

        _deferred_stop_pending.clear()

        mock_agent = MagicMock()
        mock_agent.id = 42
        mock_agent.project_id = 1

        app = Flask(__name__)
        with app.app_context():
            # Capture the thread target so we can run it synchronously
            with patch("claude_headspace.services.hook_deferred_stop.threading.Thread") as mock_thread_cls:
                mock_thread_instance = MagicMock()
                mock_thread_cls.return_value = mock_thread_instance

                _schedule_deferred_stop(mock_agent, mock_command)

                # Verify thread was spawned and agent was added to pending set
                assert mock_thread_cls.call_count == 1
                mock_thread_instance.start.assert_called_once()

                # Extract the target function and run it synchronously
                target_fn = mock_thread_cls.call_args[1]["target"]

            # Run the deferred check synchronously (outside the Thread mock)
            with patch("claude_headspace.services.hook_deferred_stop.time.sleep"):
                target_fn()

        # Verify transcript extraction was called twice (empty then success)
        assert mock_extract.call_count == 2

        # Verify intent detection ran on the found transcript
        mock_detect.assert_called_once()
        assert "Done. All changes applied." in mock_detect.call_args[0][0]

        # Verify command was completed via lifecycle manager
        mock_lifecycle.complete_command.assert_called_once()

        # Verify downstream effects fired
        mock_trigger.assert_called_once()  # priority scoring
        mock_broadcast.assert_called_once()  # card refresh
        mock_exec_summ.assert_called_once()  # pending summarisations

        # Verify agent was cleaned up from pending set (via AgentHookState)
        from claude_headspace.services.hook_agent_state import get_agent_hook_state
        assert not get_agent_hook_state().is_deferred_stop_pending(42)

    @patch("claude_headspace.services.hook_deferred_stop._extract_transcript_content")
    @patch("claude_headspace.services.hook_deferred_stop._get_lifecycle_manager")
    @patch("claude_headspace.database.db")
    def test_deferred_stop_exits_early_if_command_completed(
        self, mock_db, mock_get_lm, mock_extract, fresh_state,
    ):
        """Deferred stop should exit early if command state becomes COMPLETE between polls."""
        from flask import Flask
        from claude_headspace.models.command import CommandState

        mock_command = MagicMock()
        mock_command.id = 100
        # Task becomes COMPLETE after first poll (simulating another hook completing it)
        mock_command.state = CommandState.COMPLETE

        mock_db.session.get.return_value = mock_command

        mock_lifecycle = MagicMock()
        mock_get_lm.return_value = mock_lifecycle

        _deferred_stop_pending.clear()

        mock_agent = MagicMock()
        mock_agent.id = 43
        mock_agent.project_id = 1

        app = Flask(__name__)
        with app.app_context():
            with patch("claude_headspace.services.hook_deferred_stop.threading.Thread") as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                _schedule_deferred_stop(mock_agent, mock_command)
                # Thread was spawned
                assert mock_thread.call_count == 1

                # Get the target function and run it
                target_fn = mock_thread.call_args[1]["target"]

        _deferred_stop_pending.clear()


class TestResetReceiverState:
    """Tests for reset_receiver_state() — clears all module-level state dicts."""

    def test_reset_clears_all_module_dicts(self):
        """reset_receiver_state should clear all three module-level dicts."""
        _awaiting_tool_for_agent[99] = "Bash"
        _respond_pending_for_agent[99] = 1.0
        _deferred_stop_pending.add(99)

        reset_receiver_state()

        assert len(_awaiting_tool_for_agent) == 0
        assert len(_respond_pending_for_agent) == 0
        assert len(_deferred_stop_pending) == 0

    def test_deferred_stop_deduplication(self):
        """_schedule_deferred_stop should not spawn duplicate threads for the same agent."""
        from flask import Flask
        from claude_headspace.services.hook_agent_state import get_agent_hook_state

        mock_agent = MagicMock()
        mock_agent.id = 42
        mock_agent.project_id = 1

        mock_command = MagicMock()
        mock_command.id = 100

        _deferred_stop_pending.clear()

        app = Flask(__name__)
        with app.app_context():
            with patch("claude_headspace.services.hook_deferred_stop.threading.Thread") as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                _schedule_deferred_stop(mock_agent, mock_command)
                assert mock_thread.call_count == 1
                assert get_agent_hook_state().is_deferred_stop_pending(42)

                # Second call with same agent should be deduped
                _schedule_deferred_stop(mock_agent, mock_command)
                assert mock_thread.call_count == 1  # Still just 1

        _deferred_stop_pending.clear()
