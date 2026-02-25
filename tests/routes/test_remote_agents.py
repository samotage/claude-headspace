"""Tests for the remote agents API routes."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from claude_headspace.routes.remote_agents import remote_agents_bp
from claude_headspace.services.session_token import SessionTokenService
from claude_headspace.services.remote_agent_service import RemoteAgentResult


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def token_service():
    return SessionTokenService()


@pytest.fixture
def mock_remote_service():
    return MagicMock()


@pytest.fixture
def app(token_service, mock_remote_service):
    """Create a test Flask application with remote agents blueprint."""
    app = Flask(
        __name__,
        template_folder="../../templates",
    )
    app.register_blueprint(remote_agents_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "remote_agents": {
            "allowed_origins": ["https://allowed.example.com"],
            "embed_defaults": {
                "file_upload": False,
                "context_usage": False,
                "voice_mic": False,
            },
        },
        "server": {
            "application_url": "https://test.example.com:5055",
        },
    }
    app.extensions = {
        "session_token_service": token_service,
        "remote_agent_service": mock_remote_service,
    }
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# ──────────────────────────────────────────────────────────────
# Create endpoint tests
# ──────────────────────────────────────────────────────────────

class TestCreateEndpoint:
    """Tests for POST /api/remote_agents/create."""

    def test_missing_fields_returns_400(self, client):
        resp = client.post("/api/remote_agents/create", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "missing_fields"

    def test_partial_fields_returns_400(self, client):
        resp = client.post(
            "/api/remote_agents/create",
            json={"project_slug": "test"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "persona_slug" in data["error"]["message"]
        assert "initial_prompt" in data["error"]["message"]

    def test_invalid_feature_flags_returns_400(self, client):
        resp = client.post(
            "/api/remote_agents/create",
            json={
                "project_slug": "test",
                "persona_slug": "test",
                "initial_prompt": "hello",
                "feature_flags": "not-a-dict",
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "invalid_feature_flags"

    def test_successful_create_returns_201(self, client, mock_remote_service):
        mock_remote_service.create_blocking.return_value = RemoteAgentResult(
            success=True,
            agent_id=42,
            embed_url="https://test.example.com:5055/embed/42?token=abc",
            session_token="abc",
            project_slug="test-project",
            persona_slug="test",
            tmux_session_name="hs-test-abc123",
            status="ready",
        )

        resp = client.post(
            "/api/remote_agents/create",
            json={
                "project_slug": "test-project",
                "persona_slug": "test",
                "initial_prompt": "hello",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["agent_id"] == 42
        assert data["session_token"] == "abc"
        assert data["status"] == "ready"

    def test_project_not_found_returns_404(self, client, mock_remote_service):
        mock_remote_service.create_blocking.return_value = RemoteAgentResult(
            success=False,
            error_code="project_not_found",
            error_message="Project 'bad' not found",
        )

        resp = client.post(
            "/api/remote_agents/create",
            json={
                "project_slug": "bad",
                "persona_slug": "test",
                "initial_prompt": "hello",
            },
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "project_not_found"

    def test_timeout_returns_408_with_retryable(self, client, mock_remote_service):
        mock_remote_service.create_blocking.return_value = RemoteAgentResult(
            success=False,
            error_code="agent_creation_timeout",
            error_message="Timed out",
        )

        resp = client.post(
            "/api/remote_agents/create",
            json={
                "project_slug": "test",
                "persona_slug": "test",
                "initial_prompt": "hello",
            },
        )
        assert resp.status_code == 408
        data = resp.get_json()
        assert data["error"]["code"] == "agent_creation_timeout"
        assert data["error"]["retryable"] is True
        assert data["error"]["retry_after_seconds"] == 5


# ──────────────────────────────────────────────────────────────
# Alive endpoint tests
# ──────────────────────────────────────────────────────────────

class TestAliveEndpoint:
    """Tests for GET /api/remote_agents/<id>/alive."""

    def test_missing_token_returns_401(self, client):
        resp = client.get("/api/remote_agents/1/alive")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"]["code"] == "invalid_session_token"

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/remote_agents/1/alive",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"]["code"] == "invalid_session_token"

    def test_wrong_agent_token_returns_401(self, client, token_service):
        """Token for agent 2 should not work for agent 1."""
        token = token_service.generate(agent_id=2)
        resp = client.get(
            "/api/remote_agents/1/alive",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    def test_valid_token_returns_200(self, client, token_service, mock_remote_service):
        token = token_service.generate(agent_id=1)
        mock_remote_service.check_alive.return_value = {
            "alive": True,
            "agent_id": 1,
            "state": "processing",
        }

        resp = client.get(
            "/api/remote_agents/1/alive",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["alive"] is True

    def test_token_via_query_param(self, client, token_service, mock_remote_service):
        token = token_service.generate(agent_id=1)
        mock_remote_service.check_alive.return_value = {"alive": True}

        resp = client.get(f"/api/remote_agents/1/alive?token={token}")
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────
# Shutdown endpoint tests
# ──────────────────────────────────────────────────────────────

class TestShutdownEndpoint:
    """Tests for POST /api/remote_agents/<id>/shutdown.

    Response shapes per S5 FR3 contract:
    - 200 initiated: {"status": "ok", "agent_id": N, "message": "Agent shutdown initiated"}
    - 200 idempotent: {"status": "ok", "agent_id": N, "message": "Agent already terminated"}
    - 401: standard error envelope (invalid_session_token)
    - 404: standard error envelope (agent_not_found)
    """

    def test_missing_token_returns_401(self, client):
        resp = client.post("/api/remote_agents/1/shutdown")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"]["code"] == "invalid_session_token"

    def test_shutdown_initiated(self, client, token_service, mock_remote_service):
        token = token_service.generate(agent_id=1)
        mock_remote_service.shutdown.return_value = {
            "result": "initiated",
            "agent_id": 1,
        }

        resp = client.post(
            "/api/remote_agents/1/shutdown",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["message"] == "Agent shutdown initiated"

    def test_already_terminated_returns_200(self, client, token_service, mock_remote_service):
        """Idempotent — double-shutdown returns 200, not an error."""
        token = token_service.generate(agent_id=1)
        mock_remote_service.shutdown.return_value = {
            "result": "already_terminated",
            "agent_id": 1,
        }

        resp = client.post(
            "/api/remote_agents/1/shutdown",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["agent_id"] == 1
        assert data["message"] == "Agent already terminated"

    def test_agent_not_found_returns_404(self, client, token_service, mock_remote_service):
        token = token_service.generate(agent_id=1)
        mock_remote_service.shutdown.return_value = {
            "result": "not_found",
            "agent_id": 1,
        }

        resp = client.post(
            "/api/remote_agents/1/shutdown",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "agent_not_found"


# ──────────────────────────────────────────────────────────────
# CORS tests
# ──────────────────────────────────────────────────────────────

class TestCORS:
    """Tests for CORS header handling."""

    def test_allowed_origin_gets_cors_headers(self, client):
        resp = client.post(
            "/api/remote_agents/create",
            json={},
            headers={"Origin": "https://allowed.example.com"},
        )
        assert resp.headers.get("Access-Control-Allow-Origin") == "https://allowed.example.com"
        assert "Authorization" in resp.headers.get("Access-Control-Allow-Headers", "")

    def test_disallowed_origin_no_cors_headers(self, client):
        resp = client.post(
            "/api/remote_agents/create",
            json={},
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.headers.get("Access-Control-Allow-Origin") is None

    def test_no_origin_no_cors_headers(self, client):
        resp = client.post("/api/remote_agents/create", json={})
        assert resp.headers.get("Access-Control-Allow-Origin") is None

    def test_options_preflight_returns_204(self, client):
        resp = client.options(
            "/api/remote_agents/create",
            headers={"Origin": "https://allowed.example.com"},
        )
        assert resp.status_code == 204


# ──────────────────────────────────────────────────────────────
# Embed view tests
# ──────────────────────────────────────────────────────────────

class TestEmbedView:
    """Tests for the embed view route."""

    def test_missing_token_returns_401(self, client):
        resp = client.get("/embed/1")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/embed/1?token=bad-token")
        assert resp.status_code == 401

    def test_wrong_agent_token_returns_401(self, client, token_service):
        token = token_service.generate(agent_id=2)
        resp = client.get(f"/embed/1?token={token}")
        assert resp.status_code == 401

    def test_valid_token_renders_template(self, client, token_service, app):
        """Valid token should render the embed chat template (may 500 if template
        directory isn't set up for test, but should NOT be 401)."""
        token = token_service.generate(agent_id=1)
        resp = client.get(f"/embed/1?token={token}")
        # We expect either 200 (template found) or 500 (template not found)
        # but NOT 401 (auth should pass)
        assert resp.status_code != 401


# ──────────────────────────────────────────────────────────────
# Error envelope tests
# ──────────────────────────────────────────────────────────────

class TestErrorEnvelope:
    """Tests for standardised error response format (S5 FR5 contract).

    Error envelope: {"error": {"code": "...", "message": "...", "status": N,
                               "retryable": bool, "retry_after_seconds": N|null}}
    """

    def test_error_envelope_structure(self, client):
        resp = client.get("/api/remote_agents/1/alive")
        data = resp.get_json()

        assert "error" in data
        err = data["error"]
        assert isinstance(err["code"], str)
        assert isinstance(err["message"], str)
        assert isinstance(err["status"], int)
        assert isinstance(err["retryable"], bool)
        assert "retry_after_seconds" in err  # always present, even if null

    def test_retryable_includes_retry_after(self, client, mock_remote_service):
        mock_remote_service.create_blocking.return_value = RemoteAgentResult(
            success=False,
            error_code="agent_creation_timeout",
            error_message="Timed out",
        )

        resp = client.post(
            "/api/remote_agents/create",
            json={
                "project_slug": "test",
                "persona_slug": "test",
                "initial_prompt": "hello",
            },
        )
        data = resp.get_json()
        assert data["error"]["retryable"] is True
        assert data["error"]["retry_after_seconds"] == 5

    def test_non_retryable_has_null_retry_after(self, client):
        """Non-retryable errors have retry_after_seconds: null."""
        resp = client.get("/api/remote_agents/1/alive")
        data = resp.get_json()
        assert data["error"]["retryable"] is False
        assert data["error"]["retry_after_seconds"] is None
