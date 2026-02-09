"""Tests for GET /api/tasks/<id>/full-text endpoint and full-text exclusion (e5-s9).

Tests cover:
- Task 3.4: Route tests for full-text endpoint (happy path, 404, empty fields)
- Task 3.5: Verify /api/agents/<id>/tasks does NOT include full_command/full_output
- Task 3.6: Verify SSE card_refresh events do NOT include full text fields
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.projects import projects_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
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


@pytest.fixture
def mock_task_with_full_text():
    """Create a mock task with full_command and full_output."""
    task = MagicMock()
    task.id = 1
    task.full_command = "Please refactor the auth module to use JWT"
    task.full_output = "Done. I've refactored the auth module.\n\nChanges:\n1. jwt_utils.py\n2. middleware.py"
    return task


@pytest.fixture
def mock_task_empty_fields():
    """Create a mock task with no full text fields."""
    task = MagicMock()
    task.id = 2
    task.full_command = None
    task.full_output = None
    return task


class TestGetTaskFullText:
    """Task 3.4: Route tests for GET /api/tasks/<id>/full-text."""

    def test_happy_path_returns_full_text(self, client, mock_db, mock_task_with_full_text):
        """Should return full_command and full_output for existing task."""
        mock_db.session.get.return_value = mock_task_with_full_text

        response = client.get("/api/tasks/1/full-text")

        assert response.status_code == 200
        data = response.get_json()
        assert data["full_command"] == "Please refactor the auth module to use JWT"
        assert "Done. I've refactored" in data["full_output"]

    def test_returns_null_when_fields_empty(self, client, mock_db, mock_task_empty_fields):
        """Should return null for fields that haven't been populated."""
        mock_db.session.get.return_value = mock_task_empty_fields

        response = client.get("/api/tasks/2/full-text")

        assert response.status_code == 200
        data = response.get_json()
        assert data["full_command"] is None
        assert data["full_output"] is None

    def test_returns_404_for_nonexistent_task(self, client, mock_db):
        """Should return 404 when task doesn't exist."""
        mock_db.session.get.return_value = None

        response = client.get("/api/tasks/999/full-text")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_returns_only_two_fields(self, client, mock_db, mock_task_with_full_text):
        """Response should contain exactly full_command and full_output keys."""
        mock_db.session.get.return_value = mock_task_with_full_text

        response = client.get("/api/tasks/1/full-text")

        data = response.get_json()
        assert set(data.keys()) == {"full_command", "full_output"}


class TestAgentTasksExcludesFullText:
    """Task 3.5: Verify /api/agents/<id>/tasks does NOT include full_command or full_output."""

    def test_agent_tasks_excludes_full_text_fields(self, client, mock_db):
        """GET /api/agents/<id>/tasks should not include full_command or full_output."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_db.session.get.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.state.value = "processing"
        mock_task.instruction = "Fix auth"
        mock_task.completion_summary = None
        mock_task.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_task.completed_at = None
        mock_task.full_command = "Please fix the auth module"
        mock_task.full_output = "Done fixing the auth module"

        # Mock query chain for tasks
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_task]
        mock_query.group_by.return_value = mock_query

        response = client.get("/api/agents/1/tasks")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        task_data = data[0]

        # These fields must NOT be present
        assert "full_command" not in task_data
        assert "full_output" not in task_data

        # These fields should be present
        assert "id" in task_data
        assert "state" in task_data
        assert "instruction" in task_data


class TestCardStateExcludesFullText:
    """Task 3.6: Verify SSE card_refresh events do NOT include full text fields."""

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_card_state_excludes_full_text(self, mock_config):
        """build_card_state() should not include full_command or full_output."""
        from claude_headspace.services.card_state import build_card_state

        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.state = MagicMock()
        mock_task.state.value = "processing"
        mock_task.instruction = "Fix auth"
        mock_task.completion_summary = None
        mock_task.turns = []
        mock_task.full_command = "Full command text here"
        mock_task.full_output = "Full output text here"

        agent = MagicMock()
        agent.id = 42
        agent.session_uuid = "test-uuid"
        agent.state = MagicMock()
        agent.state.value = "processing"
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.started_at = datetime.now(timezone.utc)
        agent.ended_at = None
        agent.priority_score = None
        agent.priority_reason = None
        agent.project_id = 10
        agent.project = MagicMock()
        agent.project.name = "test-project"
        agent.project.slug = "test-project"
        agent.get_current_task.return_value = mock_task
        agent.tasks = [mock_task]

        result = build_card_state(agent)

        # card_state should NOT include full text fields
        assert "full_command" not in result
        assert "full_output" not in result

        # But should include current_task_id for drill-down
        assert "current_task_id" in result
        assert result["current_task_id"] == 1
