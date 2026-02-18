"""Unit tests for summarisation API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.summarisation import summarisation_bp


@pytest.fixture
def app():
    """Create a test Flask application with summarisation blueprint."""
    app = Flask(__name__)
    app.register_blueprint(summarisation_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service():
    service = MagicMock()
    return service


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    return service


class TestTurnSummarisationEndpoint:

    def test_summarise_turn_success(self, app, client, mock_service, mock_inference):
        app.extensions["summarisation_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_turn = MagicMock()
        mock_turn.summary = None
        mock_turn.summary_generated_at = None
        mock_service.summarise_turn.return_value = "Generated summary"
        # After summarise_turn is called, summary is set
        def set_summary(turn, db_session=None):
            turn.summary = "Generated summary"
            from datetime import datetime, timezone
            turn.summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
            return "Generated summary"
        mock_service.summarise_turn.side_effect = set_summary

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] == "Generated summary"
        assert data["turn_id"] == 1
        assert data["cached"] is False

    def test_summarise_turn_existing_summary(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service

        mock_turn = MagicMock()
        mock_turn.summary = "Existing summary"
        from datetime import datetime, timezone
        mock_turn.summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] == "Existing summary"
        assert data["cached"] is True
        mock_service.summarise_turn.assert_not_called()

    def test_summarise_turn_not_found(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/summarise/turn/999")

        assert response.status_code == 404

    def test_summarise_turn_no_service(self, app, client):
        app.extensions.pop("summarisation_service", None)
        response = client.post("/api/summarise/turn/1")

        assert response.status_code == 503

    def test_summarise_turn_inference_unavailable(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service
        mock_inference = MagicMock()
        mock_inference.is_available = False
        app.extensions["inference_service"] = mock_inference

        mock_turn = MagicMock()
        mock_turn.summary = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 503


class TestCommandSummarisationEndpoint:

    def test_summarise_command_success(self, app, client, mock_service, mock_inference):
        app.extensions["summarisation_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_cmd = MagicMock()
        mock_cmd.completion_summary = None
        mock_cmd.completion_summary_generated_at = None
        def set_summary(cmd, db_session=None):
            cmd.completion_summary = "Command summary"
            from datetime import datetime, timezone
            cmd.completion_summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
            return "Command summary"
        mock_service.summarise_command.side_effect = set_summary

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_cmd
            response = client.post("/api/summarise/command/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] == "Command summary"
        assert data["command_id"] == 1

    def test_summarise_command_existing_summary(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service

        mock_cmd = MagicMock()
        mock_cmd.completion_summary = "Already done"
        from datetime import datetime, timezone
        mock_cmd.completion_summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_cmd
            response = client.post("/api/summarise/command/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["cached"] is True
        mock_service.summarise_command.assert_not_called()

    def test_summarise_command_not_found(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/summarise/command/999")

        assert response.status_code == 404

    def test_summarise_command_no_service(self, app, client):
        app.extensions.pop("summarisation_service", None)
        response = client.post("/api/summarise/command/1")

        assert response.status_code == 503

    def test_summarise_command_inference_unavailable(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service
        mock_inference = MagicMock()
        mock_inference.is_available = False
        app.extensions["inference_service"] = mock_inference

        mock_cmd = MagicMock()
        mock_cmd.completion_summary = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_cmd
            response = client.post("/api/summarise/command/1")

        assert response.status_code == 503
