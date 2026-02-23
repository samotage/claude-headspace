"""Route tests for POST /api/agents with persona_slug parameter."""

from unittest.mock import patch

import pytest

from claude_headspace.database import db
from claude_headspace.models.persona import Persona
from claude_headspace.models.role import Role
from claude_headspace.services.agent_lifecycle import CreateResult


@pytest.fixture
def db_session(app):
    """Provide a database session with rollback isolation."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


def _create_role(session, name="developer"):
    """Helper to create a role."""
    role = Role(name=name)
    session.add(role)
    session.flush()
    return role


def _create_persona(session, name="Con", role=None, status="active"):
    """Helper to create a persona with a role."""
    if role is None:
        role = _create_role(session)
    persona = Persona(name=name, role_id=role.id, role=role, status=status)
    session.add(persona)
    session.flush()
    return persona


class TestCreateAgentWithPersona:
    """Test POST /api/agents with persona_slug parameter."""

    @patch("claude_headspace.routes.agents.create_agent")
    def test_with_valid_persona_slug(self, mock_create, client, db_session):
        """Persona slug is passed through to create_agent service."""
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent started",
            tmux_session_name="hs-test-abc123",
        )

        response = client.post(
            "/api/agents",
            json={"project_id": 1, "persona_slug": "developer-con-1"},
        )

        assert response.status_code == 201
        mock_create.assert_called_once_with(1, persona_slug="developer-con-1")

    @patch("claude_headspace.routes.agents.create_agent")
    def test_without_persona_slug(self, mock_create, client, db_session):
        """No persona_slug passes None to create_agent (backward compat)."""
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent started",
            tmux_session_name="hs-test-abc123",
        )

        response = client.post(
            "/api/agents",
            json={"project_id": 1},
        )

        assert response.status_code == 201
        mock_create.assert_called_once_with(1, persona_slug=None)

    @patch("claude_headspace.routes.agents.create_agent")
    def test_with_invalid_persona_slug(self, mock_create, client, db_session):
        """Invalid persona_slug returns 422 from create_agent."""
        mock_create.return_value = CreateResult(
            success=False,
            message="Persona 'nonexistent' not found or not active.",
        )

        response = client.post(
            "/api/agents",
            json={"project_id": 1, "persona_slug": "nonexistent"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data
        assert "nonexistent" in data["error"]

    def test_missing_project_id_returns_400(self, client, db_session):
        """Missing project_id returns 400 regardless of persona_slug."""
        response = client.post(
            "/api/agents",
            json={"persona_slug": "developer-con-1"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "project_id is required"

    @patch("claude_headspace.routes.agents.create_agent")
    def test_persona_slug_null_treated_as_none(self, mock_create, client, db_session):
        """Explicit null persona_slug is treated as None."""
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent started",
            tmux_session_name="hs-test-abc123",
        )

        response = client.post(
            "/api/agents",
            json={"project_id": 1, "persona_slug": None},
        )

        assert response.status_code == 201
        mock_create.assert_called_once_with(1, persona_slug=None)
