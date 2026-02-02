"""Tests for waypoint API routes."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.waypoint import waypoint_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(waypoint_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestListProjects:
    """Tests for GET /api/projects."""

    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_projects_list(self, mock_db, client):
        """Should return list of projects."""
        mock_project1 = MagicMock()
        mock_project1.id = 1
        mock_project1.name = "Alpha"
        mock_project1.path = "/path/to/alpha"

        mock_project2 = MagicMock()
        mock_project2.id = 2
        mock_project2.name = "Beta"
        mock_project2.path = "/path/to/beta"

        mock_query = MagicMock()
        mock_query.order_by.return_value.all.return_value = [mock_project1, mock_project2]
        mock_db.session.query.return_value = mock_query

        response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.get_json()
        assert "projects" in data
        assert len(data["projects"]) == 2
        assert data["projects"][0]["name"] == "Alpha"
        assert data["projects"][1]["name"] == "Beta"

    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_empty_list(self, mock_db, client):
        """Should return empty list when no projects."""
        mock_query = MagicMock()
        mock_query.order_by.return_value.all.return_value = []
        mock_db.session.query.return_value = mock_query

        response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.get_json()
        assert data["projects"] == []


class TestGetWaypoint:
    """Tests for GET /api/projects/<id>/waypoint."""

    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_404_for_unknown_project(self, mock_db, client):
        """Should return 404 when project not found."""
        mock_db.session.get.return_value = None

        response = client.get("/api/projects/999/waypoint")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "not_found"

    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_500_for_invalid_path(self, mock_db, mock_validate, client):
        """Should return 500 when project path is invalid."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/invalid/path"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (False, "Path does not exist")

        response = client.get("/api/projects/1/waypoint")

        assert response.status_code == 500
        data = response.get_json()
        assert data["error"] == "path_error"

    @patch("src.claude_headspace.routes.waypoint.load_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_waypoint_content(self, mock_db, mock_validate, mock_load, client):
        """Should return waypoint content when file exists."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "TestProject"
        mock_project.path = "/path/to/project"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import WaypointResult
        mock_load.return_value = WaypointResult(
            content="# My Waypoint",
            exists=True,
            template=False,
            path="/path/to/project/docs/brain_reboot/waypoint.md",
            last_modified=datetime(2026, 1, 29, 10, 30, tzinfo=timezone.utc),
        )

        response = client.get("/api/projects/1/waypoint")

        assert response.status_code == 200
        data = response.get_json()
        assert data["project_id"] == 1
        assert data["project_name"] == "TestProject"
        assert data["exists"] is True
        assert data["content"] == "# My Waypoint"
        assert "last_modified" in data

    @patch("src.claude_headspace.routes.waypoint.load_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_template_when_missing(self, mock_db, mock_validate, mock_load, client):
        """Should return template when waypoint doesn't exist."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "TestProject"
        mock_project.path = "/path/to/project"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import WaypointResult, DEFAULT_TEMPLATE
        mock_load.return_value = WaypointResult(
            content=DEFAULT_TEMPLATE,
            exists=False,
            template=True,
            path="/path/to/project/docs/brain_reboot/waypoint.md",
            last_modified=None,
        )

        response = client.get("/api/projects/1/waypoint")

        assert response.status_code == 200
        data = response.get_json()
        assert data["exists"] is False
        assert data["template"] is True


class TestPostWaypoint:
    """Tests for POST /api/projects/<id>/waypoint."""

    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_404_for_unknown_project(self, mock_db, client):
        """Should return 404 when project not found."""
        mock_db.session.get.return_value = None

        response = client.post(
            "/api/projects/999/waypoint",
            json={"content": "# Waypoint"},
        )

        assert response.status_code == 404

    def test_requires_json_content_type(self, client):
        """Should require JSON content type."""
        with patch("src.claude_headspace.routes.waypoint.db") as mock_db:
            mock_project = MagicMock()
            mock_project.id = 1
            mock_project.path = "/path"
            mock_db.session.get.return_value = mock_project

            with patch("src.claude_headspace.routes.waypoint.validate_project_path") as mock_validate:
                mock_validate.return_value = (True, None)

                response = client.post(
                    "/api/projects/1/waypoint",
                    data="not json",
                )

                assert response.status_code == 400
                data = response.get_json()
                assert "application/json" in data["message"]

    def test_requires_content_field(self, client):
        """Should require content field."""
        with patch("src.claude_headspace.routes.waypoint.db") as mock_db:
            mock_project = MagicMock()
            mock_project.id = 1
            mock_project.path = "/path"
            mock_db.session.get.return_value = mock_project

            with patch("src.claude_headspace.routes.waypoint.validate_project_path") as mock_validate:
                mock_validate.return_value = (True, None)

                response = client.post(
                    "/api/projects/1/waypoint",
                    json={},
                )

                assert response.status_code == 400
                data = response.get_json()
                assert "content" in data["message"]

    @patch("src.claude_headspace.routes.waypoint.save_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_saves_waypoint_successfully(self, mock_db, mock_validate, mock_save, client):
        """Should save waypoint and return success."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/path/to/project"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import SaveResult
        mock_save.return_value = SaveResult(
            success=True,
            archived=True,
            archive_path="archive/waypoint_2026-01-29.md",
            last_modified=datetime(2026, 1, 29, 11, 0, tzinfo=timezone.utc),
        )

        response = client.post(
            "/api/projects/1/waypoint",
            json={"content": "# New Waypoint"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["archived"] is True
        assert "archive_path" in data
        assert "last_modified" in data

    @patch("src.claude_headspace.routes.waypoint.save_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_409_on_conflict(self, mock_db, mock_validate, mock_save, client):
        """Should return 409 on conflict."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/path/to/project"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import SaveResult
        mock_save.return_value = SaveResult(
            success=False,
            archived=False,
            archive_path=None,
            last_modified=datetime(2026, 1, 29, 10, 45, tzinfo=timezone.utc),
            error="conflict",
        )

        response = client.post(
            "/api/projects/1/waypoint",
            json={
                "content": "# New Waypoint",
                "expected_mtime": "2026-01-29T10:30:00Z",
            },
        )

        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "conflict"

    @patch("src.claude_headspace.routes.waypoint.save_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_403_on_permission_denied(self, mock_db, mock_validate, mock_save, client):
        """Should return 403 on permission denied."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/path/to/project"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import SaveResult
        mock_save.return_value = SaveResult(
            success=False,
            archived=False,
            archive_path=None,
            last_modified=None,
            error="Permission denied: /path/to/project/docs/brain_reboot/waypoint.md",
        )

        response = client.post(
            "/api/projects/1/waypoint",
            json={"content": "# Waypoint"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert data["error"] == "permission_denied"


class TestExpectedMtimeParsing:
    """Tests for expected_mtime parsing."""

    @patch("src.claude_headspace.routes.waypoint.save_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_parses_iso_format_with_z(self, mock_db, mock_validate, mock_save, client):
        """Should parse ISO format with Z suffix."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/path"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import SaveResult
        mock_save.return_value = SaveResult(
            success=True, archived=False, archive_path=None,
            last_modified=datetime.now(timezone.utc)
        )

        response = client.post(
            "/api/projects/1/waypoint",
            json={
                "content": "# Waypoint",
                "expected_mtime": "2026-01-29T10:30:00Z",
            },
        )

        assert response.status_code == 200
        # Verify save_waypoint was called with datetime
        call_args = mock_save.call_args
        assert call_args[0][2] is not None  # expected_mtime arg

    @patch("src.claude_headspace.routes.waypoint.save_waypoint")
    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_parses_iso_format_with_offset(self, mock_db, mock_validate, mock_save, client):
        """Should parse ISO format with timezone offset."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/path"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        from claude_headspace.services.waypoint_editor import SaveResult
        mock_save.return_value = SaveResult(
            success=True, archived=False, archive_path=None,
            last_modified=datetime.now(timezone.utc)
        )

        response = client.post(
            "/api/projects/1/waypoint",
            json={
                "content": "# Waypoint",
                "expected_mtime": "2026-01-29T10:30:00+00:00",
            },
        )

        assert response.status_code == 200

    @patch("src.claude_headspace.routes.waypoint.validate_project_path")
    @patch("src.claude_headspace.routes.waypoint.db")
    def test_returns_400_for_invalid_mtime(self, mock_db, mock_validate, client):
        """Should return 400 for invalid mtime format."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.path = "/path"
        mock_db.session.get.return_value = mock_project
        mock_validate.return_value = (True, None)

        response = client.post(
            "/api/projects/1/waypoint",
            json={
                "content": "# Waypoint",
                "expected_mtime": "not-a-date",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "ISO 8601" in data["message"]
