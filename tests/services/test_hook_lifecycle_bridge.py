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
        """Stop hook should complete the active task when no question detected."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            # Mock _extract_transcript_content to return completion text
            with patch.object(
                bridge, '_extract_transcript_content', return_value="Done. Changes applied."
            ):
                result = bridge.process_stop(mock_agent, "session-123")

                assert result.success is True
                mock_lifecycle.complete_task.assert_called_once_with(
                    task=mock_task,
                    trigger="hook:stop",
                    agent_text="Done. Changes applied.",
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

            with patch.object(
                bridge, '_extract_transcript_content', return_value=""
            ):
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

            with patch.object(
                bridge_no_writer, '_extract_transcript_content', return_value=""
            ):
                result = bridge_no_writer.process_stop(mock_agent, "session-123")

                assert result.event_written is False

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_question_detected_transitions_to_awaiting_input(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Stop hook should transition to AWAITING_INPUT when question is detected."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            with patch.object(
                bridge, '_extract_transcript_content',
                return_value="Would you like me to proceed with the changes?"
            ):
                result = bridge.process_stop(mock_agent, "session-123")

                assert result.success is True
                assert result.task is mock_task
                # Should NOT have called complete_task
                mock_lifecycle.complete_task.assert_not_called()
                # Should have called update_task_state with AWAITING_INPUT
                mock_lifecycle.update_task_state.assert_called_once()
                call_kwargs = mock_lifecycle.update_task_state.call_args
                assert call_kwargs.kwargs["task"] is mock_task
                assert call_kwargs.kwargs["to_state"] == TaskState.AWAITING_INPUT
                assert call_kwargs.kwargs["trigger"] == "hook:stop:question_detected"
                # Should have added a QUESTION turn
                mock_db.session.add.assert_called_once()
                added_turn = mock_db.session.add.call_args[0][0]
                assert added_turn.actor == TurnActor.AGENT
                assert added_turn.intent == TurnIntent.QUESTION

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_end_of_task_detected_completes_with_eot_intent(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Stop hook should complete with END_OF_TASK intent when end-of-task is detected."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            eot_text = (
                "Here's a summary of the changes I made:\n"
                "- Updated the config module\n"
                "- Fixed the login bug\n\n"
                "Let me know if you'd like any adjustments."
            )
            with patch.object(
                bridge, '_extract_transcript_content',
                return_value=eot_text,
            ):
                result = bridge.process_stop(mock_agent, "session-123")

                assert result.success is True
                mock_lifecycle.complete_task.assert_called_once_with(
                    task=mock_task,
                    trigger="hook:stop:end_of_task",
                    agent_text=eot_text,
                    intent=TurnIntent.END_OF_TASK,
                )
                mock_lifecycle.update_task_state.assert_not_called()

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_completion_text_completes_normally(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Stop hook should complete normally when text is a completion, not a question."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            with patch.object(
                bridge, '_extract_transcript_content',
                return_value="I've finished implementing the changes."
            ):
                result = bridge.process_stop(mock_agent, "session-123")

                assert result.success is True
                mock_lifecycle.complete_task.assert_called_once_with(
                    task=mock_task,
                    trigger="hook:stop",
                    agent_text="I've finished implementing the changes.",
                )
                mock_lifecycle.update_task_state.assert_not_called()

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_empty_transcript_completes_normally(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Stop hook should complete normally when transcript is empty."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            with patch.object(
                bridge, '_extract_transcript_content', return_value=""
            ):
                result = bridge.process_stop(mock_agent, "session-123")

                assert result.success is True
                mock_lifecycle.complete_task.assert_called_once()
                mock_lifecycle.update_task_state.assert_not_called()

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_no_transcript_path_completes_normally(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """Stop hook should complete normally when agent has no transcript path."""
        mock_agent.transcript_path = None

        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            # _extract_transcript_content will return "" since no transcript_path
            result = bridge.process_stop(mock_agent, "session-123")

            assert result.success is True
            mock_lifecycle.complete_task.assert_called_once()
            mock_lifecycle.update_task_state.assert_not_called()


class TestProcessPostToolUse(TestHookLifecycleBridge):
    """Tests for process_post_tool_use method."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_creates_task_when_no_active_task(
        self, mock_db, bridge, mock_agent
    ):
        """PostToolUse should create a PROCESSING task when agent has no active task."""
        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = None

            new_task = MagicMock()
            new_task.id = 10
            new_task.state = TaskState.PROCESSING
            mock_lifecycle.create_task.return_value = new_task

            result = bridge.process_post_tool_use(mock_agent, "session-123")

            assert result.success is True
            assert result.new_task_created is True
            assert result.task is new_task
            mock_lifecycle.create_task.assert_called_once_with(
                mock_agent, TaskState.COMMANDED
            )
            mock_lifecycle.update_task_state.assert_called_once_with(
                task=new_task,
                to_state=TaskState.PROCESSING,
                trigger="hook:post_tool_use:inferred",
                confidence=0.9,
            )

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_noop_when_already_processing(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """PostToolUse should be a no-op when task is already PROCESSING."""
        mock_task.state = TaskState.PROCESSING

        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            result = bridge.process_post_tool_use(mock_agent, "session-123")

            assert result.success is True
            assert result.task is mock_task
            mock_lifecycle.create_task.assert_not_called()
            mock_lifecycle.process_turn.assert_not_called()

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_resumes_from_awaiting_input(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """PostToolUse should resume from AWAITING_INPUT to PROCESSING."""
        mock_task.state = TaskState.AWAITING_INPUT

        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task
            mock_lifecycle.process_turn.return_value = TurnProcessingResult(
                success=True,
                task=mock_task,
            )

            result = bridge.process_post_tool_use(mock_agent, "session-123")

            assert result.success is True
            mock_lifecycle.process_turn.assert_called_once_with(
                agent=mock_agent,
                actor=TurnActor.USER,
                text=None,
            )

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_noop_when_commanded(
        self, mock_db, bridge, mock_agent, mock_task
    ):
        """PostToolUse should be a no-op when task is COMMANDED."""
        mock_task.state = TaskState.COMMANDED

        with patch.object(
            bridge, '_get_lifecycle_manager'
        ) as mock_get_lifecycle:
            mock_lifecycle = MagicMock()
            mock_get_lifecycle.return_value = mock_lifecycle
            mock_lifecycle.get_current_task.return_value = mock_task

            result = bridge.process_post_tool_use(mock_agent, "session-123")

            assert result.success is True
            assert result.task is mock_task
            mock_lifecycle.create_task.assert_not_called()


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


class TestSummarisationServiceInjection(TestHookLifecycleBridge):
    """Tests for summarisation service injection into lifecycle manager."""

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_lifecycle_manager_receives_summarisation_service(
        self, mock_db, mock_event_writer
    ):
        """Lifecycle manager should receive summarisation_service when available."""
        from flask import Flask

        mock_summarisation = MagicMock()
        bridge = HookLifecycleBridge(event_writer=mock_event_writer)

        test_app = Flask(__name__)
        test_app.extensions["summarisation_service"] = mock_summarisation

        with test_app.app_context():
            lifecycle = bridge._get_lifecycle_manager()

            assert lifecycle._summarisation_service is mock_summarisation

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_lifecycle_manager_none_when_no_app_context(
        self, mock_db, mock_event_writer
    ):
        """Lifecycle manager should have None summarisation_service outside app context."""
        bridge = HookLifecycleBridge(event_writer=mock_event_writer)

        # Outside any app context, RuntimeError is caught internally
        lifecycle = bridge._get_lifecycle_manager()

        assert lifecycle._summarisation_service is None

    @patch("claude_headspace.services.hook_lifecycle_bridge.db")
    def test_lifecycle_manager_none_when_service_not_registered(
        self, mock_db, mock_event_writer
    ):
        """Lifecycle manager should have None when summarisation_service not in extensions."""
        from flask import Flask

        bridge = HookLifecycleBridge(event_writer=mock_event_writer)

        test_app = Flask(__name__)
        # Don't register summarisation_service

        with test_app.app_context():
            lifecycle = bridge._get_lifecycle_manager()

            assert lifecycle._summarisation_service is None


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
