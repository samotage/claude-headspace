"""Tests for the voice bridge API routes (tasks 3.4-3.8, 3.9-3.10)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.models.command import CommandState
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
    """Agent with AWAITING_INPUT command."""
    agent = MagicMock()
    agent.id = 1
    agent.name = "agent-1"
    agent.project = mock_project
    agent.tmux_pane_id = "%5"
    agent.tmux_session = None
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    cmd = MagicMock()
    cmd.id = 10
    cmd.state = CommandState.AWAITING_INPUT
    cmd.instruction = "Fix the bug"
    cmd.completion_summary = None
    cmd.full_command = None
    cmd.full_output = None
    cmd.started_at = datetime.now(timezone.utc)

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

    cmd.turns = [q_turn]
    agent.get_current_command.return_value = cmd
    return agent


@pytest.fixture
def mock_agent_processing(mock_project):
    """Agent with PROCESSING command."""
    agent = MagicMock()
    agent.id = 2
    agent.name = "agent-2"
    agent.project = mock_project
    agent.tmux_pane_id = "%6"
    agent.tmux_session = None
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    cmd = MagicMock()
    cmd.id = 20
    cmd.state = CommandState.PROCESSING
    cmd.turns = []
    agent.get_current_command.return_value = cmd
    return agent


@pytest.fixture
def mock_agent_no_pane(mock_project):
    """Agent with AWAITING_INPUT but no tmux pane."""
    agent = MagicMock()
    agent.id = 3
    agent.name = "agent-3"
    agent.project = mock_project
    agent.tmux_pane_id = None
    agent.tmux_session = None
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    cmd = MagicMock()
    cmd.id = 30
    cmd.state = CommandState.AWAITING_INPUT
    cmd.turns = []
    agent.get_current_command.return_value = cmd
    return agent


@pytest.fixture
def mock_agent_complete(mock_project):
    """Agent with COMPLETE command (idle, ready for new command)."""
    agent = MagicMock()
    agent.id = 4
    agent.name = "agent-4"
    agent.project = mock_project
    agent.tmux_pane_id = "%7"
    agent.tmux_session = None
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    cmd = MagicMock()
    cmd.id = 40
    cmd.state = CommandState.COMPLETE
    cmd.turns = []
    agent.get_current_command.return_value = cmd
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
        stale_agent.get_current_command.return_value = None

        mock_db.session.query.return_value.filter.return_value.all.return_value = [stale_agent]
        response = client.get("/api/voice/sessions")
        data = response.get_json()
        assert len(data["agents"]) == 0

    def test_no_ended_agents_by_default(self, client, mock_db):
        """Ended agents are not included unless include_ended=true."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/voice/sessions")
        data = response.get_json()
        assert "ended_agents" not in data

    @patch("src.claude_headspace.routes.voice_bridge._agent_to_voice_dict")
    @patch("src.claude_headspace.routes.voice_bridge._get_ended_agents")
    def test_include_ended_returns_ended_agents(self, mock_get_ended, mock_to_dict, client, mock_db):
        """include_ended=true returns ended_agents in response."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []

        ended_agent = MagicMock()
        ended_agent.id = 50
        mock_get_ended.return_value = [ended_agent]

        mock_to_dict.return_value = {
            "agent_id": 50,
            "name": "ended-agent",
            "hero_chars": "ab",
            "hero_trail": "cd1234",
            "project": "test-project",
            "state": "complete",
            "state_label": "Complete",
            "awaiting_input": False,
            "command_instruction": None,
            "command_summary": None,
            "command_completion_summary": None,
            "turn_count": 0,
            "summary": None,
            "last_activity_ago": "1h ago",
            "ended": True,
            "ended_at": "2026-02-14T12:00:00+00:00",
        }

        response = client.get("/api/voice/sessions?include_ended=true")
        data = response.get_json()
        assert "ended_agents" in data
        assert len(data["ended_agents"]) == 1
        assert data["ended_agents"][0]["agent_id"] == 50
        assert data["ended_agents"][0]["ended"] is True
        assert data["ended_agents"][0]["ended_at"] is not None

    @patch("src.claude_headspace.routes.voice_bridge._get_ended_agents")
    def test_include_ended_false_omits_ended(self, mock_get_ended, client, mock_db):
        """include_ended=false does not include ended_agents."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/voice/sessions?include_ended=false")
        data = response.get_json()
        assert "ended_agents" not in data
        mock_get_ended.assert_not_called()


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

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_processing_agent_gets_queued_send_and_turn(self, mock_bridge, mock_bcast, client, mock_db, mock_agent_processing):
        """PROCESSING agent gets queued send_text (no interrupt) and a turn is created."""
        mock_db.session.get.return_value = mock_agent_processing
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc = MagicMock()
            mock_lc_cls.return_value = mock_lc
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.command = mock_agent_processing.get_current_command()
            mock_result.command.state = CommandState.PROCESSING
            mock_result.command.turns = []
            mock_result.intent = MagicMock()
            mock_result.intent.intent.value = "command"
            mock_lc.process_turn.return_value = mock_result
            mock_lc.get_pending_summarisations.return_value = []

            response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 2})
            assert response.status_code == 200
            mock_bridge.send_text.assert_called_once()
            mock_bridge.interrupt_and_send_text.assert_not_called()
            mock_lc.process_turn.assert_called_once()

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

    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_commit_failure_does_not_set_respond_pending(self, mock_bridge, client, mock_db, mock_agent):
        """Commit failure should NOT set respond-pending flag (flag is set post-commit)."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)
        mock_db.session.commit.side_effect = Exception("DB error")

        with patch("src.claude_headspace.services.hook_agent_state.get_agent_hook_state") as mock_get_state:
            response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 1})
            assert response.status_code == 500
            # respond-pending should NOT be set on commit failure
            mock_get_state().set_respond_pending.assert_not_called()

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_picker_detection_sets_has_picker(self, mock_bridge, mock_bcast, client, mock_db, mock_agent):
        """When agent has structured options (picker), response includes has_picker flag."""
        mock_db.session.get.return_value = mock_agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 1})
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_picker"] is True

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_no_picker_when_free_text_question(self, mock_bridge, mock_bcast, client, mock_db, mock_project):
        """When agent has a free-text question (no options), has_picker is not in response."""
        agent = MagicMock()
        agent.id = 11
        agent.name = "agent-11"
        agent.project = mock_project
        agent.tmux_pane_id = "%11"
        agent.tmux_session = None
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None

        cmd = MagicMock()
        cmd.id = 110
        cmd.state = CommandState.AWAITING_INPUT
        cmd.instruction = "Do something"

        q_turn = MagicMock()
        q_turn.id = 1100
        q_turn.actor = TurnActor.AGENT
        q_turn.intent = TurnIntent.QUESTION
        q_turn.text = "What should we name it?"
        q_turn.question_text = "What should we name it?"
        q_turn.question_options = None
        q_turn.question_source_type = "free_text"
        q_turn.tool_input = None

        cmd.turns = [q_turn]
        agent.get_current_command.return_value = cmd
        mock_db.session.get.return_value = agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "my-api", "agent_id": 11})
        assert response.status_code == 200
        data = response.get_json()
        assert "has_picker" not in data

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_picker_detection_via_tool_input_fallback(self, mock_bridge, mock_bcast, client, mock_db, mock_project):
        """Picker detection works via tool_input fallback when question_options is None."""
        agent = MagicMock()
        agent.id = 12
        agent.name = "agent-12"
        agent.project = mock_project
        agent.tmux_pane_id = "%12"
        agent.tmux_session = None
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None

        cmd = MagicMock()
        cmd.id = 120
        cmd.state = CommandState.AWAITING_INPUT
        cmd.instruction = "Choose DB"

        q_turn = MagicMock()
        q_turn.id = 1200
        q_turn.actor = TurnActor.AGENT
        q_turn.intent = TurnIntent.QUESTION
        q_turn.text = "Which DB?"
        q_turn.question_text = "Which DB?"
        q_turn.question_options = None
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

        cmd.turns = [q_turn]
        agent.get_current_command.return_value = cmd
        mock_db.session.get.return_value = agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        response = client.post("/api/voice/command", json={"text": "postgres", "agent_id": 12})
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_picker"] is True


class TestVoiceCommandToIdle:
    """Tests for sending commands to idle/complete agents.

    Idle/complete agents get turns created directly via CommandLifecycleManager
    and respond_pending is set to prevent duplicate turn creation by hooks.
    """

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_to_complete_agent(self, mock_bridge, mock_bcast, client, mock_db, mock_agent_complete):
        """Sending a command to a COMPLETE agent creates a turn and succeeds."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc = MagicMock()
            mock_lc_cls.return_value = mock_lc
            mock_result = MagicMock()
            mock_result.success = True
            mock_cmd = MagicMock()
            mock_cmd.state = CommandState.COMMANDED
            mock_cmd.turns = []
            mock_result.command = mock_cmd
            mock_result.intent = MagicMock()
            mock_result.intent.intent.value = "command"
            mock_lc.process_turn.return_value = mock_result
            mock_lc.get_pending_summarisations.return_value = []

            response = client.post("/api/voice/command", json={"text": "fix the bug", "agent_id": 4})
            assert response.status_code == 200
            data = response.get_json()
            assert data["agent_id"] == 4
            mock_lc.process_turn.assert_called_once()

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_to_idle_agent_no_command(self, mock_bridge, mock_bcast, client, mock_db, mock_project):
        """Sending a command to an agent with no current command creates a turn."""
        agent = MagicMock()
        agent.id = 10
        agent.name = "agent-10"
        agent.project = mock_project
        agent.project_id = 1
        agent.tmux_pane_id = "%10"
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.get_current_command.return_value = None

        mock_db.session.get.return_value = agent
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc = MagicMock()
            mock_lc_cls.return_value = mock_lc
            mock_result = MagicMock()
            mock_result.success = True
            mock_cmd = MagicMock()
            mock_cmd.state = CommandState.COMMANDED
            mock_cmd.turns = []
            mock_result.command = mock_cmd
            mock_result.intent = MagicMock()
            mock_result.intent.intent.value = "command"
            mock_lc.process_turn.return_value = mock_result
            mock_lc.get_pending_summarisations.return_value = []

            response = client.post("/api/voice/command", json={"text": "hello", "agent_id": 10})
            assert response.status_code == 200
            mock_lc.process_turn.assert_called_once()

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_idle_command_creates_turn_via_lifecycle(self, mock_bridge, mock_bcast, client, mock_db, mock_agent_complete):
        """Idle path creates turn via CommandLifecycleManager."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc = MagicMock()
            mock_lc_cls.return_value = mock_lc
            mock_result = MagicMock()
            mock_result.success = True
            mock_cmd = MagicMock()
            mock_cmd.state = CommandState.COMMANDED
            mock_cmd.turns = []
            mock_result.command = mock_cmd
            mock_result.intent = MagicMock()
            mock_result.intent.intent.value = "command"
            mock_lc.process_turn.return_value = mock_result
            mock_lc.get_pending_summarisations.return_value = []

            client.post("/api/voice/command", json={"text": "run tests", "agent_id": 4})
            mock_lc.process_turn.assert_called_once()

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_idle_command_sets_respond_pending(self, mock_bridge, mock_bcast, client, mock_db, mock_agent_complete):
        """Idle path sets respond-pending to prevent duplicate turn from hooks."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc = MagicMock()
            mock_lc_cls.return_value = mock_lc
            mock_result = MagicMock()
            mock_result.success = True
            mock_cmd = MagicMock()
            mock_cmd.state = CommandState.COMMANDED
            mock_cmd.turns = []
            mock_result.command = mock_cmd
            mock_result.intent = MagicMock()
            mock_result.intent.intent.value = "command"
            mock_lc.process_turn.return_value = mock_result
            mock_lc.get_pending_summarisations.return_value = []

            with patch("src.claude_headspace.services.hook_agent_state.get_agent_hook_state") as mock_get_state:
                client.post("/api/voice/command", json={"text": "run tests", "agent_id": 4})
                mock_get_state().set_respond_pending.assert_called_once_with(4)

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_idle_command_lifecycle_failure_falls_back(self, mock_bridge, mock_bcast, client, mock_db, mock_agent_complete):
        """If lifecycle processing fails, tmux send already succeeded — returns 200."""
        mock_db.session.get.return_value = mock_agent_complete
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc_cls.side_effect = Exception("lifecycle error")

            response = client.post("/api/voice/command", json={"text": "do something", "agent_id": 4})
            assert response.status_code == 200

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_processing_command_creates_turn(self, mock_bridge, mock_bcast, client, mock_db, mock_agent_processing):
        """PROCESSING agent gets queued send_text (no interrupt) and a turn is created."""
        mock_db.session.get.return_value = mock_agent_processing
        mock_bridge.send_text.return_value = SendResult(success=True, latency_ms=50)

        with patch("src.claude_headspace.services.command_lifecycle.CommandLifecycleManager") as mock_lc_cls:
            mock_lc = MagicMock()
            mock_lc_cls.return_value = mock_lc
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.command = mock_agent_processing.get_current_command()
            mock_result.command.state = CommandState.PROCESSING
            mock_result.command.turns = []
            mock_result.intent = MagicMock()
            mock_result.intent.intent.value = "command"
            mock_lc.process_turn.return_value = mock_result
            mock_lc.get_pending_summarisations.return_value = []

            response = client.post("/api/voice/command", json={"text": "yes", "agent_id": 2})
            assert response.status_code == 200
            mock_bridge.send_text.assert_called_once()
            mock_bridge.interrupt_and_send_text.assert_not_called()
            mock_lc.process_turn.assert_called_once()


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

    def test_output_returns_commands(self, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent

        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_cmd.state = CommandState.PROCESSING
        mock_cmd.instruction = "Fix the bug"
        mock_cmd.completion_summary = "Fixed it"
        mock_cmd.full_command = "pytest tests/"
        mock_cmd.full_output = "5 passed"
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_cmd]

        response = client.get("/api/voice/agents/1/output")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["commands"]) == 1
        assert data["commands"][0]["instruction"] == "Fix the bug"
        assert data["commands"][0]["completion_summary"] == "Fixed it"
        assert "latency_ms" in data

    def test_output_empty(self, client, mock_db, mock_agent):
        mock_db.session.get.return_value = mock_agent
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        response = client.get("/api/voice/agents/1/output")
        assert response.status_code == 200
        data = response.get_json()
        assert data["commands"] == []

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

        cmd = MagicMock()
        cmd.id = 50
        cmd.state = CommandState.AWAITING_INPUT

        q_turn = MagicMock()
        q_turn.id = 500
        q_turn.actor = TurnActor.AGENT
        q_turn.intent = TurnIntent.QUESTION
        q_turn.text = "What name should the API use?"
        q_turn.question_text = "What name should the API use?"
        q_turn.question_options = None
        q_turn.question_source_type = "free_text"
        q_turn.tool_input = None

        cmd.turns = [q_turn]
        agent.get_current_command.return_value = cmd
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

        cmd = MagicMock()
        cmd.id = 60
        cmd.state = CommandState.AWAITING_INPUT

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

        cmd.turns = [q_turn]
        agent.get_current_command.return_value = cmd
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

        cmd = MagicMock()
        cmd.id = 70
        cmd.state = CommandState.AWAITING_INPUT
        cmd.turns = []  # No turns at all
        agent.get_current_command.return_value = cmd
        mock_db.session.get.return_value = agent

        response = client.get("/api/voice/agents/7/question")
        assert response.status_code == 404

    def test_awaiting_input_guard(self, client, mock_db, mock_project):
        """Agent not in AWAITING_INPUT returns 409 (task 3.7)."""
        agent = MagicMock()
        agent.id = 8
        agent.project = mock_project
        cmd = MagicMock()
        cmd.state = CommandState.IDLE
        agent.get_current_command.return_value = cmd
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


# ──────────────────────────────────────────────────────────────
# Transcript endpoint tests (tasks 3.3, 3.4, 3.5)
# ──────────────────────────────────────────────────────────────

class TestAgentTranscript:
    """Tests for GET /api/voice/agents/<agent_id>/transcript."""

    def test_agent_not_found(self, client, mock_db):
        mock_db.session.get.return_value = None
        response = client.get("/api/voice/agents/999/transcript")
        assert response.status_code == 404

    def test_returns_turns_across_commands(self, client, mock_db, mock_agent):
        """Transcript returns turns from ALL commands for agent."""
        mock_db.session.get.return_value = mock_agent

        # Mock turns from different commands
        mock_cmd1 = MagicMock()
        mock_cmd1.id = 10
        mock_cmd1.instruction = "Fix the bug"
        mock_cmd1.state = CommandState.COMPLETE

        mock_cmd2 = MagicMock()
        mock_cmd2.id = 20
        mock_cmd2.instruction = "Add tests"
        mock_cmd2.state = CommandState.PROCESSING

        turn1 = MagicMock()
        turn1.id = 1
        turn1.actor = TurnActor.USER
        turn1.intent = TurnIntent.COMMAND
        turn1.text = "fix it"
        turn1.summary = None
        turn1.timestamp = datetime(2026, 2, 10, 1, 0, 0, tzinfo=timezone.utc)
        turn1.tool_input = None
        turn1.question_text = None
        turn1.question_options = None
        turn1.question_source_type = None
        turn1.answered_by_turn_id = None
        turn1.file_metadata = None

        turn2 = MagicMock()
        turn2.id = 2
        turn2.actor = TurnActor.AGENT
        turn2.intent = TurnIntent.COMPLETION
        turn2.text = "Fixed"
        turn2.summary = None
        turn2.timestamp = datetime(2026, 2, 10, 1, 5, 0, tzinfo=timezone.utc)
        turn2.tool_input = None
        turn2.question_text = None
        turn2.question_options = None
        turn2.question_source_type = None
        turn2.answered_by_turn_id = None
        turn2.file_metadata = None

        # Mock the query chain: query(Turn, Command).join().filter().order_by().limit()
        turn_query = MagicMock()
        turn_query.join.return_value = turn_query
        turn_query.filter.return_value = turn_query
        turn_query.order_by.return_value = turn_query
        turn_query.limit.return_value = turn_query
        turn_query.all.return_value = [(turn2, mock_cmd2), (turn1, mock_cmd1)]

        # Empty-command query returns nothing
        empty_cmd_query = MagicMock()
        empty_cmd_query.filter.return_value = empty_cmd_query
        empty_cmd_query.all.return_value = []

        mock_db.session.query.side_effect = [turn_query, empty_cmd_query]

        response = client.get("/api/voice/agents/1/transcript")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["turns"]) == 2
        # Each turn should have command metadata
        assert data["turns"][0]["command_id"] is not None
        assert data["turns"][0]["command_instruction"] is not None
        assert data["turns"][0]["command_state"] is not None

    def test_cursor_pagination(self, client, mock_db, mock_agent):
        """Transcript supports cursor-based pagination."""
        mock_db.session.get.return_value = mock_agent

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        response = client.get("/api/voice/agents/1/transcript?before=100&limit=25")
        assert response.status_code == 200
        data = response.get_json()
        assert "has_more" in data
        assert "turns" in data

    def test_has_more_flag(self, client, mock_db, mock_agent):
        """has_more is true when more turns exist."""
        mock_db.session.get.return_value = mock_agent

        # Return limit+1 results to indicate more exist
        mock_turn = MagicMock()
        mock_turn.id = 1
        mock_turn.actor = TurnActor.USER
        mock_turn.intent = TurnIntent.COMMAND
        mock_turn.text = "test"
        mock_turn.summary = None
        mock_turn.timestamp = datetime(2026, 2, 10, 1, 0, 0, tzinfo=timezone.utc)
        mock_turn.tool_input = None
        mock_turn.question_text = None
        mock_turn.question_options = None
        mock_turn.question_source_type = None
        mock_turn.answered_by_turn_id = None
        mock_turn.file_metadata = None

        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_cmd.instruction = "Test"
        mock_cmd.state = CommandState.PROCESSING

        # Simulate limit=2 returning 3 results (2+1 extra = has_more)
        turn_query = MagicMock()
        turn_query.join.return_value = turn_query
        turn_query.filter.return_value = turn_query
        turn_query.order_by.return_value = turn_query
        turn_query.limit.return_value = turn_query
        turn_query.all.return_value = [(mock_turn, mock_cmd)] * 3

        # Empty-command query returns nothing
        empty_cmd_query = MagicMock()
        empty_cmd_query.filter.return_value = empty_cmd_query
        empty_cmd_query.all.return_value = []

        mock_db.session.query.side_effect = [turn_query, empty_cmd_query]

        response = client.get("/api/voice/agents/1/transcript?limit=2")
        assert response.status_code == 200
        data = response.get_json()
        assert data["has_more"] is True
        assert len(data["turns"]) == 2

    def test_ended_agent_transcript(self, client, mock_db, mock_project):
        """Ended agent returns full history with agent_ended flag."""
        agent = MagicMock()
        agent.id = 5
        agent.name = "ended-agent"
        agent.project = mock_project
        agent.tmux_session = None
        agent.ended_at = datetime(2026, 2, 10, tzinfo=timezone.utc)
        agent.get_current_command.return_value = None

        mock_db.session.get.return_value = agent

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        response = client.get("/api/voice/agents/5/transcript")
        assert response.status_code == 200
        data = response.get_json()
        assert data["agent_ended"] is True
        assert data["agent_state"] == "idle"

    def test_empty_transcript(self, client, mock_db, mock_agent):
        """Agent with no turns returns empty list."""
        mock_db.session.get.return_value = mock_agent

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        response = client.get("/api/voice/agents/1/transcript")
        assert response.status_code == 200
        data = response.get_json()
        assert data["turns"] == []
        assert data["has_more"] is False

    def test_filters_empty_progress_turns(self, client, mock_db, mock_agent):
        """Empty PROGRESS turns are filtered from response."""
        mock_db.session.get.return_value = mock_agent

        turn = MagicMock()
        turn.id = 1
        turn.actor = TurnActor.AGENT
        turn.intent = TurnIntent.PROGRESS
        turn.text = "   "  # whitespace-only
        turn.summary = None
        turn.timestamp = datetime(2026, 2, 10, 1, 0, 0, tzinfo=timezone.utc)
        turn.tool_input = None
        turn.question_text = None
        turn.question_options = None
        turn.question_source_type = None
        turn.answered_by_turn_id = None

        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_cmd.instruction = "Test"
        mock_cmd.state = CommandState.PROCESSING

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [(turn, mock_cmd)]

        response = client.get("/api/voice/agents/1/transcript")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["turns"]) == 0

    def test_limit_capped_at_200(self, client, mock_db, mock_agent):
        """Limit parameter is capped at 200."""
        mock_db.session.get.return_value = mock_agent

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        client.get("/api/voice/agents/1/transcript?limit=500")
        # Should have been capped to 201 (200+1 for has_more check)
        mock_query.limit.assert_called_with(201)

    def test_includes_command_boundaries_for_empty_commands(self, client, mock_db, mock_agent):
        """Synthetic command_boundary entries appear for commands with no turns."""
        mock_db.session.get.return_value = mock_agent

        # Command 1 - has turns
        mock_cmd1 = MagicMock()
        mock_cmd1.id = 10
        mock_cmd1.instruction = "First command"
        mock_cmd1.state = CommandState.COMPLETE

        # Command 2 - NO turns (lost during server downtime)
        mock_cmd2 = MagicMock()
        mock_cmd2.id = 20
        mock_cmd2.instruction = "Empty command"
        mock_cmd2.state = CommandState.COMPLETE
        mock_cmd2.started_at = datetime(2026, 2, 10, 1, 3, 0, tzinfo=timezone.utc)

        # Command 3 - has turns
        mock_cmd3 = MagicMock()
        mock_cmd3.id = 30
        mock_cmd3.instruction = "Third command"
        mock_cmd3.state = CommandState.PROCESSING

        # Turn for command 1 (01:00)
        turn1 = MagicMock()
        turn1.id = 1
        turn1.actor = TurnActor.USER
        turn1.intent = TurnIntent.COMMAND
        turn1.text = "do command 1"
        turn1.summary = None
        turn1.timestamp = datetime(2026, 2, 10, 1, 0, 0, tzinfo=timezone.utc)
        turn1.tool_input = None
        turn1.question_text = None
        turn1.question_options = None
        turn1.question_source_type = None
        turn1.answered_by_turn_id = None
        turn1.file_metadata = None

        # Turn for command 3 (01:10)
        turn2 = MagicMock()
        turn2.id = 2
        turn2.actor = TurnActor.USER
        turn2.intent = TurnIntent.COMMAND
        turn2.text = "do command 3"
        turn2.summary = None
        turn2.timestamp = datetime(2026, 2, 10, 1, 10, 0, tzinfo=timezone.utc)
        turn2.tool_input = None
        turn2.question_text = None
        turn2.question_options = None
        turn2.question_source_type = None
        turn2.answered_by_turn_id = None
        turn2.file_metadata = None

        # First db.session.query(Turn, Command) -- returns turns
        turn_query = MagicMock()
        turn_query.join.return_value = turn_query
        turn_query.filter.return_value = turn_query
        turn_query.order_by.return_value = turn_query
        turn_query.limit.return_value = turn_query
        turn_query.all.return_value = [(turn2, mock_cmd3), (turn1, mock_cmd1)]

        # Second db.session.query(Command) -- returns the empty command
        cmd_query = MagicMock()
        cmd_query.filter.return_value = cmd_query
        cmd_query.all.return_value = [mock_cmd2]

        mock_db.session.query.side_effect = [turn_query, cmd_query]

        response = client.get("/api/voice/agents/1/transcript")
        assert response.status_code == 200
        data = response.get_json()

        # 2 real turns + 1 synthetic command_boundary
        assert len(data["turns"]) == 3

        # Find the synthetic boundary
        boundaries = [t for t in data["turns"] if t.get("type") == "command_boundary"]
        assert len(boundaries) == 1
        assert boundaries[0]["command_id"] == 20
        assert boundaries[0]["command_instruction"] == "Empty command"
        assert boundaries[0]["has_turns"] is False

        # Verify chronological order: turn1 (01:00), boundary (01:03), turn2 (01:10)
        timestamps = [t["timestamp"] for t in data["turns"]]
        assert timestamps == sorted(timestamps)
