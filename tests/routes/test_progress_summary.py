"""Unit tests for progress summary API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.progress_summary import progress_summary_bp


@pytest.fixture
def app():
    """Create a test Flask application with progress summary blueprint."""
    app = Flask(__name__)
    app.register_blueprint(progress_summary_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.is_generating.return_value = False
    return service


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    return service


@pytest.fixture
def mock_project():
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.path = "/test/path"
    return project


class TestGenerateEndpoint:

    def test_generate_success(self, app, client, mock_service, mock_inference, mock_project):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_service.generate.return_value = {
            "summary": "Progress summary text.",
            "metadata": {
                "generated_at": "2026-01-31T10:00:00+00:00",
                "scope": "last_n",
                "commit_count": 5,
            },
            "status": "success",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.post("/api/projects/1/progress-summary")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert "Progress summary text." in data["summary"]

    def test_generate_with_scope_override(self, app, client, mock_service, mock_inference, mock_project):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_service.generate.return_value = {
            "status": "success",
            "summary": "Summary.",
            "metadata": {},
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.post(
                "/api/projects/1/progress-summary",
                data=json.dumps({"scope": "time_based"}),
                content_type="application/json",
            )

        assert response.status_code == 200
        mock_service.generate.assert_called_once_with(mock_project, scope="time_based")

    def test_generate_project_not_found(self, app, client, mock_service, mock_inference):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/projects/999/progress-summary")

        assert response.status_code == 404

    def test_generate_not_git_repo(self, app, client, mock_service, mock_inference, mock_project):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_service.generate.return_value = {
            "error": "Not a git repository: /test/path",
            "status": "error",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.post("/api/projects/1/progress-summary")

        assert response.status_code == 422

    def test_generate_already_in_progress(self, app, client, mock_service, mock_inference, mock_project):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference
        mock_service.is_generating.return_value = True

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.post("/api/projects/1/progress-summary")

        assert response.status_code == 409

    def test_generate_no_service(self, app, client):
        app.extensions.pop("progress_summary_service", None)
        response = client.post("/api/projects/1/progress-summary")
        assert response.status_code == 503

    def test_generate_inference_unavailable(self, app, client, mock_service):
        app.extensions["progress_summary_service"] = mock_service
        mock_inf = MagicMock()
        mock_inf.is_available = False
        app.extensions["inference_service"] = mock_inf

        response = client.post("/api/projects/1/progress-summary")
        assert response.status_code == 503

    def test_generate_empty_scope(self, app, client, mock_service, mock_inference, mock_project):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_service.generate.return_value = {
            "message": "No commits found in configured scope",
            "status": "empty",
            "scope_used": "last_n",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.post("/api/projects/1/progress-summary")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "empty"

    def test_generate_generic_error(self, app, client, mock_service, mock_inference, mock_project):
        app.extensions["progress_summary_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_service.generate.return_value = {
            "error": "Inference failed: API error",
            "status": "error",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.post("/api/projects/1/progress-summary")

        assert response.status_code == 500


class TestGetSummaryEndpoint:

    def test_get_summary_success(self, app, client, mock_service, mock_project):
        app.extensions["progress_summary_service"] = mock_service

        mock_service.get_current_summary.return_value = {
            "summary": "Summary content.",
            "metadata": {"generated_at": "2026-01-31T10:00:00+00:00"},
            "status": "found",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.get("/api/projects/1/progress-summary")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "found"
        assert "Summary content." in data["summary"]

    def test_get_summary_not_found(self, app, client, mock_service, mock_project):
        app.extensions["progress_summary_service"] = mock_service

        mock_service.get_current_summary.return_value = {"status": "not_found"}

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.get("/api/projects/1/progress-summary")

        assert response.status_code == 404

    def test_get_summary_project_not_found(self, app, client, mock_service):
        app.extensions["progress_summary_service"] = mock_service

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.get("/api/projects/999/progress-summary")

        assert response.status_code == 404

    def test_get_summary_no_service(self, app, client):
        app.extensions.pop("progress_summary_service", None)
        response = client.get("/api/projects/1/progress-summary")
        assert response.status_code == 503

    def test_get_summary_read_error(self, app, client, mock_service, mock_project):
        app.extensions["progress_summary_service"] = mock_service

        mock_service.get_current_summary.return_value = {
            "error": "Failed to read summary: Permission denied",
            "status": "error",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_project
            response = client.get("/api/projects/1/progress-summary")

        assert response.status_code == 500
