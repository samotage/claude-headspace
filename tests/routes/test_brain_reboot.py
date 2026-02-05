"""Tests for brain reboot API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.brain_reboot import brain_reboot_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(brain_reboot_bp)

    mock_service = MagicMock()
    app.extensions["brain_reboot_service"] = mock_service

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service(app):
    return app.extensions["brain_reboot_service"]


def _mock_project(project_id=1, name="Test Project", path="/tmp/test"):
    project = MagicMock()
    project.id = project_id
    project.name = name
    project.path = path
    return project


class TestGenerateEndpoint:
    def test_success(self, client, mock_service):
        mock_service.generate.return_value = {
            "content": "# Brain Reboot",
            "metadata": {"generated_at": "2026-01-31T12:00:00"},
            "status": "generated",
            "has_waypoint": True,
            "has_summary": True,
        }

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.post("/api/projects/1/brain-reboot")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "generated"
        assert data["has_waypoint"] is True

    def test_project_not_found(self, client, mock_service):
        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/projects/999/brain-reboot")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "not found" in data["error"].lower()

    def test_no_service(self, app):
        app.extensions.pop("brain_reboot_service")
        client = app.test_client()

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.post("/api/projects/1/brain-reboot")

        assert response.status_code == 503

    def test_generation_error(self, client, mock_service):
        mock_service.generate.side_effect = Exception("Disk full")

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.post("/api/projects/1/brain-reboot")

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "failed" in data["error"].lower()


class TestGetEndpoint:
    def test_success(self, client, mock_service):
        mock_service.get_last_generated.return_value = {
            "content": "# Brain Reboot",
            "metadata": {"generated_at": "2026-01-31T12:00:00"},
            "status": "generated",
        }

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.get("/api/projects/1/brain-reboot")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "generated"

    def test_not_generated_yet(self, client, mock_service):
        mock_service.get_last_generated.return_value = None

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.get("/api/projects/1/brain-reboot")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["status"] == "not_found"

    def test_project_not_found(self, client, mock_service):
        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = None
            response = client.get("/api/projects/999/brain-reboot")

        assert response.status_code == 404

    def test_no_service(self, app):
        app.extensions.pop("brain_reboot_service")
        client = app.test_client()

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.get("/api/projects/1/brain-reboot")

        assert response.status_code == 503


class TestExportEndpoint:
    def test_success(self, client, mock_service):
        mock_service.get_last_generated.return_value = {
            "content": "# Brain Reboot content",
            "status": "generated",
        }
        mock_service.export.return_value = {
            "success": True,
            "path": "/tmp/test/brain_reboot/brain_reboot.md",
            "error": None,
        }

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.post("/api/projects/1/brain-reboot/export")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "exported"
        assert "path" in data

    def test_not_generated_yet(self, client, mock_service):
        mock_service.get_last_generated.return_value = None

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.post("/api/projects/1/brain-reboot/export")

        assert response.status_code == 404

    def test_export_failure(self, client, mock_service):
        mock_service.get_last_generated.return_value = {
            "content": "content",
            "status": "generated",
        }
        mock_service.export.return_value = {
            "success": False,
            "path": "/tmp/test/brain_reboot/brain_reboot.md",
            "error": "Permission denied",
        }

        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = _mock_project()
            response = client.post("/api/projects/1/brain-reboot/export")

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "Permission denied" in data["error"]

    def test_project_not_found(self, client, mock_service):
        with patch(
            "src.claude_headspace.database.db"
        ) as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/projects/999/brain-reboot/export")

        assert response.status_code == 404
