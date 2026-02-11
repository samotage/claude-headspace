"""Tests for voice bridge agent lifecycle endpoints (create, shutdown, context)."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.voice_bridge import voice_bridge_bp
from src.claude_headspace.services.agent_lifecycle import (
    ContextResult,
    CreateResult,
    ShutdownResult,
)


@pytest.fixture
def app():
    """Create a test Flask app with voice bridge blueprint."""
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
    app.extensions = {
        "voice_auth": None,
        "voice_formatter": None,
    }
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestVoiceCreateAgent:
    """Tests for POST /api/voice/agents/create."""

    def test_missing_project(self, client):
        response = client.post(
            "/api/voice/agents/create",
            json={},
            content_type="application/json",
        )
        # _voice_error returns 400 by default
        assert response.status_code == 400
        assert "error" in response.json

    @patch("src.claude_headspace.routes.voice_bridge.create_agent")
    def test_create_by_project_id(self, mock_create, client):
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent starting in tmux session 'hs-test-abc'.",
            tmux_session_name="hs-test-abc",
        )
        response = client.post(
            "/api/voice/agents/create",
            json={"project_id": 1},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert "voice" in response.json
        assert response.json["tmux_session_name"] == "hs-test-abc"
        mock_create.assert_called_once_with(1)

    @patch("src.claude_headspace.routes.voice_bridge.db")
    @patch("src.claude_headspace.routes.voice_bridge.create_agent")
    def test_create_by_project_name(self, mock_create, mock_db, client):
        # Mock the project name lookup
        mock_project = MagicMock()
        mock_project.id = 42
        mock_db.session.query.return_value.filter.return_value.first.return_value = (
            mock_project
        )
        mock_db.func.lower = MagicMock()
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent starting.",
            tmux_session_name="hs-proj-abc",
        )
        response = client.post(
            "/api/voice/agents/create",
            json={"project_name": "my-project"},
            content_type="application/json",
        )
        assert response.status_code == 201
        mock_create.assert_called_once_with(42)

    @patch("src.claude_headspace.routes.voice_bridge.db")
    def test_project_name_not_found(self, mock_db, client):
        mock_db.session.query.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.func.lower = MagicMock()
        response = client.post(
            "/api/voice/agents/create",
            json={"project_name": "nonexistent"},
            content_type="application/json",
        )
        assert response.status_code == 404

    @patch("src.claude_headspace.routes.voice_bridge.create_agent")
    def test_create_failure(self, mock_create, client):
        mock_create.return_value = CreateResult(
            success=False, message="tmux is not installed"
        )
        response = client.post(
            "/api/voice/agents/create",
            json={"project_id": 1},
            content_type="application/json",
        )
        assert response.status_code == 422
        assert "error" in response.json


class TestVoiceShutdownAgent:
    """Tests for POST /api/voice/agents/<id>/shutdown."""

    @patch("src.claude_headspace.routes.voice_bridge.shutdown_agent")
    def test_success(self, mock_shutdown, client):
        mock_shutdown.return_value = ShutdownResult(
            success=True, message="Shutdown command sent."
        )
        response = client.post("/api/voice/agents/1/shutdown")
        assert response.status_code == 200
        assert "voice" in response.json

    @patch("src.claude_headspace.routes.voice_bridge.shutdown_agent")
    def test_not_found(self, mock_shutdown, client):
        mock_shutdown.return_value = ShutdownResult(
            success=False, message="Agent not found"
        )
        response = client.post("/api/voice/agents/99/shutdown")
        assert response.status_code == 404

    @patch("src.claude_headspace.routes.voice_bridge.shutdown_agent")
    def test_no_pane(self, mock_shutdown, client):
        mock_shutdown.return_value = ShutdownResult(
            success=False, message="Agent has no tmux pane"
        )
        response = client.post("/api/voice/agents/1/shutdown")
        assert response.status_code == 422


class TestVoiceAgentContext:
    """Tests for GET /api/voice/agents/<id>/context."""

    @patch("src.claude_headspace.routes.voice_bridge.get_context_usage")
    def test_success(self, mock_ctx, client):
        mock_ctx.return_value = ContextResult(
            available=True,
            percent_used=45,
            remaining_tokens="110k",
            raw="[ctx: 45% used, 110k remaining]",
        )
        response = client.get("/api/voice/agents/1/context")
        assert response.status_code == 200
        assert response.json["available"] is True
        assert response.json["percent_used"] == 45
        assert "voice" in response.json

    @patch("src.claude_headspace.routes.voice_bridge.get_context_usage")
    def test_not_found(self, mock_ctx, client):
        mock_ctx.return_value = ContextResult(
            available=False, reason="agent_not_found"
        )
        response = client.get("/api/voice/agents/99/context")
        assert response.status_code == 404

    @patch("src.claude_headspace.routes.voice_bridge.get_context_usage")
    def test_unavailable(self, mock_ctx, client):
        mock_ctx.return_value = ContextResult(
            available=False, reason="statusline_not_found"
        )
        response = client.get("/api/voice/agents/1/context")
        assert response.status_code == 200
        assert response.json["available"] is False
