"""Tests for the projects API routes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.projects import projects_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(projects_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("src.claude_headspace.routes.projects.db") as mock:
        mock.session = MagicMock()
        yield mock


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.path = "/path/to/project"
    project.github_repo = "https://github.com/test/repo"
    project.description = "A test project"
    project.current_branch = "main"
    project.inference_paused = False
    project.inference_paused_at = None
    project.inference_paused_reason = None
    project.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    project.agents = []
    return project


@pytest.fixture
def mock_project_with_agents(mock_project):
    """Create a mock project with agents."""
    active_agent = MagicMock()
    active_agent.id = 1
    active_agent.session_uuid = "uuid-1"
    active_agent.state.value = "idle"
    active_agent.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    active_agent.ended_at = None

    ended_agent = MagicMock()
    ended_agent.id = 2
    ended_agent.session_uuid = "uuid-2"
    ended_agent.state.value = "idle"
    ended_agent.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ended_agent.ended_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

    mock_project.agents = [active_agent, ended_agent]
    return mock_project


class TestListProjects:
    """Tests for GET /api/projects."""

    def test_list_empty(self, client, mock_db):
        """Test listing when no projects exist."""
        mock_db.session.query.return_value.order_by.return_value.all.return_value = []

        response = client.get("/api/projects")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_with_projects(self, client, mock_db, mock_project_with_agents):
        """Test listing projects with agent counts."""
        mock_db.session.query.return_value.order_by.return_value.all.return_value = [
            mock_project_with_agents
        ]

        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["name"] == "test-project"
        assert data[0]["agent_count"] == 1  # Only active agents

    def test_list_includes_all_fields(self, client, mock_db, mock_project):
        """Test that list response includes required fields."""
        mock_db.session.query.return_value.order_by.return_value.all.return_value = [mock_project]

        response = client.get("/api/projects")
        data = response.get_json()[0]
        assert "id" in data
        assert "name" in data
        assert "path" in data
        assert "github_repo" in data
        assert "description" in data
        assert "current_branch" in data
        assert "inference_paused" in data
        assert "created_at" in data
        assert "agent_count" in data


class TestCreateProject:
    """Tests for POST /api/projects."""

    def test_missing_body(self, client):
        """Test error when request body is missing."""
        response = client.post("/api/projects", data="", content_type="application/json")
        assert response.status_code == 400
        assert "Request body is required" in response.get_json()["error"]

    def test_missing_required_fields(self, client):
        """Test error when required fields are missing."""
        response = client.post("/api/projects", json={"name": "test"})
        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    def test_missing_name(self, client):
        """Test error when name is missing."""
        response = client.post("/api/projects", json={"path": "/some/path"})
        assert response.status_code == 400

    def test_create_success(self, client, mock_db):
        """Test creating a project successfully."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = None

            mock_project = MagicMock()
            mock_project.id = 1
            mock_project.name = "new-project"
            mock_project.path = "/path/to/new"
            mock_project.github_repo = None
            mock_project.description = None
            mock_project.inference_paused = False
            mock_project.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            MockProject.return_value = mock_project

            response = client.post("/api/projects", json={
                "name": "new-project",
                "path": "/path/to/new",
            })

            assert response.status_code == 201
            data = response.get_json()
            assert data["id"] == 1
            assert data["name"] == "new-project"

    def test_duplicate_path_returns_409(self, client, mock_db, mock_project):
        """Test creating project with duplicate path returns 409."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = mock_project

            response = client.post("/api/projects", json={
                "name": "another-project",
                "path": "/path/to/project",
            })

            assert response.status_code == 409
            assert "already exists" in response.get_json()["error"]

    def test_create_with_optional_fields(self, client, mock_db):
        """Test creating project with optional fields."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = None

            mock_project = MagicMock()
            mock_project.id = 1
            mock_project.name = "project"
            mock_project.path = "/path"
            mock_project.github_repo = "https://github.com/test/repo"
            mock_project.description = "A description"
            mock_project.inference_paused = False
            mock_project.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            MockProject.return_value = mock_project

            response = client.post("/api/projects", json={
                "name": "project",
                "path": "/path",
                "github_repo": "https://github.com/test/repo",
                "description": "A description",
            })

            assert response.status_code == 201


class TestGetProject:
    """Tests for GET /api/projects/<id>."""

    def test_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.get("/api/projects/999")
        assert response.status_code == 404

    def test_get_success(self, client, mock_db, mock_project_with_agents):
        """Test successful project retrieval with agents."""
        mock_db.session.get.return_value = mock_project_with_agents

        response = client.get("/api/projects/1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == 1
        assert data["name"] == "test-project"
        assert "agents" in data
        assert len(data["agents"]) == 2

    def test_get_includes_inference_fields(self, client, mock_db, mock_project):
        """Test that get response includes inference fields."""
        mock_db.session.get.return_value = mock_project

        response = client.get("/api/projects/1")
        data = response.get_json()
        assert "inference_paused" in data
        assert "inference_paused_at" in data
        assert "inference_paused_reason" in data


class TestUpdateProject:
    """Tests for PUT /api/projects/<id>."""

    def test_missing_body(self, client, mock_db):
        """Test error when request body is missing."""
        response = client.put("/api/projects/1", data="", content_type="application/json")
        assert response.status_code == 400

    def test_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.put("/api/projects/999", json={"name": "updated"})
        assert response.status_code == 404

    def test_update_success(self, client, mock_db, mock_project):
        """Test successful project update."""
        mock_db.session.get.return_value = mock_project

        response = client.put("/api/projects/1", json={"name": "updated-name"})
        assert response.status_code == 200
        assert mock_project.name == "updated-name"

    def test_path_conflict_returns_409(self, client, mock_db, mock_project):
        """Test updating path to conflicting value returns 409."""
        mock_db.session.get.return_value = mock_project

        conflicting = MagicMock()
        conflicting.id = 2

        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = conflicting

            response = client.put("/api/projects/1", json={"path": "/other/path"})
            assert response.status_code == 409

    def test_update_description(self, client, mock_db, mock_project):
        """Test updating description."""
        mock_db.session.get.return_value = mock_project

        response = client.put("/api/projects/1", json={"description": "New description"})
        assert response.status_code == 200
        assert mock_project.description == "New description"


class TestDeleteProject:
    """Tests for DELETE /api/projects/<id>."""

    def test_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.delete("/api/projects/999")
        assert response.status_code == 404

    def test_delete_success(self, client, mock_db, mock_project):
        """Test successful project deletion."""
        mock_db.session.get.return_value = mock_project

        response = client.delete("/api/projects/1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["deleted"] is True
        assert data["id"] == 1
        mock_db.session.delete.assert_called_once_with(mock_project)


class TestGetProjectSettings:
    """Tests for GET /api/projects/<id>/settings."""

    def test_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.get("/api/projects/999/settings")
        assert response.status_code == 404

    def test_get_settings_success(self, client, mock_db, mock_project):
        """Test successful settings retrieval."""
        mock_db.session.get.return_value = mock_project

        response = client.get("/api/projects/1/settings")
        assert response.status_code == 200
        data = response.get_json()
        assert data["inference_paused"] is False
        assert data["inference_paused_at"] is None
        assert data["inference_paused_reason"] is None


class TestUpdateProjectSettings:
    """Tests for PUT /api/projects/<id>/settings."""

    def test_missing_body(self, client, mock_db):
        """Test error when request body is missing."""
        response = client.put("/api/projects/1/settings", data="", content_type="application/json")
        assert response.status_code == 400

    def test_missing_inference_paused(self, client, mock_db):
        """Test error when inference_paused field is missing."""
        response = client.put("/api/projects/1/settings", json={"reason": "test"})
        assert response.status_code == 400

    def test_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.put("/api/projects/999/settings", json={"inference_paused": True})
        assert response.status_code == 404

    def test_pause_sets_timestamp(self, client, mock_db, mock_project):
        """Test pausing inference sets timestamp."""
        mock_db.session.get.return_value = mock_project

        response = client.put("/api/projects/1/settings", json={
            "inference_paused": True,
            "inference_paused_reason": "Testing pause",
        })

        assert response.status_code == 200
        assert mock_project.inference_paused is True
        assert mock_project.inference_paused_at is not None
        assert mock_project.inference_paused_reason == "Testing pause"

    def test_resume_clears_timestamp_and_reason(self, client, mock_db, mock_project):
        """Test resuming inference clears timestamp and reason."""
        mock_project.inference_paused = True
        mock_project.inference_paused_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_project.inference_paused_reason = "Was paused"

        mock_db.session.get.return_value = mock_project

        response = client.put("/api/projects/1/settings", json={"inference_paused": False})

        assert response.status_code == 200
        assert mock_project.inference_paused is False
        assert mock_project.inference_paused_at is None
        assert mock_project.inference_paused_reason is None


class TestDetectMetadata:
    """Tests for POST /api/projects/<id>/detect-metadata."""

    def test_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.post("/api/projects/999/detect-metadata")
        assert response.status_code == 404

    def test_detect_github_repo_persists(self, client, app, mock_db, mock_project):
        """Test detecting github_repo from git remote and persisting it."""
        mock_project.github_repo = None
        mock_project.description = "Already set"
        mock_db.session.get.return_value = mock_project

        mock_git_metadata = MagicMock()
        mock_git_info = MagicMock()
        mock_git_info.repo_url = "git@github.com:octocat/hello-world.git"
        mock_git_metadata.get_git_info.return_value = mock_git_info

        app.extensions["git_metadata"] = mock_git_metadata

        response = client.post("/api/projects/1/detect-metadata")
        assert response.status_code == 200
        data = response.get_json()
        assert data["github_repo"] == "octocat/hello-world"
        assert data["description"] is None  # Already set, not detected

        # Verify persisted to model
        assert mock_project.github_repo == "octocat/hello-world"
        mock_db.session.commit.assert_called()

    def test_detect_description_persists(self, client, app, mock_db, mock_project):
        """Test detecting description from CLAUDE.md via LLM and persisting it."""
        mock_project.github_repo = "already/set"
        mock_project.description = None
        mock_db.session.get.return_value = mock_project

        mock_inference = MagicMock()
        mock_inference.is_available = True
        mock_inference_result = MagicMock()
        mock_inference_result.text = "A Flask dashboard for tracking sessions."
        mock_inference.infer.return_value = mock_inference_result

        app.extensions["inference_service"] = mock_inference
        app.extensions["git_metadata"] = MagicMock()

        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", MagicMock(
                 return_value=MagicMock(
                     __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="# My Project\nSome content"))),
                     __exit__=MagicMock(return_value=False)
                 )
             )):
            response = client.post("/api/projects/1/detect-metadata")
            assert response.status_code == 200
            data = response.get_json()
            assert data["github_repo"] is None  # Already set, not detected
            assert data["description"] is not None

            # Verify persisted to model
            assert mock_project.description is not None
            mock_db.session.commit.assert_called()

    def test_detect_broadcasts_project_changed(self, client, app, mock_db, mock_project):
        """Test that detection broadcasts project_changed event when values detected."""
        mock_project.github_repo = None
        mock_project.description = "Already set"
        mock_db.session.get.return_value = mock_project

        mock_git_metadata = MagicMock()
        mock_git_info = MagicMock()
        mock_git_info.repo_url = "https://github.com/org/repo.git"
        mock_git_metadata.get_git_info.return_value = mock_git_info
        app.extensions["git_metadata"] = mock_git_metadata

        with patch("src.claude_headspace.routes.projects._broadcast_project_event") as mock_broadcast:
            response = client.post("/api/projects/1/detect-metadata")
            assert response.status_code == 200
            mock_broadcast.assert_called_once_with("project_changed", {
                "action": "updated",
                "project_id": 1,
            })

    def test_both_already_set_returns_nulls(self, client, app, mock_db, mock_project):
        """Test that when both fields are already set, both return null and no commit."""
        mock_project.github_repo = "owner/repo"
        mock_project.description = "Already described"
        mock_db.session.get.return_value = mock_project

        response = client.post("/api/projects/1/detect-metadata")
        assert response.status_code == 200
        data = response.get_json()
        assert data["github_repo"] is None
        assert data["description"] is None

        # No commit when nothing detected
        mock_db.session.commit.assert_not_called()

    def test_git_failure_non_fatal(self, client, app, mock_db, mock_project):
        """Test that git failure is non-fatal and doesn't affect other detection."""
        mock_project.github_repo = None
        mock_project.description = "Already set"
        mock_db.session.get.return_value = mock_project

        mock_git_metadata = MagicMock()
        mock_git_metadata.get_git_info.side_effect = Exception("Git not found")
        app.extensions["git_metadata"] = mock_git_metadata

        response = client.post("/api/projects/1/detect-metadata")
        assert response.status_code == 200
        data = response.get_json()
        assert data["github_repo"] is None

    def test_inference_unavailable_still_returns_github(self, client, app, mock_db, mock_project):
        """Test that when inference is unavailable, github_repo is still detected and persisted."""
        mock_project.github_repo = None
        mock_project.description = None
        mock_db.session.get.return_value = mock_project

        mock_git_metadata = MagicMock()
        mock_git_info = MagicMock()
        mock_git_info.repo_url = "https://github.com/org/project.git"
        mock_git_metadata.get_git_info.return_value = mock_git_info
        app.extensions["git_metadata"] = mock_git_metadata

        mock_inference = MagicMock()
        mock_inference.is_available = False
        app.extensions["inference_service"] = mock_inference

        response = client.post("/api/projects/1/detect-metadata")
        assert response.status_code == 200
        data = response.get_json()
        assert data["github_repo"] == "org/project"
        assert data["description"] is None

        # github_repo persisted even without inference
        assert mock_project.github_repo == "org/project"
        mock_db.session.commit.assert_called()


class TestSSEBroadcasting:
    """Tests for SSE event broadcasting on project changes."""

    def test_create_broadcasts_event(self, client, mock_db):
        """Test that creating a project broadcasts project_changed event."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = None

            mock_project = MagicMock()
            mock_project.id = 1
            mock_project.name = "test"
            mock_project.path = "/test"
            mock_project.github_repo = None
            mock_project.description = None
            mock_project.inference_paused = False
            mock_project.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            MockProject.return_value = mock_project

            with patch("src.claude_headspace.routes.projects._broadcast_project_event") as mock_broadcast:
                response = client.post("/api/projects", json={
                    "name": "test",
                    "path": "/test",
                })

                assert response.status_code == 201
                mock_broadcast.assert_called_once_with("project_changed", {
                    "action": "created",
                    "project_id": 1,
                })

    def test_delete_broadcasts_event(self, client, mock_db, mock_project):
        """Test that deleting a project broadcasts project_changed event."""
        mock_db.session.get.return_value = mock_project

        with patch("src.claude_headspace.routes.projects._broadcast_project_event") as mock_broadcast:
            response = client.delete("/api/projects/1")

            assert response.status_code == 200
            mock_broadcast.assert_called_once_with("project_changed", {
                "action": "deleted",
                "project_id": 1,
            })

    def test_settings_change_broadcasts_event(self, client, mock_db, mock_project):
        """Test that settings change broadcasts project_settings_changed event."""
        mock_db.session.get.return_value = mock_project

        with patch("src.claude_headspace.routes.projects._broadcast_project_event") as mock_broadcast:
            response = client.put("/api/projects/1/settings", json={"inference_paused": True})

            assert response.status_code == 200
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][0] == "project_settings_changed"
            assert call_args[0][1]["project_id"] == 1
