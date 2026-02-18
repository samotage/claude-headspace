"""Tests for the project show tree drill-down API endpoints."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.projects import projects_bp

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TEMPLATE_DIR = os.path.join(_PROJECT_ROOT, "templates")


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.register_blueprint(projects_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("src.claude_headspace.routes.projects.db") as mock:
        mock.session = MagicMock()
        yield mock


# --- GET /api/agents/<id>/commands ---


class TestGetAgentCommands:
    """Tests for the agent commands endpoint."""

    def test_returns_commands_for_agent(self, client, mock_db):
        """Test 200 response with commands list."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_db.session.get.return_value = mock_agent

        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_cmd.state = MagicMock()
        mock_cmd.state.value = "PROCESSING"
        mock_cmd.instruction = "Fix the bug"
        mock_cmd.completion_summary = None
        mock_cmd.started_at = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_cmd.completed_at = None

        # First query: commands (filter -> order_by -> all -> [mock_cmd])
        # Second query: turn counts (filter -> group_by -> all -> [(command_id, count)])
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.group_by.return_value = query_mock
        query_mock.all.side_effect = [[mock_cmd], [(10, 5)]]  # commands, then turn counts
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/agents/1/commands")
        assert resp.status_code == 200

        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 10
        assert data[0]["state"] == "PROCESSING"
        assert data[0]["instruction"] == "Fix the bug"
        assert data[0]["turn_count"] == 5

    def test_agent_not_found(self, client, mock_db):
        """Test 404 when agent doesn't exist."""
        mock_db.session.get.return_value = None

        resp = client.get("/api/agents/999/commands")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_empty_commands(self, client, mock_db):
        """Test 200 with empty list when agent has no commands."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_db.session.get.return_value = mock_agent

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = []
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/agents/1/commands")
        assert resp.status_code == 200
        assert resp.get_json() == []


# --- GET /api/commands/<id>/turns ---


class TestGetCommandTurns:
    """Tests for the command turns endpoint."""

    def test_returns_turns_for_command(self, client, mock_db):
        """Test 200 response with turns list."""
        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_db.session.get.return_value = mock_cmd

        mock_turn = MagicMock()
        mock_turn.id = 100
        mock_turn.actor = MagicMock()
        mock_turn.actor.value = "USER"
        mock_turn.intent = MagicMock()
        mock_turn.intent.value = "COMMAND"
        mock_turn.summary = "User asked to fix the bug"
        mock_turn.frustration_score = 3
        mock_turn.timestamp = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = [mock_turn]
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/commands/10/turns")
        assert resp.status_code == 200

        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 100
        assert data[0]["actor"] == "USER"
        assert data[0]["intent"] == "COMMAND"
        assert data[0]["summary"] == "User asked to fix the bug"
        assert data[0]["frustration_score"] == 3

    def test_command_not_found(self, client, mock_db):
        """Test 404 when command doesn't exist."""
        mock_db.session.get.return_value = None

        resp = client.get("/api/commands/999/turns")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_turns_with_null_frustration(self, client, mock_db):
        """Test turns with null frustration score (agent turns)."""
        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_db.session.get.return_value = mock_cmd

        mock_turn = MagicMock()
        mock_turn.id = 101
        mock_turn.actor = MagicMock()
        mock_turn.actor.value = "AGENT"
        mock_turn.intent = MagicMock()
        mock_turn.intent.value = "PROGRESS"
        mock_turn.summary = "Working on the fix"
        mock_turn.frustration_score = None
        mock_turn.timestamp = datetime(2026, 2, 1, 12, 1, 0, tzinfo=timezone.utc)

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = [mock_turn]
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/commands/10/turns")
        assert resp.status_code == 200

        data = resp.get_json()
        assert data[0]["frustration_score"] is None

    def test_empty_turns(self, client, mock_db):
        """Test 200 with empty list when command has no turns."""
        mock_cmd = MagicMock()
        mock_cmd.id = 10
        mock_db.session.get.return_value = mock_cmd

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = []
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/commands/10/turns")
        assert resp.status_code == 200
        assert resp.get_json() == []


# --- GET /api/projects/<id>/inference-summary ---


class TestGetProjectInferenceSummary:
    """Tests for the project inference summary endpoint."""

    def test_returns_inference_summary(self, client, mock_db):
        """Test 200 response with inference metrics."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_db.session.get.return_value = mock_project

        mock_row = MagicMock()
        mock_row.total_calls = 42
        mock_row.total_input_tokens = 50000
        mock_row.total_output_tokens = 10000
        mock_row.total_cost = 0.75

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.one.return_value = mock_row
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/projects/1/inference-summary")
        assert resp.status_code == 200

        data = resp.get_json()
        assert data["project_id"] == 1
        assert data["total_calls"] == 42
        assert data["total_input_tokens"] == 50000
        assert data["total_output_tokens"] == 10000
        assert data["total_cost"] == 0.75

    def test_project_not_found(self, client, mock_db):
        """Test 404 when project doesn't exist."""
        mock_db.session.get.return_value = None

        resp = client.get("/api/projects/999/inference-summary")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_zero_inference_calls(self, client, mock_db):
        """Test response when project has no inference calls."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_db.session.get.return_value = mock_project

        mock_row = MagicMock()
        mock_row.total_calls = 0
        mock_row.total_input_tokens = 0
        mock_row.total_output_tokens = 0
        mock_row.total_cost = 0

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.one.return_value = mock_row
        mock_db.session.query.return_value = query_mock

        resp = client.get("/api/projects/1/inference-summary")
        assert resp.status_code == 200

        data = resp.get_json()
        assert data["total_calls"] == 0
        assert data["total_cost"] == 0.0
