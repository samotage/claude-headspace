"""Unit tests for priority scoring hook integration and SSE broadcast."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.services.hook_lifecycle_bridge import HookLifecycleBridge


@pytest.fixture
def app():
    """Create a minimal Flask app for testing app context."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def bridge():
    return HookLifecycleBridge(event_writer=None)


class TestHookPriorityScoringTrigger:

    def test_scoring_triggered_on_user_prompt(self, bridge):
        """process_user_prompt_submit triggers priority scoring on success."""
        mock_agent = MagicMock()
        mock_agent.id = 1

        with patch.object(bridge, "_get_lifecycle_manager") as mock_lm, \
             patch.object(HookLifecycleBridge, "_trigger_priority_scoring") as mock_trigger:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.task = MagicMock()
            mock_result.task.state = MagicMock()
            mock_result.task.state.__eq__ = lambda self, other: False  # Not COMMANDED
            mock_lm.return_value.process_turn.return_value = mock_result

            bridge.process_user_prompt_submit(mock_agent, "session-123", "Fix the bug")
            mock_trigger.assert_called_once()

    def test_scoring_not_triggered_on_failure(self, bridge):
        """process_user_prompt_submit does not trigger scoring on failure."""
        mock_agent = MagicMock()
        mock_agent.id = 1

        with patch.object(bridge, "_get_lifecycle_manager") as mock_lm, \
             patch.object(HookLifecycleBridge, "_trigger_priority_scoring") as mock_trigger:
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.task = None
            mock_lm.return_value.process_turn.return_value = mock_result

            bridge.process_user_prompt_submit(mock_agent, "session-123", "Fix the bug")
            mock_trigger.assert_not_called()

    def test_scoring_triggered_on_stop(self, bridge):
        """process_stop triggers priority scoring."""
        mock_agent = MagicMock()
        mock_agent.id = 1

        with patch.object(bridge, "_get_lifecycle_manager") as mock_lm, \
             patch.object(HookLifecycleBridge, "_trigger_priority_scoring") as mock_trigger:
            mock_task = MagicMock()
            mock_lm.return_value.get_current_task.return_value = mock_task

            bridge.process_stop(mock_agent, "session-123")
            mock_trigger.assert_called_once()

    def test_trigger_priority_scoring_graceful_no_app(self, app):
        """_trigger_priority_scoring handles missing Flask app context."""
        with app.app_context():
            # No priority_scoring_service in extensions
            HookLifecycleBridge._trigger_priority_scoring()

    def test_trigger_priority_scoring_calls_service(self, app):
        """_trigger_priority_scoring calls service.trigger_scoring()."""
        mock_service = MagicMock()

        with app.app_context():
            app.extensions["priority_scoring_service"] = mock_service
            HookLifecycleBridge._trigger_priority_scoring()
            mock_service.trigger_scoring.assert_called_once()
