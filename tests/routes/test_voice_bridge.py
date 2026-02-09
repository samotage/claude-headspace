"""Tests for the voice bridge API routes (tasks 3.4-3.8, 3.9-3.10)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.models.task import TaskState
from src.claude_headspace.models.turn import TurnActor, TurnIntent
from src.claude_headspace.routes.voice_bridge import voice_bridge_bp
from src.claude_headspace.services.tmux_bridge import SendResult


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a test Flask application with voice bridge blueprint."""
    app = Flask(__name__)
    app.register_blueprint(voice_bridge_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "dashboard": {"active_timeout_minutes": 5},
        "tmux_bridge": {
            "subprocess_timeout": 5,
            "text_enter_delay_ms": 100,
        },
    }
    # Voice auth and formatter extensions
    app.extensions = {
        "voice_auth": None,
        "voice_formatter": None,
    }
    return app


@pytest.fixture
def app_with_auth():
    """Create app with voice_auth enabled."""
    app = Flask(__name__)
    app.register_blueprint(voice_bridge_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "dashboard": {"active_timeout_minutes": 5},
        "tmux_bridge": {
            "subprocess_timeout": 5,
            "text_enter_delay_ms": 100,
        },
    }
    mock_auth = MagicMock()
    mock_auth.authenticate.return_value = None  # Allow by default
    mock_formatter = MagicMock()
    # Make formatter return JSON-serializable dicts
    mock_formatter.format_sessions.return_value = {"status_line": "ok", "results": [], "next_action": "none"}
    mock_formatter.format_command_result.return_value = {"status_line": "ok", "results": [], "next_action": "none"}
    mock_formatter.format_question.return_value = {"status_line": "ok", "results": [], "next_action": "none"}
    mock_formatter.format_output.return_value = {"status_line": "ok", "results": [], "next_action": "none"}
    mock_formatter.format_error.return_value = {"status_line": "error", "results": [], "next_action": "fix"}
    app.extensions = {
        "voice_auth": mock_auth,
        "voice_formatter": mock_formatter,
    }
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def client_with_auth(app_with_auth):
    return app_with_auth.test_client()


@pytest.fixture
def mock_db():
    with patch("src.claude_headspace.routes.voice_bridge.db") as mock:
        mock.session = MagicMock()
        yield mock


@pytest.fixture
def mock_project():
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    return project


@pytest.fixture
def mock_agent(mock_project):
    """Agent with AWAITING_INPUT task."""
    agent = MagicMock()
    agent.id = 1
    agent.name = "agent-1"
    agent.project = mock_project
    agent.tmux_pane_id = "%5"
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    task = MagicMock()
    task.id = 10
    task.state = TaskState.AWAITING_INPUT
    task.instruction = "Fix the bug"
    task.completion_summary = None
    task.full_command = None
    task.full_output = None
    task.started_at = datetime.now(timezone.utc)

    # Question turn
    q_turn = MagicMock()
    q_turn.id = 100
    q_turn.actor = TurnActor.AGENT
    q_turn.intent = TurnIntent.QUESTION
    q_turn.text = "Which approach should we use?"
    q_turn.question_text = "Which approach should we use?"
    q_turn.question_options = [
        {"label": "A", "description": "Option A"},
        {"label": "B", "description": "Option B"},
    ]
    q_turn.question_source_type = "ask_user_question"
    q_turn.tool_input = None
    q_turn.summary = None

    task.turns = [q_turn]
    agent.get_current_task.return_value = task
    return agent


@pytest.fixture
def mock_agent_processing(mock_project):
    """Agent with PROCESSING task."""
    agent = MagicMock()
    agent.id = 2
    agent.name = "agent-2"
    agent.project = mock_project
    agent.tmux_pane_id = "%6"
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    task = MagicMock()
    task.id = 20
    task.state = TaskState.PROCESSING
    task.turns = []
    agent.get_current_task.return_value = task
    return agent


@pytest.fixture
def mock_agent_no_pane(mock_project):
    """Agent with AWAITING_INPUT but no tmux pane."""
    agent = MagicMock()
    agent.id = 3
    agent.name = "agent-3"
    agent.project = mock_project
    agent.tmux_pane_id = None
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    task = MagicMock()
    task.id = 30
    task.state = TaskState.AWAITING_INPUT
    task.turns = []
    agent.get_current_task.return_value = task
    return agent


@pytest.fixture
def mock_agent_complete(mock_project):
    """Agent with COMPLETE task (idle, ready for new command)."""
    agent = MagicMock()
    agent.id = 4
    agent.name = "agent-4"
    agent.project = mock_project
    agent.tmux_pane_id = "%7"
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    task = MagicMock()
    task.id = 40
    task.state = TaskState.COMPLETE
    task.turns = []
    agent.get_current_task.return_value = task
    return agent


# ──────────────────────────────────────────────────────────────
# Authentication tests (task 3.8)
# ──────────────────────────────────────────────────────────────

class TestVoiceAuth:
    """Test authentication middleware on voice bridge routes."""

    def test_auth_called_on_remote_request(self, client_with_auth, app_with_auth, mock_db):
        """Auth middleware is invoked on non-LAN requests."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        # Simulate a public (non-LAN) request
        with app_with_auth.test_request_context("/api/voice/sessions", environ_base={"REMOTE_ADDR": "8.8.8.8"}):
            from src.claude_headspace.routes.voice_bridge import voice_auth_check
            voice_auth_check()
            app_with_auth.extensions["voice_auth"].authenticate.assert_called()

    def test_auth_bypassed_on_localhost(self, client_with_auth, app_with_auth, mock_db):
        """Auth middleware is skipped for localhost requests."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        client_with_auth.get("/api/voice/sessions")
        # Test client defaults to 127.0.0.1 — auth should NOT be called
        app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_auth_bypassed_on_lan_192_168(self, client_with_auth, app_with_auth, mock_db):
        """Auth middleware is skipped for 192.168.x.x LAN requests."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        with app_with_auth.test_request_context("/api/voice/sessions", environ_base={"REMOTE_ADDR": "192.168.1.100"}):
            from src.claude_headspace.routes.voice_bridge import voice_auth_check
            voice_auth_check()
            app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_auth_bypassed_on_lan_10(self, client_with_auth, app_with_auth, mock_db):
        """Auth middleware is skipped for 10.x.x.x LAN requests."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        with app_with_auth.test_request_context("/api/voice/sessions", environ_base={"REMOTE_ADDR": "10.0.0.5"}):
            from src.claude_headspace.routes.voice_bridge import voice_auth_check
            voice_auth_check()
            app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_auth_bypassed_on_lan_172(self, client_with_auth, app_with_auth, mock_db):
        """Auth middleware is skipped for 172.16-31.x.x LAN requests."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        with app_with_auth.test_request_context("/api/voice/sessions", environ_base={"REMOTE_ADDR": "172.20.0.1"}):
            from src.claude_headspace.routes.voice_bridge import voice_auth_check
            voice_auth_check()
            app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_auth_not_bypassed_on_172_outside_range(self, client_with_auth, app_with_auth, mock_db):
        """Auth middleware is NOT skipped for 172.x.x.x outside 16-31 range."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        with app_with_auth.test_request_context("/api/voice/sessions", environ_base={"REMOTE_ADDR": "172.32.0.1"}):
            from src.claude_headspace.routes.voice_bridge import voice_auth_check
            voice_auth_check()
            app_with_auth.extensions["voice_auth"].authenticate.assert_called()

    def test_auth_rejection_returns_error(self, app_with_auth, mock_db):
        """When auth rejects, the endpoint is not reached."""
        from flask import jsonify as flask_jsonify
        with app_with_auth.app_context():
            reject_response = flask_jsonify({"error": "invalid_token", "voice": {"status_line": "Invalid.", "results": [], "next_action": "Fix token."}})
        app_with_auth.extensions["voice_auth"].authenticate.return_value = (reject_response, 401)
        # Use a public (non-LAN) address to trigger auth
        with app_with_auth.test_client() as client:
            response = client.get("/api/voice/sessions", environ_base={"REMOTE_ADDR": "8.8.8.8"})
        assert response.status_code == 401

    def test_no_auth_service_allows_request(self, client, mock_db):
        """When voice_auth is None, requests are allowed."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/voice/sessions")
        assert response.status_code == 200


# ──────────────────────────────────────────────────────────────
# Session listing tests (task 3.5)
# ──────────────────────────────────────────────────────────────

class TestListSessions:
    """Tests for GET /api/voice/sessions."""

    def test_empty_agents(self, client, mock_db):
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/voice/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert "voice" in data
        assert data["agents"] == []

    def test_active_agents_returned(self, client, mock_db, mock_agent):
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]
        response = client.get("/api/voice/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["agent_id"] == 1
        assert data["agents"][0]["name"] == "agent-1"
        assert data["agents"][0]["project"] == "test-project"
        assert data["agents"][0]["awaiting_input"] is True

    def test_latency_included(self, client, mock_db):
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/voice/sessions")
        data = response.get_json()
        assert "latency_ms" in data

    def test_verbosity_param_passed(self, client_with_auth, app_with_auth, mock_db, mock_agent):
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]
        client_with_auth.get("/api/voice/sessions?verbosity=detailed")
        app_with_auth.extensions["voice_formatter"].format_sessions.assert_called_once()
        call_args = app_with_auth.extensions["voice_formatter"].format_sessions.call_args
        assert call_args[1]["verbosity"] == "detailed"

    def test_settings_includes_auto_target(self, client, mock_db):
        """Sessions response includes auto_target setting."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/voice/sessions")
        data = response.get_json()
        assert "settings" in data
        assert data["settings"]["auto_target"] is False

    def test_stale_agent_excluded(self, client, mock_db, mock_project):
        """Agent with last_seen_at older than timeout is excluded."""
        stale_agent = MagicMock()
        stale_agent.id = 99
        stale_agent.name = "stale"
        stale_agent.project = mock_project
        stale_agent.ended_at = None
        stale_agent.last_seen_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        stale_agent.get_current_task.return_value = None

        mock_db.session.query.return_value.filter.return_value.all.return_value = [stale_agent]
        response = client.get("/api/voice/sessions")
        data = response.get_json()
        assert len(data["agents"]) == 0


# ──────────────────────────────────────────────────────────────
# Voice command tests (task 3.4)
# ──────────────────────────────────────────────────────────────

class TestVoiceCommand:
    """Tests for POST /api/voice/command."""

    def test_missing_text(self, client, mock_db):
        response = client.post("/api/voice/command", json={"text": ""})
        assert response.status_code == 400

    def test_no_json_body(self, client, mock_db):
        response = client.post("/api/voice/command", json={})
        assert response.status_code == 400

    def test_agent_not_found(self, client, mock_db):
        mock_db.session.get.return_value = None
        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 999})
        assert response.status_code == 404

    def test_agent_not_awaiting(self, client, mock_db, mock_agent_processing):
        mock_db.session.get.return_value = mock_agent_processing
        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 2})
        assert response.status_code == 409
        data = response.get_json()
        assert "processing" in data.get("error", "") or "processing" in str(data.get("voice", {}).get("status_line", "")).lower()

    def test_no_pane_id(self, client, mock_db, mock_agent_no_pane):
        mock_db.session.get.return_value = mock_agent_no_pane
        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 3})
        assert response.status_code == 503

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_successful_command(self, mock_bridge, mock_bcast, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "option 1", "agent_id": 1})
        assert response.status_code == 200
        data = response.get_json()
        assert data["agent_id"] == 1
        assert data["new_state"] == "processing"
        assert "latency_ms" in data

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_creates_answer_turn(self, mock_bridge, mock_bcast, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        client.post("/api/voice/command", json={"text": "yes", "agent_id": 1})

        mock_db.session.add.assert_called_once()
        turn = mock_db.session.add.call_args[0][0]
        assert turn.actor == TurnActor.USER
        assert turn.intent == TurnIntent.ANSWER
        assert turn.text == "yes"

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_links_answered_by_turn_id(self, mock_bridge, mock_bcast, client, mock_db, mock_agent):
        """Answer turn should link to the most recent QUESTION turn (task 3.10)."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        client.post("/api/voice/command", json={"text": "yes", "agent_id": 1})

        turn = mock_db.session.add.call_args[0][0]
        assert turn.answered_by_turn_id == 100  # question turn id

    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_tmux_send_failure(self, mock_bridge, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(
            success=False,
            error_message="Pane not found",
            latency_ms=5,
        )
        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 1})
        assert response.status_code == 502
        data = response.get_json()
        assert data["error"] == "send_failed"

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_db_error_rollback(self, mock_bridge, mock_bcast, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)
        mock_db.session.commit.side_effect = Exception("DB error")

        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 1})
        assert response.status_code == 500
        mock_db.session.rollback.assert_called_once()


class TestVoiceCommandToIdle:
    """Tests for sending commands to idle/complete agents.

    Idle/complete agents receive commands via tmux only — the hook receiver
    handles task/turn creation when Claude Code's hooks fire.
    """

    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_to_complete_agent(self, mock_bridge, client, mock_db, mock_agent_complete):
        """Sending a command to a COMPLETE agent succeeds."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "fix the bug", "agent_id": 4})
        assert response.status_code == 200
        data = response.get_json()
        assert data["agent_id"] == 4
        assert data["new_state"] == "commanded"

    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_to_idle_agent_no_task(self, mock_bridge, client, mock_db, mock_project):
        """Sending a command to an agent with no current task succeeds."""
        agent = MagicMock()
        agent.id = 10
        agent.name = "agent-10"
        agent.project = mock_project
        agent.tmux_pane_id = "%10"
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.get_current_task.return_value = None

        mock_db.session.get.return_value = agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "hello", "agent_id": 10})
        assert response.status_code == 200
        data = response.get_json()
        assert data["new_state"] == "commanded"

    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_idle_command_does_not_create_task(self, mock_bridge, client, mock_db, mock_agent_complete):
        """Idle path delegates task creation to hook receiver — no db.session.add for Task/Turn."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        client.post("/api/voice/command", json={"text": "run tests", "agent_id": 4})

        # Should NOT have called add (no Task or Turn created in this path)
        mock_db.session.add.assert_not_called()

    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_idle_command_does_not_set_respond_pending(self, mock_bridge, client, mock_db, mock_agent_complete):
        """Idle path should NOT set respond-pending flag (hook receiver needs to process the prompt)."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.hook_receiver._respond_pending_for_agent", {}) as pending:
            client.post("/api/voice/command", json={"text": "run tests", "agent_id": 4})
            assert 4 not in pending

    def test_command_to_processing_rejected(self, client, mock_db, mock_agent_processing):
        """Sending a command to a PROCESSING agent is rejected."""
        mock_db.session.get.return_value = mock_agent_processing
        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 2})
        assert response.status_code == 409


class TestAutoTarget:
    """Tests for auto-targeting when agent_id is not specified."""

    @pytest.fixture(autouse=True)
    def _enable_auto_target(self, app):
        """Enable auto_target in config for these tests."""
        app.config["APP_CONFIG"]["voice_bridge"] = {"auto_target": True}

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_auto_target_single_awaiting(self, mock_bridge, mock_bcast, client, mock_db, mock_agent):
        """Auto-target the single awaiting agent."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "yes"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["agent_id"] == 1

    def test_auto_target_no_awaiting(self, client, mock_db, mock_agent_processing):
        """No agents awaiting input returns 409."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent_processing]
        response = client.post("/api/voice/command", json={"text": "yes"})
        assert response.status_code == 409

    def test_auto_target_multiple_awaiting(self, client, mock_db, mock_agent, mock_agent_no_pane):
        """Multiple awaiting agents returns 409 with agent names."""
        # Both agents are awaiting input
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent, mock_agent_no_pane]
        response = client.post("/api/voice/command", json={"text": "yes"})
        assert response.status_code == 409

    def test_auto_target_no_active_agents(self, client, mock_db):
        """No active agents returns 409."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.post("/api/voice/command", json={"text": "yes"})
        assert response.status_code == 409

    def test_auto_target_disabled_returns_400(self, app, client):
        """When auto_target is disabled, commands without agent_id return 400."""
        app.config["APP_CONFIG"]["voice_bridge"] = {"auto_target": False}
        response = client.post("/api/voice/command", json={"text": "yes"})
        assert response.status_code == 400
        data = response.get_json()
        assert "No agent specified" in data["error"]


# ──────────────────────────────────────────────────────────────
# Output retrieval tests (task 3.6)
# ──────────────────────────────────────────────────────────────

class TestAgentOutput:
    """Tests for GET /api/voice/agents/<agent_id>/output."""

    def test_agent_not_found(self, client, mock_db):
        mock_db.session.get.return_value = None
        response = client.get("/api/voice/agents/999/output")
        assert response.status_code == 404

    def test_output_returns_tasks(self, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = 10
        mock_task.state = TaskState.PROCESSING
        mock_task.instruction = "Fix the bug"
        mock_task.completion_summary = "Fixed it"
        mock_task.full_command = "pytest tests/"
        mock_task.full_output = "5 passed"
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_task]

        response = client.get("/api/voice/agents/1/output")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["instruction"] == "Fix the bug"
        assert data["tasks"][0]["completion_summary"] == "Fixed it"
        assert "latency_ms" in data

    def test_output_empty(self, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        response = client.get("/api/voice/agents/1/output")
        assert response.status_code == 200
        data = response.get_json()
        assert data["tasks"] == []

    def test_output_respects_limit(self, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        client.get("/api/voice/agents/1/output?limit=3")
        # Verify limit was passed to the query
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_with(3)


# ──────────────────────────────────────────────────────────────
# Question detail tests (task 3.7)
# ──────────────────────────────────────────────────────────────

class TestAgentQuestion:
    """Tests for GET /api/voice/agents/<agent_id>/question."""

    def test_agent_not_found(self, client, mock_db):
        mock_db.session.get.return_value = None
        response = client.get("/api/voice/agents/999/question")
        assert response.status_code == 404

    def test_agent_not_awaiting(self, client, mock_db, mock_agent_processing):
        mock_db.session.get.return_value = mock_agent_processing
        response = client.get("/api/voice/agents/2/question")
        assert response.status_code == 409

    def test_question_with_structured_options(self, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        response = client.get("/api/voice/agents/1/question")
        assert response.status_code == 200
        data = response.get_json()
        q = data["question"]
        assert q["question_text"] == "Which approach should we use?"
        assert q["question_source_type"] == "ask_user_question"
        assert len(q["question_options"]) == 2
        assert q["question_options"][0]["label"] == "A"

    def test_question_free_text(self, client, mock_db, mock_project):
        """Question without options (free text)."""
        agent = MagicMock()
        agent.id = 5
        agent.name = "agent-5"
        agent.project = mock_project
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None

        task = MagicMock()
        task.id = 50
        task.state = TaskState.AWAITING_INPUT

        q_turn = MagicMock()
        q_turn.id = 500
        q_turn.actor = TurnActor.AGENT
        q_turn.intent = TurnIntent.QUESTION
        q_turn.text = "What name should the API use?"
        q_turn.question_text = "What name should the API use?"
        q_turn.question_options = None
        q_turn.question_source_type = "free_text"
        q_turn.tool_input = None

        task.turns = [q_turn]
        agent.get_current_task.return_value = task
        mock_db.session.get.return_value = agent

        response = client.get("/api/voice/agents/5/question")
        assert response.status_code == 200
        data = response.get_json()
        assert data["question"]["question_source_type"] == "free_text"
        assert data["question"]["question_options"] is None

    def test_question_fallback_to_tool_input(self, client, mock_db, mock_project):
        """When question_options is None, falls back to tool_input."""
        agent = MagicMock()
        agent.id = 6
        agent.name = "agent-6"
        agent.project = mock_project
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None

        task = MagicMock()
        task.id = 60
        task.state = TaskState.AWAITING_INPUT

        q_turn = MagicMock()
        q_turn.id = 600
        q_turn.actor = TurnActor.AGENT
        q_turn.intent = TurnIntent.QUESTION
        q_turn.text = "Which DB?"
        q_turn.question_text = "Which DB?"
        q_turn.question_options = None  # Not populated
        q_turn.question_source_type = "unknown"
        q_turn.tool_input = {
            "questions": [{
                "question": "Which DB?",
                "options": [
                    {"label": "Postgres", "description": "SQL"},
                    {"label": "Mongo", "description": "NoSQL"},
                ],
            }]
        }

        task.turns = [q_turn]
        agent.get_current_task.return_value = task
        mock_db.session.get.return_value = agent

        response = client.get("/api/voice/agents/6/question")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["question"]["question_options"]) == 2
        assert data["question"]["question_options"][0]["label"] == "Postgres"
        assert data["question"]["question_source_type"] == "ask_user_question"

    def test_no_question_turn_found(self, client, mock_db, mock_project):
        """Agent awaiting but no QUESTION turn exists."""
        agent = MagicMock()
        agent.id = 7
        agent.name = "agent-7"
        agent.project = mock_project

        task = MagicMock()
        task.id = 70
        task.state = TaskState.AWAITING_INPUT
        task.turns = []  # No turns at all
        agent.get_current_task.return_value = task
        mock_db.session.get.return_value = agent

        response = client.get("/api/voice/agents/7/question")
        assert response.status_code == 404

    def test_awaiting_input_guard(self, client, mock_db, mock_project):
        """Agent not in AWAITING_INPUT returns 409 (task 3.7)."""
        agent = MagicMock()
        agent.id = 8
        agent.project = mock_project
        task = MagicMock()
        task.state = TaskState.IDLE
        agent.get_current_task.return_value = task
        mock_db.session.get.return_value = agent

        response = client.get("/api/voice/agents/8/question")
        assert response.status_code == 409


# ──────────────────────────────────────────────────────────────
# Turn model column tests (task 3.1)
# ──────────────────────────────────────────────────────────────

class TestTurnModelColumns:
    """Test that Turn model has the new voice bridge columns."""

    def test_turn_has_question_text(self):
        from src.claude_headspace.models.turn import Turn
        assert hasattr(Turn, "question_text")

    def test_turn_has_question_options(self):
        from src.claude_headspace.models.turn import Turn
        assert hasattr(Turn, "question_options")

    def test_turn_has_question_source_type(self):
        from src.claude_headspace.models.turn import Turn
        assert hasattr(Turn, "question_source_type")

    def test_turn_has_answered_by_turn_id(self):
        from src.claude_headspace.models.turn import Turn
        assert hasattr(Turn, "answered_by_turn_id")

    def test_turn_has_answered_by_relationship(self):
        from src.claude_headspace.models.turn import Turn
        assert hasattr(Turn, "answered_by")
