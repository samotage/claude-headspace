"""Integration tests for key routes with a real database.

TST-M6: Exercises routes against real PostgreSQL instead of mocked DB.
Covers: projects CRUD, agent dismiss, project settings.
"""

import uuid
from datetime import datetime, timezone

import pytest

from claude_headspace.models import Agent, Project

from .factories import AgentFactory, ProjectFactory


@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    """Inject the test db_session into all factories."""
    ProjectFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session


# ---------------------------------------------------------------------------
# Helper: Flask test app wired to the integration DB session
# ---------------------------------------------------------------------------

@pytest.fixture
def int_app(test_db_engine):
    """Create a Flask app that uses the integration test database."""
    from pathlib import Path
    from claude_headspace.app import create_app

    project_root = Path(__file__).parent.parent.parent
    app = create_app(config_path=str(project_root / "config.yaml"), testing=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = str(test_db_engine.url)

    return app


@pytest.fixture
def int_client(int_app):
    return int_app.test_client()


# ===========================================================================
# Projects CRUD
# ===========================================================================

class TestProjectsCRUDIntegration:

    def test_list_projects_empty(self, int_client, int_app):
        """GET /api/projects returns empty list when no projects exist."""
        with int_app.app_context():
            response = int_client.get("/api/projects")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_create_project(self, int_client, int_app):
        """POST /api/projects creates a project in the real DB."""
        with int_app.app_context():
            response = int_client.post("/api/projects", json={
                "name": "integration-test-project",
                "path": "/Users/test/integration-test-project",
            })
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "integration-test-project"
        assert data["id"] is not None

    def test_create_and_get_project(self, int_client, int_app):
        """Create then retrieve a project."""
        with int_app.app_context():
            create_resp = int_client.post("/api/projects", json={
                "name": "get-test-proj",
                "path": "/Users/test/get-test-proj",
            })
            assert create_resp.status_code == 201
            proj_id = create_resp.get_json()["id"]

            get_resp = int_client.get(f"/api/projects/{proj_id}")
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert data["name"] == "get-test-proj"

    def test_update_project(self, int_client, int_app):
        """PUT /api/projects/<id> updates project fields."""
        with int_app.app_context():
            create_resp = int_client.post("/api/projects", json={
                "name": "update-me",
                "path": "/Users/test/update-me",
            })
            proj_id = create_resp.get_json()["id"]

            update_resp = int_client.put(f"/api/projects/{proj_id}", json={
                "description": "Updated description",
            })
        assert update_resp.status_code == 200

    def test_delete_project(self, int_client, int_app):
        """DELETE /api/projects/<id> removes the project."""
        with int_app.app_context():
            create_resp = int_client.post("/api/projects", json={
                "name": "delete-me",
                "path": "/Users/test/delete-me",
            })
            proj_id = create_resp.get_json()["id"]

            del_resp = int_client.delete(f"/api/projects/{proj_id}")
        assert del_resp.status_code == 200
        data = del_resp.get_json()
        assert data["deleted"] is True

    def test_delete_nonexistent_project_returns_404(self, int_client, int_app):
        """DELETE non-existent project returns 404."""
        with int_app.app_context():
            response = int_client.delete("/api/projects/99999")
        assert response.status_code == 404

    def test_create_duplicate_path_returns_409(self, int_client, int_app):
        """POST with duplicate path returns 409."""
        with int_app.app_context():
            int_client.post("/api/projects", json={
                "name": "first",
                "path": "/Users/test/dup-path",
            })
            response = int_client.post("/api/projects", json={
                "name": "second",
                "path": "/Users/test/dup-path",
            })
        assert response.status_code == 409

    def test_create_missing_fields_returns_400(self, int_client, int_app):
        """POST with missing required fields returns 400."""
        with int_app.app_context():
            response = int_client.post("/api/projects", json={"name": "no-path"})
        assert response.status_code == 400


# ===========================================================================
# Agent dismiss
# ===========================================================================

class TestAgentDismissIntegration:

    def test_dismiss_agent(self, int_client, int_app):
        """POST /api/agents/<id>/dismiss marks an agent as ended."""
        with int_app.app_context():
            from claude_headspace.database import db as flask_db

            # Create project + agent
            create_resp = int_client.post("/api/projects", json={
                "name": "dismiss-proj",
                "path": "/Users/test/dismiss-proj",
            })
            proj_id = create_resp.get_json()["id"]

            agent = Agent(
                session_uuid=uuid.uuid4(),
                claude_session_id="dismiss-session",
                project_id=proj_id,
                started_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
            )
            flask_db.session.add(agent)
            flask_db.session.commit()
            agent_id = agent.id

            response = int_client.post(f"/api/agents/{agent_id}/dismiss")

        assert response.status_code == 200


# ===========================================================================
# Project settings
# ===========================================================================

class TestProjectSettingsIntegration:

    def test_pause_and_resume_inference(self, int_client, int_app):
        """PUT /api/projects/<id>/settings toggles inference_paused."""
        with int_app.app_context():
            create_resp = int_client.post("/api/projects", json={
                "name": "settings-proj",
                "path": "/Users/test/settings-proj",
            })
            proj_id = create_resp.get_json()["id"]

            # Pause
            pause_resp = int_client.put(f"/api/projects/{proj_id}/settings", json={
                "inference_paused": True,
                "inference_paused_reason": "Testing pause",
            })
            assert pause_resp.status_code == 200
            pause_data = pause_resp.get_json()
            assert pause_data["inference_paused"] is True

            # Resume
            resume_resp = int_client.put(f"/api/projects/{proj_id}/settings", json={
                "inference_paused": False,
            })
            assert resume_resp.status_code == 200
            resume_data = resume_resp.get_json()
            assert resume_data["inference_paused"] is False
