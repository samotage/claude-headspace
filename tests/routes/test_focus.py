"""Tests for the focus API routes."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.focus import focus_bp
from src.claude_headspace.services.iterm_focus import FocusErrorType, FocusResult


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(focus_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("src.claude_headspace.routes.focus.db") as mock:
        mock.session = MagicMock()
        yield mock


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.path = "/path/to/project"
    return project


@pytest.fixture
def mock_agent(mock_project):
    """Create a mock agent with pane ID."""
    agent = MagicMock()
    agent.id = 1
    agent.iterm_pane_id = "pty-12345"
    agent.project = mock_project
    return agent


@pytest.fixture
def mock_agent_no_pane(mock_project):
    """Create a mock agent without pane ID."""
    agent = MagicMock()
    agent.id = 2
    agent.iterm_pane_id = None
    agent.project = mock_project
    return agent


class TestFocusAgent:
    """Tests for POST /api/focus/<agent_id>."""

    def test_agent_not_found(self, client, mock_db):
        """Test 404 when agent doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.post("/api/focus/999")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert data["detail"] == "agent_not_found"
        assert "999" in data["error"]

    def test_agent_no_pane_id(self, client, mock_db, mock_agent_no_pane):
        """Test error when agent has no pane ID."""
        mock_db.session.get.return_value = mock_agent_no_pane

        response = client.post("/api/focus/2")

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert data["detail"] == "pane_not_found"
        assert "fallback_path" in data
        assert data["fallback_path"] == "/path/to/project"

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    def test_focus_success(self, mock_focus, client, mock_db, mock_agent):
        """Test successful focus operation."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=True,
            latency_ms=100,
        )

        response = client.post("/api/focus/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["pane_id"] == "pty-12345"

        mock_focus.assert_called_once_with("pty-12345")

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    def test_focus_permission_denied(self, mock_focus, client, mock_db, mock_agent):
        """Test focus with permission denied error."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=False,
            error_type=FocusErrorType.PERMISSION_DENIED,
            error_message="Permission denied",
            latency_ms=50,
        )

        response = client.post("/api/focus/1")

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data
        assert data["detail"] == "permission_denied"
        assert data["error"] == "Permission denied"
        assert data["fallback_path"] == "/path/to/project"

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    def test_focus_pane_not_found(self, mock_focus, client, mock_db, mock_agent):
        """Test focus when pane not found."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=False,
            error_type=FocusErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
            latency_ms=50,
        )

        response = client.post("/api/focus/1")

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data
        assert data["detail"] == "pane_not_found"
        assert "fallback_path" in data

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    def test_focus_iterm_not_running(self, mock_focus, client, mock_db, mock_agent):
        """Test focus when iTerm is not running."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=False,
            error_type=FocusErrorType.ITERM_NOT_RUNNING,
            error_message="iTerm2 is not running",
            latency_ms=50,
        )

        response = client.post("/api/focus/1")

        assert response.status_code == 500
        data = response.get_json()
        assert data["detail"] == "iterm_not_running"

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    def test_focus_timeout(self, mock_focus, client, mock_db, mock_agent):
        """Test focus when AppleScript times out."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=False,
            error_type=FocusErrorType.TIMEOUT,
            error_message="Operation timed out",
            latency_ms=2000,
        )

        response = client.post("/api/focus/1")

        assert response.status_code == 500
        data = response.get_json()
        assert data["detail"] == "timeout"

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    def test_focus_unknown_error(self, mock_focus, client, mock_db, mock_agent):
        """Test focus with unknown error."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=False,
            error_type=FocusErrorType.UNKNOWN,
            error_message="Something went wrong",
            latency_ms=50,
        )

        response = client.post("/api/focus/1")

        assert response.status_code == 500
        data = response.get_json()
        assert data["detail"] == "unknown"

    def test_focus_agent_without_project(self, client, mock_db):
        """Test focus when agent has no project."""
        agent = MagicMock()
        agent.id = 1
        agent.iterm_pane_id = None
        agent.project = None
        mock_db.session.get.return_value = agent

        response = client.post("/api/focus/1")

        assert response.status_code == 400
        data = response.get_json()
        # fallback_path should be None when no project
        assert data["fallback_path"] is None


class TestFallbackPath:
    """Tests for fallback path behavior."""

    def test_fallback_path_from_project(self, client, mock_db, mock_agent_no_pane):
        """Test fallback path is extracted from project."""
        mock_db.session.get.return_value = mock_agent_no_pane

        response = client.post("/api/focus/2")

        data = response.get_json()
        assert data["fallback_path"] == "/path/to/project"

    def test_fallback_path_none_when_no_project(self, client, mock_db):
        """Test fallback path is None when no project."""
        agent = MagicMock()
        agent.id = 1
        agent.iterm_pane_id = None
        agent.project = None
        mock_db.session.get.return_value = agent

        response = client.post("/api/focus/1")

        data = response.get_json()
        assert data["fallback_path"] is None

    def test_fallback_path_none_when_project_has_no_path(self, client, mock_db):
        """Test fallback path is None when project has no path."""
        project = MagicMock()
        project.path = None
        agent = MagicMock()
        agent.id = 1
        agent.iterm_pane_id = None
        agent.project = project
        mock_db.session.get.return_value = agent

        response = client.post("/api/focus/1")

        data = response.get_json()
        assert data["fallback_path"] is None


class TestFocusEventLogging:
    """Tests for focus event logging."""

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    @patch("src.claude_headspace.routes.focus.logger")
    def test_success_logged(self, mock_logger, mock_focus, client, mock_db, mock_agent):
        """Test successful focus is logged."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(success=True, latency_ms=100)

        client.post("/api/focus/1")

        # Verify logging was called
        assert mock_logger.info.called
        log_message = mock_logger.info.call_args[0][0]
        assert "focus_attempted" in log_message
        assert "agent_id=1" in log_message
        assert "outcome=success" in log_message

    @patch("src.claude_headspace.routes.focus.focus_iterm_pane")
    @patch("src.claude_headspace.routes.focus.logger")
    def test_failure_logged(self, mock_logger, mock_focus, client, mock_db, mock_agent):
        """Test failed focus is logged."""
        mock_db.session.get.return_value = mock_agent
        mock_focus.return_value = FocusResult(
            success=False,
            error_type=FocusErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
            latency_ms=50,
        )

        client.post("/api/focus/1")

        assert mock_logger.info.called
        log_message = mock_logger.info.call_args[0][0]
        assert "outcome=failure" in log_message
        assert "error_type=pane_not_found" in log_message

    @patch("src.claude_headspace.routes.focus.logger")
    def test_agent_not_found_logged(self, mock_logger, client, mock_db):
        """Test agent not found is logged."""
        mock_db.session.get.return_value = None

        client.post("/api/focus/999")

        assert mock_logger.info.called
        log_message = mock_logger.info.call_args[0][0]
        assert "agent_id=999" in log_message
        assert "error_type=agent_not_found" in log_message
