"""Tests for revival injection in the hook receiver.

Tests the revival-specific logic added to process_session_start():
- Revival injection fires for agents with previous_agent_id and no Handoff record
- Revival injection does NOT fire for handoff successors
- Revival instruction message is sent via tmux_bridge
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.hook_receiver import (
    HookMode,
    _awaiting_tool_for_agent,
    _deferred_stop_pending,
    _respond_pending_for_agent,
    get_receiver_state,
    process_session_start,
)


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


def _make_revival_agent(previous_agent_id=5):
    """Create a mock agent configured as a revival successor."""
    agent = MagicMock()
    agent.id = 10
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None
    agent.state.value = "idle"
    agent.get_current_command.return_value = None
    agent.tmux_pane_id = "%42"
    agent.context_updated_at = None
    agent.persona_id = None
    agent.previous_agent_id = previous_agent_id
    agent.tmux_session = None
    return agent


class TestRevivalInjection:
    """Tests for revival injection during session_start."""

    @patch("claude_headspace.services.revival_service.db")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_revival_injection_fires_for_revival_successor(
        self, mock_hr_db, mock_rs_db, fresh_state, app
    ):
        """Revival injection should fire when previous_agent_id is set and no Handoff exists."""
        agent = _make_revival_agent(previous_agent_id=5)

        # No handoff record on predecessor -> this is a revival
        mock_rs_db.session.query.return_value.filter.return_value.first.return_value = None

        # Handoff executor returns no_handoff_record
        with app.app_context():
            handoff_executor = MagicMock()
            handoff_result = MagicMock()
            handoff_result.success = False
            handoff_result.error_code = "no_handoff_record"
            handoff_executor.deliver_injection_prompt.return_value = handoff_result
            app.extensions["handoff_executor"] = handoff_executor

            # Patch tmux_bridge where it's imported in the hook_receiver
            with patch("claude_headspace.services.tmux_bridge.send_text") as mock_send:
                mock_send.return_value = MagicMock(success=True)
                result = process_session_start(agent, "session-123")

                assert result.success
                # Verify tmux_bridge.send_text was called with the revival instruction
                mock_send.assert_called()
                call_args = mock_send.call_args
                assert agent.tmux_pane_id == call_args[0][0]
                revival_msg = call_args[0][1]
                assert "claude-headspace transcript 5" in revival_msg
                assert "predecessor" in revival_msg.lower()

    @patch("claude_headspace.services.hook_receiver.db")
    def test_revival_injection_skipped_for_handoff_successor(
        self, mock_db, fresh_state, app
    ):
        """Revival injection should NOT fire when handoff injection succeeds."""
        agent = _make_revival_agent(previous_agent_id=5)

        with app.app_context():
            # Handoff executor delivers successfully -> this is a handoff, not revival
            handoff_executor = MagicMock()
            handoff_result = MagicMock()
            handoff_result.success = True
            handoff_executor.deliver_injection_prompt.return_value = handoff_result
            app.extensions["handoff_executor"] = handoff_executor

            result = process_session_start(agent, "session-123")

        assert result.success
        # Revival injection should NOT have been attempted

    @patch("claude_headspace.services.hook_receiver.db")
    def test_no_injection_without_previous_agent(self, mock_db, fresh_state, app):
        """No injection when agent has no previous_agent_id."""
        agent = MagicMock()
        agent.id = 10
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None
        agent.state.value = "idle"
        agent.get_current_command.return_value = None
        agent.tmux_pane_id = "%42"
        agent.context_updated_at = None
        agent.persona_id = None
        agent.previous_agent_id = None
        agent.tmux_session = None

        with app.app_context():
            result = process_session_start(agent, "session-123")

        assert result.success

    @patch("claude_headspace.services.revival_service.db")
    @patch("claude_headspace.services.hook_receiver.db")
    def test_revival_injection_failure_does_not_block(
        self, mock_hr_db, mock_rs_db, fresh_state, app
    ):
        """If revival injection fails, session_start should still succeed."""
        agent = _make_revival_agent(previous_agent_id=5)

        # No handoff record
        mock_rs_db.session.query.return_value.filter.return_value.first.return_value = None

        with app.app_context():
            handoff_executor = MagicMock()
            handoff_result = MagicMock()
            handoff_result.success = False
            handoff_result.error_code = "no_handoff_record"
            handoff_executor.deliver_injection_prompt.return_value = handoff_result
            app.extensions["handoff_executor"] = handoff_executor

            # Patch tmux_bridge where it's imported
            with patch("claude_headspace.services.tmux_bridge.send_text") as mock_send:
                # tmux send fails
                mock_send.return_value = MagicMock(
                    success=False, error_message="pane not found"
                )

                result = process_session_start(agent, "session-123")

        # Should still succeed even though injection failed
        assert result.success
