"""Tests for the sessions API routes."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.sessions import sessions_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(sessions_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("src.claude_headspace.routes.sessions.db") as mock:
        mock.session = MagicMock()
        yield mock


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.path = "/path/to/project"
    project.current_branch = "main"
    return project


@pytest.fixture
def mock_agent(mock_project):
    """Create a mock agent."""
    agent = MagicMock()
    agent.id = 1
    agent.session_uuid = uuid.uuid4()
    agent.project_id = mock_project.id
    agent.project = mock_project
    agent.iterm_pane_id = "pane123"
    agent.started_at = datetime.now(timezone.utc)
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.state.value = "idle"
    return agent


class TestCreateSession:
    """Tests for POST /api/sessions."""

    def test_missing_request_body(self, client):
        """Test error when request body is missing."""
        response = client.post(
            "/api/sessions",
            data="",
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data is not None
        assert "Request body is required" in data["error"]

    def test_missing_required_fields(self, client):
        """Test error when required fields are missing."""
        response = client.post(
            "/api/sessions",
            json={"project_path": "/path/to/project"},
        )
        assert response.status_code == 400
        assert "session_uuid" in response.get_json()["error"]

    def test_invalid_session_uuid(self, client):
        """Test error when session_uuid is invalid."""
        response = client.post(
            "/api/sessions",
            json={
                "session_uuid": "not-a-uuid",
                "project_path": "/path/to/project",
            },
        )
        assert response.status_code == 400
        assert "Invalid session_uuid" in response.get_json()["error"]

    def test_auto_creates_unregistered_project(self, client, mock_db):
        """Test that unregistered project paths are auto-created."""
        session_uuid = str(uuid.uuid4())

        with patch("src.claude_headspace.routes.sessions.Project") as MockProject:
            with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
                # First filter_by(path=...) returns None (not registered)
                # Second filter_by(slug=...) returns None (slug available)
                MockProject.query.filter_by.return_value.first.side_effect = [None, None, None]

                mock_project = MagicMock()
                mock_project.id = 42
                mock_project.name = "unregistered-project"
                MockProject.return_value = mock_project

                mock_agent = MagicMock()
                mock_agent.id = 1
                MockAgent.return_value = mock_agent
                MockAgent.query.filter_by.return_value.first.return_value = None

                with patch("src.claude_headspace.models.project.generate_slug", return_value="unregistered-project"):
                    response = client.post(
                        "/api/sessions",
                        json={
                            "session_uuid": session_uuid,
                            "project_path": "/path/to/unregistered-project",
                            "iterm_pane_id": "pane123",
                        },
                    )

                assert response.status_code == 201
                data = response.get_json()
                assert data["status"] == "created"
                # Project was auto-created
                MockProject.assert_called_once_with(
                    name="unregistered-project",
                    slug="unregistered-project",
                    path="/path/to/unregistered-project",
                    current_branch=None,
                )

    def test_uses_existing_project(self, client, mock_db, mock_project):
        """Test creating session with existing project."""
        session_uuid = str(uuid.uuid4())

        with patch("src.claude_headspace.routes.sessions.Project") as MockProject:
            with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
                MockProject.query.filter_by.return_value.first.return_value = mock_project

                mock_agent = MagicMock()
                mock_agent.id = 1
                MockAgent.return_value = mock_agent
                MockAgent.query.filter_by.return_value.first.return_value = None

                response = client.post(
                    "/api/sessions",
                    json={
                        "session_uuid": session_uuid,
                        "project_path": "/path/to/project",
                        "current_branch": "feature-branch",
                    },
                )

                assert response.status_code == 201
                data = response.get_json()
                assert data["status"] == "created"
                assert data["project_id"] == mock_project.id

    def test_creates_session_with_tmux_pane_id(self, app, client, mock_db, mock_project):
        """Test creating session with tmux_pane_id stores it on Agent."""
        session_uuid = str(uuid.uuid4())

        mock_availability = MagicMock()
        app.extensions["commander_availability"] = mock_availability

        with patch("src.claude_headspace.routes.sessions.Project") as MockProject:
            with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
                MockProject.query.filter_by.return_value.first.return_value = mock_project

                mock_agent = MagicMock()
                mock_agent.id = 1
                MockAgent.return_value = mock_agent
                MockAgent.query.filter_by.return_value.first.return_value = None

                response = client.post(
                    "/api/sessions",
                    json={
                        "session_uuid": session_uuid,
                        "project_path": "/path/to/project",
                        "tmux_pane_id": "%5",
                    },
                )

                assert response.status_code == 201
                # Verify Agent was created with tmux_pane_id
                MockAgent.assert_called_once()
                call_kwargs = MockAgent.call_args[1]
                assert call_kwargs["tmux_pane_id"] == "%5"
                # Verify availability registration
                mock_availability.register_agent.assert_called_once_with(
                    mock_agent.id, "%5"
                )

    def test_creates_session_without_tmux_pane_id(self, client, mock_db, mock_project):
        """Test creating session without tmux_pane_id is backward compatible."""
        session_uuid = str(uuid.uuid4())

        with patch("src.claude_headspace.routes.sessions.Project") as MockProject:
            with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
                MockProject.query.filter_by.return_value.first.return_value = mock_project

                mock_agent = MagicMock()
                mock_agent.id = 1
                MockAgent.return_value = mock_agent
                MockAgent.query.filter_by.return_value.first.return_value = None

                response = client.post(
                    "/api/sessions",
                    json={
                        "session_uuid": session_uuid,
                        "project_path": "/path/to/project",
                    },
                )

                assert response.status_code == 201
                # Verify Agent was created with tmux_pane_id=None
                MockAgent.assert_called_once()
                call_kwargs = MockAgent.call_args[1]
                assert call_kwargs["tmux_pane_id"] is None

    def test_duplicate_session_uuid(self, client, mock_db, mock_agent):
        """Test error when session_uuid already exists."""
        session_uuid = str(mock_agent.session_uuid)

        with patch("src.claude_headspace.routes.sessions.Project") as MockProject:
            with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
                mock_project = MagicMock()
                mock_project.id = 1
                MockProject.query.filter_by.return_value.first.return_value = mock_project
                MockAgent.query.filter_by.return_value.first.return_value = mock_agent

                response = client.post(
                    "/api/sessions",
                    json={
                        "session_uuid": session_uuid,
                        "project_path": "/path/to/project",
                    },
                )

                assert response.status_code == 409
                assert "already exists" in response.get_json()["error"]

    def test_database_error(self, client, mock_db):
        """Test error handling on database failure."""
        session_uuid = str(uuid.uuid4())

        with patch("src.claude_headspace.routes.sessions.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.side_effect = Exception(
                "DB error"
            )

            response = client.post(
                "/api/sessions",
                json={
                    "session_uuid": session_uuid,
                    "project_path": "/path/to/project",
                },
            )

            assert response.status_code == 500
            assert "DB error" in response.get_json()["error"]


class TestDeleteSession:
    """Tests for DELETE /api/sessions/<uuid>."""

    def test_session_not_found(self, client, mock_db):
        """Test 404 when session doesn't exist."""
        session_uuid = uuid.uuid4()

        with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
            MockAgent.query.filter_by.return_value.first.return_value = None

            response = client.delete(f"/api/sessions/{session_uuid}")

            assert response.status_code == 404
            assert "not found" in response.get_json()["error"]

    def test_session_deleted_successfully(self, client, mock_db, mock_agent):
        """Test successful session deletion."""
        session_uuid = mock_agent.session_uuid

        with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
            MockAgent.query.filter_by.return_value.first.return_value = mock_agent

            response = client.delete(f"/api/sessions/{session_uuid}")

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ended"
            assert data["agent_id"] == mock_agent.id
            mock_db.session.commit.assert_called_once()

    def test_database_error_on_delete(self, client, mock_db):
        """Test error handling on database failure."""
        session_uuid = uuid.uuid4()

        with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
            MockAgent.query.filter_by.return_value.first.side_effect = Exception(
                "DB error"
            )

            response = client.delete(f"/api/sessions/{session_uuid}")

            assert response.status_code == 500


class TestGetSession:
    """Tests for GET /api/sessions/<uuid>."""

    def test_session_not_found(self, client, mock_db):
        """Test 404 when session doesn't exist."""
        session_uuid = uuid.uuid4()

        with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
            MockAgent.query.filter_by.return_value.first.return_value = None

            response = client.get(f"/api/sessions/{session_uuid}")

            assert response.status_code == 404

    def test_get_session_success(self, client, mock_db, mock_agent):
        """Test successful session retrieval."""
        session_uuid = mock_agent.session_uuid

        with patch("src.claude_headspace.routes.sessions.Agent") as MockAgent:
            MockAgent.query.filter_by.return_value.first.return_value = mock_agent

            response = client.get(f"/api/sessions/{session_uuid}")

            assert response.status_code == 200
            data = response.get_json()
            assert data["agent_id"] == mock_agent.id
            assert data["project_name"] == mock_agent.project.name
            assert data["iterm_pane_id"] == mock_agent.iterm_pane_id
