"""Tests for archive API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.archive import archive_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(archive_bp)

    mock_service = MagicMock()
    app.extensions["archive_service"] = mock_service

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service(app):
    return app.extensions["archive_service"]


def _mock_project(project_id=1, name="Test Project", path="/tmp/test"):
    project = MagicMock()
    project.id = project_id
    project.name = name
    project.path = path
    return project


class TestListArchives:
    """Tests for GET /api/projects/<id>/archives."""

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_grouped_archives(self, mock_db, client, mock_service):
        """Should return 200 with grouped archive listing."""
        project = _mock_project()
        mock_db.session.get.return_value = project
        mock_service.list_archives.return_value = {
            "waypoint": [
                {"filename": "waypoint_2026-01-28_14-30-00.md", "timestamp": "2026-01-28T14:30:00Z"},
            ],
            "progress_summary": [],
            "brain_reboot": [],
        }

        response = client.get("/api/projects/1/archives")

        assert response.status_code == 200
        data = response.get_json()
        assert data["project_id"] == 1
        assert len(data["archives"]["waypoint"]) == 1
        assert data["archives"]["progress_summary"] == []

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_empty_list_when_no_archives(self, mock_db, client, mock_service):
        """Should return 200 with empty lists when no archives exist."""
        project = _mock_project()
        mock_db.session.get.return_value = project
        mock_service.list_archives.return_value = {
            "waypoint": [],
            "progress_summary": [],
            "brain_reboot": [],
        }

        response = client.get("/api/projects/1/archives")

        assert response.status_code == 200
        data = response.get_json()
        for atype in ["waypoint", "progress_summary", "brain_reboot"]:
            assert data["archives"][atype] == []

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_404_for_missing_project(self, mock_db, client):
        """Should return 404 when project not found."""
        mock_db.session.get.return_value = None

        response = client.get("/api/projects/999/archives")

        assert response.status_code == 404

    def test_returns_503_when_service_unavailable(self, client, app):
        """Should return 503 when archive service not registered."""
        del app.extensions["archive_service"]

        response = client.get("/api/projects/1/archives")

        assert response.status_code == 503


class TestGetArchive:
    """Tests for GET /api/projects/<id>/archives/<artifact>/<timestamp>."""

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_archive_content(self, mock_db, client, mock_service):
        """Should return 200 with archive content."""
        project = _mock_project()
        mock_db.session.get.return_value = project
        mock_service.get_archive.return_value = {
            "artifact": "waypoint",
            "timestamp": "2026-01-28T14:30:00Z",
            "filename": "waypoint_2026-01-28_14-30-00.md",
            "content": "# Waypoint v1",
        }

        response = client.get("/api/projects/1/archives/waypoint/2026-01-28_14-30-00")

        assert response.status_code == 200
        data = response.get_json()
        assert data["artifact"] == "waypoint"
        assert data["content"] == "# Waypoint v1"

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_404_for_missing_archive(self, mock_db, client, mock_service):
        """Should return 404 when archive not found."""
        project = _mock_project()
        mock_db.session.get.return_value = project
        mock_service.get_archive.return_value = None

        response = client.get("/api/projects/1/archives/waypoint/2026-01-01_00-00-00")

        assert response.status_code == 404

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_400_for_invalid_artifact(self, mock_db, client, mock_service):
        """Should return 400 for invalid artifact type."""
        project = _mock_project()
        mock_db.session.get.return_value = project

        response = client.get("/api/projects/1/archives/invalid_type/2026-01-28_14-30-00")

        assert response.status_code == 400
        data = response.get_json()
        assert "invalid_artifact" in data["error"]

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_400_for_invalid_timestamp(self, mock_db, client, mock_service):
        """Should return 400 for invalid timestamp format."""
        project = _mock_project()
        mock_db.session.get.return_value = project

        response = client.get("/api/projects/1/archives/waypoint/not-a-timestamp")

        assert response.status_code == 400
        data = response.get_json()
        assert "invalid_timestamp" in data["error"]

    @patch("src.claude_headspace.routes.archive.db")
    def test_returns_404_for_missing_project(self, mock_db, client):
        """Should return 404 when project not found."""
        mock_db.session.get.return_value = None

        response = client.get("/api/projects/999/archives/waypoint/2026-01-28_14-30-00")

        assert response.status_code == 404
