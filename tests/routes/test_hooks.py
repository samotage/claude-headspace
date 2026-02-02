"""Tests for the hooks API routes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.hooks import hooks_bp
from src.claude_headspace.services.hook_receiver import (
    HookEventResult,
    HookMode,
    HookReceiverState,
)
from src.claude_headspace.services.session_correlator import CorrelationResult


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(hooks_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_receiver_state():
    """Mock hook receiver state."""
    with patch("src.claude_headspace.routes.hooks.get_receiver_state") as mock:
        state = HookReceiverState()
        state.enabled = True
        mock.return_value = state
        yield state


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.id = 1
    agent.state.value = "idle"
    return agent


@pytest.fixture
def mock_correlation(mock_agent):
    """Create a mock correlation result."""
    return CorrelationResult(
        agent=mock_agent,
        is_new=False,
        correlation_method="session_id",
    )


class TestHookSessionStart:
    """Tests for POST /hook/session-start."""

    def test_missing_content_type(self, client, mock_receiver_state):
        """Test error when Content-Type is not JSON."""
        response = client.post(
            "/hook/session-start",
            data="not json",
        )
        assert response.status_code == 400
        assert "application/json" in response.get_json()["message"]

    def test_missing_session_id(self, client, mock_receiver_state):
        """Test error when session_id is missing."""
        response = client.post(
            "/hook/session-start",
            json={},
        )
        assert response.status_code == 400
        assert "session_id" in response.get_json()["message"]

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_session_start")
    def test_successful_session_start(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful session start."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=False,
            new_state="idle",
        )

        response = client.post(
            "/hook/session-start",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1

    def test_hooks_disabled(self, client, mock_receiver_state):
        """Test ignored when hooks are disabled."""
        mock_receiver_state.enabled = False

        response = client.post(
            "/hook/session-start",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        assert response.get_json()["status"] == "ignored"


class TestHookSessionEnd:
    """Tests for POST /hook/session-end."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_session_end")
    def test_successful_session_end(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful session end."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="complete",
        )

        response = client.post(
            "/hook/session-end",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"


class TestHookUserPromptSubmit:
    """Tests for POST /hook/user-prompt-submit."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_user_prompt_submit")
    def test_successful_prompt_submit(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful user prompt submit."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="processing",
        )

        response = client.post(
            "/hook/user-prompt-submit",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["state"] == "processing"
        assert data["state_changed"] is True


class TestHookStop:
    """Tests for POST /hook/stop."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_stop")
    def test_successful_stop(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful stop."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="complete",
        )

        response = client.post(
            "/hook/stop",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["state"] == "complete"

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_stop")
    def test_stop_with_question_returns_awaiting_input(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test stop returns AWAITING_INPUT when question detected."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="awaiting_input",
        )

        response = client.post(
            "/hook/stop",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["state"] == "awaiting_input"
        assert data["state_changed"] is True


class TestHookNotification:
    """Tests for POST /hook/notification."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_notification")
    def test_successful_notification(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful notification."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=False,
        )

        response = client.post(
            "/hook/notification",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"


class TestHookStatus:
    """Tests for GET /hook/status."""

    def test_status_disabled(self, client, mock_receiver_state):
        """Test status when hooks are disabled."""
        mock_receiver_state.enabled = False

        response = client.get("/hook/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is False

    def test_status_hooks_active(self, client, mock_receiver_state):
        """Test status when hooks are active."""
        mock_receiver_state.mode = HookMode.HOOKS_ACTIVE
        mock_receiver_state.last_event_at = datetime.now(timezone.utc)
        mock_receiver_state.events_received = 42

        response = client.get("/hook/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is True
        assert data["mode"] == "hooks_active"
        assert data["events_received"] == 42

    def test_status_includes_config(self, client, mock_receiver_state):
        """Test status includes configuration."""
        response = client.get("/hook/status")

        assert response.status_code == 200
        data = response.get_json()
        assert "config" in data
        assert "polling_interval_with_hooks" in data["config"]
        assert "fallback_timeout" in data["config"]

    def test_status_formats_last_event_ago(self, client, mock_receiver_state):
        """Test last_event_ago formatting."""
        mock_receiver_state.last_event_at = datetime.now(timezone.utc)

        response = client.get("/hook/status")

        data = response.get_json()
        assert data["last_event_ago"] is not None
        assert "ago" in data["last_event_ago"]


class TestPayloadValidation:
    """Tests for payload validation."""

    def test_invalid_json(self, client, mock_receiver_state):
        """Test error on invalid JSON."""
        response = client.post(
            "/hook/session-start",
            data="not valid json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_empty_payload(self, client, mock_receiver_state):
        """Test error on empty payload."""
        response = client.post(
            "/hook/session-start",
            json={},
        )
        assert response.status_code == 400
        assert "session_id" in response.get_json()["message"]


class TestErrorHandling:
    """Tests for error handling."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    def test_correlation_error(
        self, mock_correlate, client, mock_receiver_state
    ):
        """Test handling of correlation errors."""
        mock_correlate.side_effect = Exception("Database error")

        response = client.post(
            "/hook/session-start",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 500
        assert "error" in response.get_json()["status"]

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_session_start")
    def test_processing_error(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test handling of processing errors."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=False,
            error_message="Processing failed",
        )

        response = client.post(
            "/hook/session-start",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 500
        assert response.get_json()["message"] == "Processing failed"


class TestHookPreToolUse:
    """Tests for POST /hook/pre-tool-use."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_pre_tool_use")
    def test_successful_pre_tool_use(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful pre-tool-use hook."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="AWAITING_INPUT",
        )

        response = client.post(
            "/hook/pre-tool-use",
            json={"session_id": "test-session", "tool_name": "AskUserQuestion"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["state_changed"] is True
        assert data["new_state"] == "AWAITING_INPUT"

    def test_missing_session_id(self, client, mock_receiver_state):
        """Test error when session_id is missing."""
        response = client.post(
            "/hook/pre-tool-use",
            json={"tool_name": "AskUserQuestion"},
        )
        assert response.status_code == 400
        assert "session_id" in response.get_json()["message"]

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_pre_tool_use")
    def test_passes_tool_input_to_service(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test that tool_input is extracted from payload and passed to service."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True, agent_id=1, state_changed=True, new_state="AWAITING_INPUT",
        )

        tool_input = {"questions": [{"question": "Which one?"}]}
        response = client.post(
            "/hook/pre-tool-use",
            json={
                "session_id": "test-session",
                "tool_name": "AskUserQuestion",
                "tool_input": tool_input,
            },
        )

        assert response.status_code == 200
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args
        assert call_kwargs[1]["tool_name"] == "AskUserQuestion"
        assert call_kwargs[1]["tool_input"] == tool_input


class TestHookPermissionRequest:
    """Tests for POST /hook/permission-request."""

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_permission_request")
    def test_successful_permission_request(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test successful permission-request hook."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True,
            agent_id=1,
            state_changed=True,
            new_state="AWAITING_INPUT",
        )

        response = client.post(
            "/hook/permission-request",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["state_changed"] is True
        assert data["new_state"] == "AWAITING_INPUT"

    def test_missing_session_id(self, client, mock_receiver_state):
        """Test error when session_id is missing."""
        response = client.post(
            "/hook/permission-request",
            json={},
        )
        assert response.status_code == 400
        assert "session_id" in response.get_json()["message"]

    @patch("src.claude_headspace.routes.hooks.correlate_session")
    @patch("src.claude_headspace.routes.hooks.process_permission_request")
    def test_passes_tool_name_and_tool_input_to_service(
        self, mock_process, mock_correlate, client, mock_receiver_state, mock_correlation
    ):
        """Test that tool_name and tool_input are extracted and passed to service."""
        mock_correlate.return_value = mock_correlation
        mock_process.return_value = HookEventResult(
            success=True, agent_id=1, state_changed=True, new_state="AWAITING_INPUT",
        )

        tool_input = {"command": "npm install"}
        response = client.post(
            "/hook/permission-request",
            json={
                "session_id": "test-session",
                "tool_name": "Bash",
                "tool_input": tool_input,
            },
        )

        assert response.status_code == 200
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args
        assert call_kwargs[1]["tool_name"] == "Bash"
        assert call_kwargs[1]["tool_input"] == tool_input
