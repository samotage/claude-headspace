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


class TestTaskSummarisationEndpoint:

    def test_summarise_task_success(self, app, client, mock_service, mock_inference):
        app.extensions["summarisation_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_task.completion_summary_generated_at = None
        def set_summary(task, db_session=None):
            task.completion_summary = "Task summary"
            from datetime import datetime, timezone
            task.completion_summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
            return "Task summary"
        mock_service.summarise_task.side_effect = set_summary

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] == "Task summary"
        assert data["task_id"] == 1

    def test_summarise_task_existing_summary(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service

        mock_task = MagicMock()
        mock_task.completion_summary = "Already done"
        from datetime import datetime, timezone
        mock_task.completion_summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["cached"] is True
        mock_service.summarise_task.assert_not_called()

    def test_summarise_task_not_found(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/summarise/task/999")

        assert response.status_code == 404

    def test_summarise_task_no_service(self, app, client):
        app.extensions.pop("summarisation_service", None)
        response = client.post("/api/summarise/task/1")

        assert response.status_code == 503

    def test_summarise_task_inference_unavailable(self, app, client, mock_service):
        app.extensions["summarisation_service"] = mock_service
        mock_inference = MagicMock()
        mock_inference.is_available = False
        app.extensions["inference_service"] = mock_inference

        mock_task = MagicMock()
        mock_task.completion_summary = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 503
