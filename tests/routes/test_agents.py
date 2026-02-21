"""Tests for agent lifecycle API routes."""

from unittest.mock import patch

import pytest

from claude_headspace.services.agent_lifecycle import (
    ContextResult,
    CreateResult,
    ShutdownResult,
)


class TestCreateAgentEndpoint:
    """Tests for POST /api/agents."""

    def test_missing_project_id(self, client):
        response = client.post("/api/agents", json={})
        assert response.status_code == 400
        assert "project_id" in response.json["error"]

    def test_invalid_project_id(self, client):
        response = client.post("/api/agents", json={"project_id": "abc"})
        assert response.status_code == 400
        assert "integer" in response.json["error"]

    @patch("claude_headspace.routes.agents.create_agent")
    def test_success(self, mock_create, client):
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent starting",
            tmux_session_name="hs-test-abc123",
        )
        response = client.post("/api/agents", json={"project_id": 1})
        assert response.status_code == 201
        assert response.json["tmux_session_name"] == "hs-test-abc123"

    @patch("claude_headspace.routes.agents.create_agent")
    def test_creation_failure(self, mock_create, client):
        mock_create.return_value = CreateResult(
            success=False, message="Project not found"
        )
        response = client.post("/api/agents", json={"project_id": 99})
        assert response.status_code == 422
        assert "Project not found" in response.json["error"]


class TestShutdownAgentEndpoint:
    """Tests for DELETE /api/agents/<id>."""

    @patch("claude_headspace.routes.agents.shutdown_agent")
    def test_success(self, mock_shutdown, client):
        mock_shutdown.return_value = ShutdownResult(
            success=True, message="Shutdown command sent"
        )
        response = client.delete("/api/agents/1")
        assert response.status_code == 200

    @patch("claude_headspace.routes.agents.shutdown_agent")
    def test_not_found(self, mock_shutdown, client):
        mock_shutdown.return_value = ShutdownResult(
            success=False, message="Agent not found"
        )
        response = client.delete("/api/agents/99")
        assert response.status_code == 404

    @patch("claude_headspace.routes.agents.shutdown_agent")
    def test_no_tmux_pane(self, mock_shutdown, client):
        mock_shutdown.return_value = ShutdownResult(
            success=False, message="Agent has no tmux pane"
        )
        response = client.delete("/api/agents/1")
        assert response.status_code == 422


class TestAgentContextEndpoint:
    """Tests for GET /api/agents/<id>/context."""

    @patch("claude_headspace.routes.agents.broadcast_card_refresh")
    @patch("claude_headspace.routes.agents.db")
    @patch("claude_headspace.routes.agents.get_context_usage")
    def test_success(self, mock_ctx, mock_db, mock_broadcast, client):
        from unittest.mock import MagicMock

        mock_agent = MagicMock()
        mock_db.session.get.return_value = mock_agent
        mock_ctx.return_value = ContextResult(
            available=True,
            percent_used=45,
            remaining_tokens="110k",
            raw="[ctx: 45% used, 110k remaining]",
        )
        response = client.get("/api/agents/1/context")
        assert response.status_code == 200
        assert response.json["available"] is True
        assert response.json["percent_used"] == 45
        assert response.json["remaining_tokens"] == "110k"
        # Verify agent record was updated
        assert mock_agent.context_percent_used == 45
        assert mock_agent.context_remaining_tokens == "110k"
        mock_db.session.commit.assert_called_once()
        mock_broadcast.assert_called_once_with(mock_agent, "context_fetched")

    @patch("claude_headspace.routes.agents.get_context_usage")
    def test_not_found(self, mock_ctx, client):
        mock_ctx.return_value = ContextResult(
            available=False, reason="agent_not_found"
        )
        response = client.get("/api/agents/99/context")
        assert response.status_code == 404

    @patch("claude_headspace.routes.agents.get_context_usage")
    def test_unavailable(self, mock_ctx, client):
        mock_ctx.return_value = ContextResult(
            available=False, reason="statusline_not_found"
        )
        response = client.get("/api/agents/1/context")
        assert response.status_code == 200
        assert response.json["available"] is False
        assert response.json["reason"] == "statusline_not_found"


class TestHandoffAgentEndpoint:
    """Tests for POST /api/agents/<id>/handoff."""

    def test_success(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=True, message="Handoff initiated"
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post(
            "/api/agents/1/handoff",
            json={"reason": "context_limit"},
        )
        assert response.status_code == 200
        assert response.json["status"] == "initiated"
        mock_executor.trigger_handoff.assert_called_once_with(
            1, reason="context_limit"
        )

    def test_default_reason(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=True, message="Handoff initiated"
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post("/api/agents/1/handoff", json={})
        assert response.status_code == 200
        mock_executor.trigger_handoff.assert_called_once_with(
            1, reason="manual"
        )

    def test_agent_not_found(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=False, message="Agent not found", error_code="not_found"
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post("/api/agents/999/handoff", json={})
        assert response.status_code == 404
        assert "Agent not found" in response.json["error"]

    def test_already_in_progress(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=False,
            message="Handoff already in progress",
            error_code="already_in_progress",
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post("/api/agents/1/handoff", json={})
        assert response.status_code == 409

    def test_no_persona(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=False,
            message="Agent has no persona",
            error_code="no_persona",
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post("/api/agents/1/handoff", json={})
        assert response.status_code == 400
        assert "no persona" in response.json["error"]

    def test_no_tmux_pane(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=False,
            message="Agent has no tmux pane",
            error_code="no_tmux_pane",
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post("/api/agents/1/handoff", json={})
        assert response.status_code == 400

    def test_not_active(self, client, app):
        from unittest.mock import MagicMock

        from claude_headspace.services.handoff_executor import HandoffResult

        mock_executor = MagicMock()
        mock_executor.trigger_handoff.return_value = HandoffResult(
            success=False,
            message="Agent is not active",
            error_code="not_active",
        )
        app.extensions["handoff_executor"] = mock_executor

        response = client.post("/api/agents/1/handoff", json={})
        assert response.status_code == 400


class TestAgentInfoEndpoint:
    """Tests for GET /api/agents/<id>/info."""

    @patch("claude_headspace.routes.agents.get_agent_info")
    def test_success(self, mock_info, client):
        mock_info.return_value = {
            "identity": {
                "id": 1,
                "session_uuid": "12345678-abcd-1234-abcd-123456789abc",
                "session_uuid_short": "12345678",
                "claude_session_id": None,
                "tmux_pane_id": "%5",
                "iterm_pane_id": None,
                "transcript_path": None,
                "tmux_session_name": "hs-test-abc",
                "tmux_pane_alive": True,
                "bridge_available": False,
            },
            "project": {
                "id": 1,
                "name": "test-project",
                "slug": "test-project",
                "path": "/tmp/test",
                "current_branch": "main",
                "github_repo": None,
            },
            "lifecycle": {
                "started_at": "2025-01-01T00:00:00+00:00",
                "last_seen_at": "2025-01-01T01:00:00+00:00",
                "ended_at": None,
                "uptime": "up 1h",
                "current_state": "PROCESSING",
                "is_active": True,
            },
            "priority": {"score": 75, "reason": "Active command", "updated_at": None},
            "headspace": None,
            "frustration_scores": [],
            "commands": [],
        }
        response = client.get("/api/agents/1/info")
        assert response.status_code == 200
        data = response.json
        assert data["identity"]["id"] == 1
        assert data["identity"]["tmux_pane_alive"] is True
        assert data["lifecycle"]["current_state"] == "PROCESSING"
        assert data["project"]["name"] == "test-project"
        assert data["commands"] == []

    @patch("claude_headspace.routes.agents.get_agent_info")
    def test_not_found(self, mock_info, client):
        mock_info.return_value = None
        response = client.get("/api/agents/999/info")
        assert response.status_code == 404
        assert "error" in response.json
