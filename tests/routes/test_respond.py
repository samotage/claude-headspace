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
            "sequential_delay_ms": 150,
            "select_other_delay_ms": 500,
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

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_commit_failure_does_not_set_respond_pending(
        self, mock_bridge, client, mock_db, mock_agent
    ):
        """Commit failure should NOT set respond-pending flag (flag is post-commit)."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)
        mock_db.session.commit.side_effect = Exception("DB error")

        with patch("src.claude_headspace.services.hook_agent_state.get_agent_hook_state") as mock_get_state:
            response = client.post("/api/respond/1", json={"text": "hello"})

            assert response.status_code == 500
            # respond-pending should NOT be set on commit failure
            mock_get_state().set_respond_pending.assert_not_called()


class TestSelectMode:
    """Tests for POST /api/respond/<agent_id> with mode=select."""

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_select_option_0_sends_enter_only(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Select index 0 sends just Enter (already highlighted)."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=30)

        response = client.post(
            "/api/respond/1",
            json={"mode": "select", "option_index": 0},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["mode"] == "select"

        mock_bridge.send_keys.assert_called_once_with(
            "%5", "Enter",
            timeout=5, sequential_delay_ms=150,
        )

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_select_option_2_sends_down_down_enter(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Select index 2 sends Down, Down, Enter."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=80)

        response = client.post(
            "/api/respond/1",
            json={"mode": "select", "option_index": 2},
        )

        assert response.status_code == 200
        mock_bridge.send_keys.assert_called_once_with(
            "%5", "Down", "Down", "Enter",
            timeout=5, sequential_delay_ms=150,
        )

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_select_creates_turn_with_marker_text(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Select mode records a descriptive marker as turn text."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=30)

        client.post("/api/respond/1", json={"mode": "select", "option_index": 1})

        mock_db.session.add.assert_called_once()
        turn = mock_db.session.add.call_args[0][0]
        assert turn.text == "[selected option 1]"

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_select_with_option_label_uses_label(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Select mode uses option_label as turn text when provided."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=30)

        client.post("/api/respond/1", json={
            "mode": "select", "option_index": 0, "option_label": "Yes"
        })

        mock_db.session.add.assert_called_once()
        turn = mock_db.session.add.call_args[0][0]
        assert turn.text == "Yes"

    def test_select_invalid_index_negative(self, client, mock_db, mock_agent):
        """Negative option_index returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "select", "option_index": -1},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_option_index"

    def test_select_missing_index(self, client, mock_db, mock_agent):
        """Missing option_index returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "select"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_option_index"

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_select_tmux_failure(self, mock_bridge, client, mock_db, mock_agent):
        """tmux failure in select mode returns error."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
            latency_ms=5,
        )

        response = client.post(
            "/api/respond/1",
            json={"mode": "select", "option_index": 0},
        )

        assert response.status_code == 503


class TestOtherMode:
    """Tests for POST /api/respond/<agent_id> with mode=other."""

    @patch("src.claude_headspace.routes.respond.time")
    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_other_navigates_then_types(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, mock_time, client, mock_db, mock_agent, mock_task_awaiting
    ):
        """Other mode navigates to Other option then types text."""
        mock_db.session.get.return_value = mock_agent
        mock_time.time.side_effect = [0, 0.05, 0.1]  # start_time, respond_pending, final latency
        mock_time.sleep = MagicMock()  # don't actually sleep

        # Set up task with 2 structured options
        from src.claude_headspace.models.turn import TurnActor, TurnIntent
        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.tool_input = {
            "questions": [{
                "question": "Which?",
                "options": [
                    {"label": "A", "description": "Option A"},
                    {"label": "B", "description": "Option B"},
                ],
            }]
        }
        mock_task_awaiting.turns = [mock_turn]

        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=50)
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=30)

        response = client.post(
            "/api/respond/1",
            json={"mode": "other", "text": "custom answer"},
        )

        assert response.status_code == 200
        # Navigate: Down × 2 (num_options) + Enter
        mock_bridge.send_keys.assert_called_once_with(
            "%5", "Down", "Down", "Enter",
            timeout=5, sequential_delay_ms=150,
        )
        # Wait, then type text
        mock_time.sleep.assert_called_with(0.5)  # select_other_delay_ms=500
        mock_bridge.send_text.assert_called_once_with(
            pane_id="%5",
            text="custom answer",
            timeout=5,
            text_enter_delay_ms=100,
        )

    def test_other_missing_text(self, client, mock_db, mock_agent):
        """Other mode with no text returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "other", "text": ""},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "missing_text"


class TestMultiSelectMode:
    """Tests for POST /api/respond/<agent_id> with mode=multi_select."""

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_two_single_select_answers(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Two single-select answers produce correct key sequence."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=80)

        response = client.post(
            "/api/respond/1",
            json={
                "mode": "multi_select",
                "answers": [
                    {"option_index": 1},
                    {"option_index": 0},
                ],
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["mode"] == "multi_select"

        # Q1: Down, Enter; Q2: Enter; Submit: Enter
        mock_bridge.send_keys.assert_called_once_with(
            "%5", "Down", "Enter", "Enter", "Enter",
            timeout=5, sequential_delay_ms=150,
        )

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_mixed_single_and_multi_select(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Mixed single + multi-select answers produce correct key sequence."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=80)

        response = client.post(
            "/api/respond/1",
            json={
                "mode": "multi_select",
                "answers": [
                    {"option_index": 2},
                    {"option_indices": [0, 2]},
                ],
            },
        )

        assert response.status_code == 200
        # Q1: Down, Down, Enter; Q2: Space (idx 0), Down, Down, Space (idx 2), Enter; Submit: Enter
        mock_bridge.send_keys.assert_called_once_with(
            "%5", "Down", "Down", "Enter", "Space", "Down", "Down", "Space", "Enter", "Enter",
            timeout=5, sequential_delay_ms=150,
        )

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_option_index_0_no_down_keys(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Option index 0 produces no Down keys."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=30)

        response = client.post(
            "/api/respond/1",
            json={
                "mode": "multi_select",
                "answers": [{"option_index": 0}],
            },
        )

        assert response.status_code == 200
        # Q1: Enter; Submit: Enter
        mock_bridge.send_keys.assert_called_once_with(
            "%5", "Enter", "Enter",
            timeout=5, sequential_delay_ms=150,
        )

    def test_empty_answers_returns_400(self, client, mock_db, mock_agent):
        """Empty answers array returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "multi_select", "answers": []},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_answers"

    def test_missing_answers_returns_400(self, client, mock_db, mock_agent):
        """Missing answers key returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "multi_select"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_answers"

    def test_invalid_answer_shape_returns_400(self, client, mock_db, mock_agent):
        """Answer without option_index or option_indices returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "multi_select", "answers": [{"bad": "shape"}]},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_answers"

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_creates_turn_with_descriptive_text(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Multi-select creates a turn with descriptive summary text."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(success=True, latency_ms=30)

        client.post(
            "/api/respond/1",
            json={
                "mode": "multi_select",
                "answers": [
                    {"option_index": 1},
                    {"option_indices": [0, 2]},
                ],
            },
        )

        mock_db.session.add.assert_called_once()
        turn = mock_db.session.add.call_args[0][0]
        assert "multi-select" in turn.text
        assert "Q1: option 1" in turn.text
        assert "Q2: options [0, 2]" in turn.text

    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_tmux_failure(self, mock_bridge, client, mock_db, mock_agent):
        """tmux failure in multi_select mode returns error."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_keys.return_value = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
            latency_ms=5,
        )

        response = client.post(
            "/api/respond/1",
            json={
                "mode": "multi_select",
                "answers": [{"option_index": 0}],
            },
        )

        assert response.status_code == 503


class TestBuildMultiSelectKeys:
    """Unit tests for _build_multi_select_keys helper."""

    def test_single_question_index_0(self):
        """Single question, option 0: just Enter + Submit Enter."""
        from src.claude_headspace.routes.respond import _build_multi_select_keys
        keys = _build_multi_select_keys([{"option_index": 0}])
        assert keys == ["Enter", "Enter"]

    def test_single_question_index_3(self):
        """Single question, option 3: Down×3 + Enter + Submit Enter."""
        from src.claude_headspace.routes.respond import _build_multi_select_keys
        keys = _build_multi_select_keys([{"option_index": 3}])
        assert keys == ["Down", "Down", "Down", "Enter", "Enter"]

    def test_two_single_selects(self):
        """Two single-select: Down+Enter each, then Submit Enter."""
        from src.claude_headspace.routes.respond import _build_multi_select_keys
        keys = _build_multi_select_keys([
            {"option_index": 1},
            {"option_index": 0},
        ])
        assert keys == ["Down", "Enter", "Enter", "Enter"]

    def test_multi_select_indices(self):
        """Multi-select with option_indices: Space toggles."""
        from src.claude_headspace.routes.respond import _build_multi_select_keys
        keys = _build_multi_select_keys([{"option_indices": [0, 2]}])
        # idx 0: Space, then Down×2 to idx 2: Space, Enter, Submit Enter
        assert keys == ["Space", "Down", "Down", "Space", "Enter", "Enter"]

    def test_mixed_single_and_multi(self):
        """Mixed single + multi-select answers."""
        from src.claude_headspace.routes.respond import _build_multi_select_keys
        keys = _build_multi_select_keys([
            {"option_index": 2},
            {"option_indices": [0, 2]},
        ])
        expected = [
            "Down", "Down", "Enter",         # Q1: select option 2
            "Space", "Down", "Down", "Space", "Enter",  # Q2: toggle 0 and 2
            "Enter",                           # Submit
        ]
        assert keys == expected

    def test_multi_select_unsorted_indices_get_sorted(self):
        """option_indices are sorted before processing."""
        from src.claude_headspace.routes.respond import _build_multi_select_keys
        keys = _build_multi_select_keys([{"option_indices": [3, 1]}])
        # Sorted: [1, 3] -> Down, Space (idx 1), Down×2, Space (idx 3), Enter, Submit Enter
        assert keys == ["Down", "Space", "Down", "Down", "Space", "Enter", "Enter"]


class TestInvalidMode:
    """Tests for POST /api/respond/<agent_id> with invalid mode."""

    def test_invalid_mode(self, client, mock_db, mock_agent):
        """Unknown mode returns 400."""
        mock_db.session.get.return_value = mock_agent

        response = client.post(
            "/api/respond/1",
            json={"mode": "invalid", "text": "hello"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_mode"


class TestLegacyTextMode:
    """Verify legacy mode (no explicit mode field) still works."""

    @patch("src.claude_headspace.routes.respond.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.respond._broadcast_state_change")
    @patch("src.claude_headspace.routes.respond.tmux_bridge")
    def test_legacy_text_without_mode(
        self, mock_bridge, mock_bcast_state, mock_bcast_card, client, mock_db, mock_agent
    ):
        """Request without mode field defaults to text mode."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post(
            "/api/respond/1",
            json={"text": "hello"},
        )

        assert response.status_code == 200
        mock_bridge.send_text.assert_called_once()


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
