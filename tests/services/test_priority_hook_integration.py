"""Unit tests for priority scoring hook integration."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from claude_headspace.services.hook_helpers import trigger_priority_scoring as _trigger_priority_scoring


@pytest.fixture
def app():
    """Create a minimal Flask app for testing app context."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestTriggerPriorityScoring:

    def test_graceful_no_app(self, app):
        """_trigger_priority_scoring handles missing Flask app context."""
        with app.app_context():
            # No priority_scoring_service in extensions
            _trigger_priority_scoring()

    def test_calls_service(self, app):
        """_trigger_priority_scoring calls service.trigger_scoring()."""
        mock_service = MagicMock()
        with app.app_context():
            app.extensions["priority_scoring_service"] = mock_service
            _trigger_priority_scoring()
            mock_service.trigger_scoring.assert_called_once()

    def test_graceful_outside_context(self):
        """_trigger_priority_scoring handles being called outside app context."""
        _trigger_priority_scoring()  # Should not raise
