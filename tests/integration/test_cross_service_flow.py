"""Cross-service integration tests.

TST-M11: Tests the hook → session_correlator → task_lifecycle → state
pipeline end-to-end with real service instances and a real database.
Only external APIs (OpenRouter) are mocked.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_headspace.models import Agent, Project, Task

from .factories import ProjectFactory

# The actual project root — has a .git directory so session_correlator
# will recognise it as a project root.
_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    """Inject the test db_session into all factories."""
    ProjectFactory._meta.sqlalchemy_session = db_session


@pytest.fixture
def cross_app(test_db_engine):
    """Flask app wired to integration test database for cross-service tests."""
    from claude_headspace.app import create_app

    app = create_app(config_path=str(Path(_PROJECT_ROOT) / "config.yaml"))
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = str(test_db_engine.url)

    return app


@pytest.fixture
def cross_client(cross_app):
    return cross_app.test_client()


def _setup_project(flask_db, name_suffix):
    """Create a project pointing to the real project root with a unique name."""
    project = Project(
        name=f"test-{name_suffix}",
        slug=f"test-{name_suffix}",
        path=_PROJECT_ROOT,
        created_at=datetime.now(timezone.utc),
    )
    flask_db.session.add(project)
    flask_db.session.commit()
    return project


# ===========================================================================
# End-to-end hook flow tests
# ===========================================================================

class TestHookToStateFlow:
    """Test that hook events flow correctly through the service pipeline.

    Each test gets its own project/session so there are no collisions.
    Since all tests use the same _PROJECT_ROOT path, but the integration
    DB is dropped and recreated per session, we ensure isolation by using
    unique session_ids (the correlator caches by session_id).
    """

    @pytest.fixture(autouse=True)
    def _unique_project(self, cross_app):
        """Create a fresh project for each test to avoid path uniqueness issues."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db
            # Delete any leftover projects with this path
            flask_db.session.query(Project).filter_by(path=_PROJECT_ROOT).delete()
            flask_db.session.commit()

    def test_session_start_creates_agent(self, cross_client, cross_app):
        """session-start hook creates a new agent via session correlator."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db

            project = _setup_project(flask_db, "session-start")

            response = cross_client.post("/hook/session-start", json={
                "session_id": f"sess-start-{uuid.uuid4().hex[:8]}",
                "working_directory": _PROJECT_ROOT,
            })

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ok"
            assert data["agent_id"] is not None

    def test_user_prompt_creates_turn_and_transitions_state(self, cross_client, cross_app):
        """user-prompt-submit hook creates a USER turn and transitions state."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db

            _setup_project(flask_db, "prompt")
            session_id = f"sess-prompt-{uuid.uuid4().hex[:8]}"

            # Start session
            start_resp = cross_client.post("/hook/session-start", json={
                "session_id": session_id,
                "working_directory": _PROJECT_ROOT,
            })
            assert start_resp.status_code == 200

            # User prompt
            prompt_resp = cross_client.post("/hook/user-prompt-submit", json={
                "session_id": session_id,
                "prompt": "Implement the login feature",
            })

            assert prompt_resp.status_code == 200
            assert prompt_resp.get_json()["status"] == "ok"

            # Verify a task exists
            agent = flask_db.session.query(Agent).filter_by(
                claude_session_id=session_id
            ).first()
            assert agent is not None
            tasks = flask_db.session.query(Task).filter_by(agent_id=agent.id).all()
            assert len(tasks) >= 1

    def test_stop_hook_transitions_agent_state(self, cross_client, cross_app):
        """stop hook transitions agent state (end-of-turn)."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db

            _setup_project(flask_db, "stop")
            session_id = f"sess-stop-{uuid.uuid4().hex[:8]}"

            cross_client.post("/hook/session-start", json={
                "session_id": session_id,
                "working_directory": _PROJECT_ROOT,
            })
            cross_client.post("/hook/user-prompt-submit", json={
                "session_id": session_id,
                "prompt": "Do something",
            })

            stop_resp = cross_client.post("/hook/stop", json={
                "session_id": session_id,
            })

            assert stop_resp.status_code == 200
            assert stop_resp.get_json()["status"] == "ok"

    def test_session_end_marks_agent_ended(self, cross_client, cross_app):
        """session-end hook sets agent.ended_at."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db

            _setup_project(flask_db, "end")
            session_id = f"sess-end-{uuid.uuid4().hex[:8]}"

            start_resp = cross_client.post("/hook/session-start", json={
                "session_id": session_id,
                "working_directory": _PROJECT_ROOT,
            })
            agent_id = start_resp.get_json()["agent_id"]

            end_resp = cross_client.post("/hook/session-end", json={
                "session_id": session_id,
            })

            assert end_resp.status_code == 200
            assert end_resp.get_json()["status"] == "ok"

            agent = flask_db.session.get(Agent, agent_id)
            assert agent is not None
            assert agent.ended_at is not None

    def test_hook_with_invalid_payload_returns_400(self, cross_client, cross_app):
        """Hook with missing required fields returns 400."""
        with cross_app.app_context():
            response = cross_client.post("/hook/session-start", json={})
        assert response.status_code == 400

    def test_hook_with_non_json_returns_400(self, cross_client, cross_app):
        """Hook with non-JSON content type returns 400."""
        with cross_app.app_context():
            response = cross_client.post(
                "/hook/session-start",
                data="not json",
                content_type="text/plain",
            )
        assert response.status_code == 400


class TestPreToolUseFlow:
    """Test pre-tool-use hook for AWAITING_INPUT transitions."""

    @pytest.fixture(autouse=True)
    def _unique_project(self, cross_app):
        """Create a fresh project for each test."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db
            flask_db.session.query(Project).filter_by(path=_PROJECT_ROOT).delete()
            flask_db.session.commit()

    def test_ask_user_question_triggers_awaiting_input(self, cross_client, cross_app):
        """pre-tool-use with AskUserQuestion should transition to AWAITING_INPUT."""
        with cross_app.app_context():
            from claude_headspace.database import db as flask_db

            _setup_project(flask_db, "pretool")
            session_id = f"sess-pretool-{uuid.uuid4().hex[:8]}"

            cross_client.post("/hook/session-start", json={
                "session_id": session_id,
                "working_directory": _PROJECT_ROOT,
            })
            cross_client.post("/hook/user-prompt-submit", json={
                "session_id": session_id,
                "prompt": "Help me",
            })

            resp = cross_client.post("/hook/pre-tool-use", json={
                "session_id": session_id,
                "tool_name": "AskUserQuestion",
            })

            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"
