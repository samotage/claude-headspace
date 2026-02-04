"""Tests for the respond API routes."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.models.task import TaskState
from src.claude_headspace.routes.respond import respond_bp
from src.claude_headspace.services.tmux_bridge import (
    SendResult,
    TmuxBridgeErrorType,
)


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(respond_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "tmux_bridge": {
            "subprocess_timeout": 5,
            "text_enter_delay_ms": 100,
        }
    }
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("src.claude_headspace.routes.respond.db") as mock:
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
def mock_task_awaiting():
    """Create a mock task in AWAITING_INPUT state."""
    task = MagicMock()
    task.id = 10
    task.state = TaskState.AWAITING_INPUT
    return task


@pytest.fixture
def mock_task_processing():
    """Create a mock task in PROCESSING state."""
    task = MagicMock()
    task.id = 10
    task.state = TaskState.PROCESSING
    return task


@pytest.fixture
def mock_agent(mock_project, mock_task_awaiting):
    """Create a mock agent with tmux pane ID and AWAITING_INPUT task."""
    agent = MagicMock()
    agent.id = 1
    agent.tmux_pane_id = "%5"
    agent.project = mock_project
    agent.project_id = 1
    agent.get_current_task.return_value = mock_task_awaiting
    return agent


@pytest.fixture
def mock_agent_no_pane(mock_project, mock_task_awaiting):
    """Create a mock agent without tmux pane ID."""
    agent = MagicMock()
    agent.id = 2
    agent.tmux_pane_id = None
    agent.project = mock_project
    agent.get_current_task.return_value = mock_task_awaiting
    return agent


@pytest.fixture
def mock_agent_processing(mock_project, mock_task_processing):
    """Create a mock agent with PROCESSING task."""
    agent = MagicMock()
    agent.id = 3
    agent.tmux_pane_id = "%5"
    agent.project = mock_project
    agent.get_current_task.return_value = mock_task_processing
    return agent


class TestRespondToAgent:
    """Tests for POST /api/respond/<agent_id>."""

    def test_agent_not_found(self, client, mock_db):
        """Test 404 when agent doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.post(
            "/api/respond/999",
            json={"text": "hello"},
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert data["error_type"] == "agent_not_found"
        assert "999" in data["message"]

    def test_missing_text(self, client, mock_db, mock_agent):
        """Test 400 when text is missing."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert data["error_type"] == "missing_text"

    def test_empty_text(self, client, mock_db, mock_agent):
        """Test 400 when text is empty."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"text": "   "},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "missing_text"

    def test_no_pane_id(self, client, mock_db, mock_agent_no_pane):
        """Test 400 when agent has no tmux pane ID."""
        mock_db.session.get.return_value = mock_agent_no_pane

        response = client.post(
            "/api/respond/2",
            json={"text": "hello"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert data["error_type"] == "no_pane_id"

    def test_wrong_state(self, client, mock_db, mock_agent_processing):
        """Test 409 when agent is not in AWAITING_INPUT state."""
        mock_db.session.get.return_value = mock_agent_processing

        response = client.post(
            "/api/respond/3",
            json={"text": "hello"},
        )

        assert response.status_code == 409
        data = response.get_json()
        assert data["status"] == "error"
        assert data["error_type"] == "wrong_state"
        assert "processing" in data["message"].lower()

    def test_no_current_task(self, client, mock_db, mock_project):
        """Test 409 when agent has no current task."""
        agent = MagicMock()
        agent.id = 4
        agent.tmux_pane_id = "%5"
        agent.get_current_task.return_value = None
        mock_db.session.get.return_value = agent

        response = client.post(
            "/api/respond/4",
            json={"text": "hello"},
        )

        assert response.status_code == 409
        data = response.get_json()
        assert data["error_type"] == "wrong_state"
        assert "no_task" in data["message"]

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_send_success(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Test successful response send."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post(
            "/api/respond/1",
            json={"text": "1"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["new_state"].upper() == "PROCESSING"
        assert data["latency_ms"] >= 0

        mock_bridge.send_text.assert_called_once_with(
            pane_id="%5",
            text="1",
            timeout=5,
            text_enter_delay_ms=100,
        )

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_send_creates_turn(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Test that successful send creates a Turn record."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        client.post("/api/respond/1", json={"text": "yes"})

        # Verify db.session.add was called (for the Turn)
        mock_db.session.add.assert_called_once()
        turn = mock_db.session.add.call_args[0][0]
        assert turn.actor.value == "user"
        assert turn.intent.value == "answer"
        assert turn.text == "yes"

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_send_transitions_state(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent, mock_task_awaiting
    ):
        """Test that successful send transitions task to PROCESSING."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        client.post("/api/respond/1", json={"text": "1"})

        assert mock_task_awaiting.state == TaskState.PROCESSING
        mock_db.session.commit.assert_called_once()

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_send_broadcasts(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Test that successful send triggers broadcasts."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        client.post("/api/respond/1", json={"text": "hello"})

        mock_bcast_card.assert_called_once_with(mock_agent, "respond")
        mock_bcast_state.assert_called_once_with(mock_agent, "hello")

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_pane_not_found(self, mock_bridge, client, mock_db, mock_agent):
        """Test 503 when pane not found."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
            latency_ms=5,
        )

        response = client.post("/api/respond/1", json={"text": "hello"})

        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "error"
        assert data["error_type"] == "pane_not_found"

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_tmux_not_installed(self, mock_bridge, client, mock_db, mock_agent):
        """Test 503 when tmux not installed."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux not installed",
            latency_ms=5,
        )

        response = client.post("/api/respond/1", json={"text": "hello"})

        assert response.status_code == 503
        data = response.get_json()
        assert data["error_type"] == "tmux_not_installed"

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_timeout(self, mock_bridge, client, mock_db, mock_agent):
        """Test 502 when timeout."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message="Timed out",
            latency_ms=2000,
        )

        response = client.post("/api/respond/1", json={"text": "hello"})

        assert response.status_code == 502
        data = response.get_json()
        assert data["error_type"] == "timeout"

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_send_failed(self, mock_bridge, client, mock_db, mock_agent):
        """Test 502 when send fails."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.SEND_FAILED,
            error_message="Send failed",
            latency_ms=50,
        )

        response = client.post("/api/respond/1", json={"text": "hello"})

        assert response.status_code == 502
        data = response.get_json()
        assert data["error_type"] == "send_failed"

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_db_error_rollback(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Test 500 when database error occurs after successful send."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)
        mock_db.session.commit.side_effect = Exception("DB error")

        response = client.post("/api/respond/1", json={"text": "hello"})

        assert response.status_code == 500
        data = response.get_json()
        assert data["error_type"] == "internal_error"
        mock_db.session.rollback.assert_called_once()

    def test_no_json_body(self, client, mock_db, mock_agent):
        """Test 400 when request has no JSON body."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            content_type="text/plain",
            data="hello",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "missing_text"


class TestCheckAvailability:
    """Tests for GET /api/respond/<agent_id>/availability."""

    def test_agent_not_found(self, client, mock_db):
        """Test 404 when agent doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.get("/api/respond/999/availability")

        assert response.status_code == 404
        data = response.get_json()
        assert data["status"] == "error"
        assert data["error_type"] == "agent_not_found"

    @patch("src.claude_headspace.routes.respond._get_commander_availability")
    def test_available(self, mock_get_avail, client, mock_db, mock_agent):
        """Test availability returns true when commander is available."""
        mock_db.session.get.return_value = mock_agent
        mock_avail = MagicMock()
        mock_avail.check_agent.return_value = True
        mock_get_avail.return_value = mock_avail

        response = client.get("/api/respond/1/availability")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["commander_available"] is True
        mock_avail.check_agent.assert_called_once_with(1, "%5")

    @patch("src.claude_headspace.routes.respond._get_commander_availability")
    def test_unavailable(self, mock_get_avail, client, mock_db, mock_agent):
        """Test availability returns false when commander is unavailable."""
        mock_db.session.get.return_value = mock_agent
        mock_avail = MagicMock()
        mock_avail.check_agent.return_value = False
        mock_get_avail.return_value = mock_avail

        response = client.get("/api/respond/1/availability")

        assert response.status_code == 200
        data = response.get_json()
        assert data["commander_available"] is False

    @patch("src.claude_headspace.routes.respond._get_commander_availability")
    def test_no_availability_service(self, mock_get_avail, client, mock_db, mock_agent):
        """Test availability returns false when service not registered."""
        mock_db.session.get.return_value = mock_agent
        mock_get_avail.return_value = None

        response = client.get("/api/respond/1/availability")

        assert response.status_code == 200
        data = response.get_json()
        assert data["commander_available"] is False

    @patch("src.claude_headspace.routes.respond._get_commander_availability")
    def test_no_pane_id_returns_unavailable(
        self, mock_get_avail, client, mock_db, mock_agent_no_pane
    ):
        """Test availability returns false when agent has no pane ID."""
        mock_db.session.get.return_value = mock_agent_no_pane

        response = client.get("/api/respond/2/availability")

        assert response.status_code == 200
        data = response.get_json()
        assert data["commander_available"] is False
