"""Route tests for persona management endpoints."""

from unittest.mock import patch

import pytest

from claude_headspace.database import db
from claude_headspace.models.persona import Persona
from claude_headspace.models.role import Role
from claude_headspace.services.persona_assets import AssetStatus


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


def _create_persona(session, name="Con", role=None, description=None, status="active"):
    """Helper to create a persona with a role."""
    if role is None:
        role = _create_role(session)
    persona = Persona(name=name, role_id=role.id, role=role, description=description, status=status)
    session.add(persona)
    session.flush()  # Triggers after_insert for slug
    return persona


# ── Existing: POST /api/personas/register ──


class TestApiRegisterPersona:
    """Test POST /api/personas/register."""

    def test_success_returns_201(self, client, db_session):
        """Successful registration returns 201 with slug, id, path."""
        response = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert "slug" in data
        assert "id" in data
        assert "path" in data
        # Slug format: {role}-{name}-{id}
        assert data["slug"].startswith("developer-con-")

    def test_with_description(self, client, db_session):
        """Registration with description succeeds."""
        response = client.post(
            "/api/personas/register",
            json={
                "name": "Con",
                "role": "developer",
                "description": "Backend Python developer",
            },
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["slug"].startswith("developer-con-")

    def test_missing_name_returns_400(self, client, db_session):
        """Missing name returns 400 with error message."""
        response = client.post(
            "/api/personas/register",
            json={"role": "developer"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_empty_name_returns_400(self, client, db_session):
        """Empty name returns 400."""
        response = client.post(
            "/api/personas/register",
            json={"name": "", "role": "developer"},
        )

        assert response.status_code == 400

    def test_missing_role_returns_400(self, client, db_session):
        """Missing role returns 400."""
        response = client.post(
            "/api/personas/register",
            json={"name": "Con"},
        )

        assert response.status_code == 400

    def test_empty_body_returns_400(self, client, db_session):
        """Empty JSON body returns 400."""
        response = client.post(
            "/api/personas/register",
            json={},
        )

        assert response.status_code == 400

    def test_duplicate_creates_unique(self, client, db_session):
        """Calling twice with same data creates two personas with different slugs."""
        r1 = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )
        r2 = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.get_json()["slug"] != r2.get_json()["slug"]

    def test_json_response_format(self, client, db_session):
        """Response JSON has exactly the expected keys."""
        response = client.post(
            "/api/personas/register",
            json={"name": "Con", "role": "developer"},
        )

        data = response.get_json()
        assert set(data.keys()) == {"slug", "id", "path"}
        assert isinstance(data["slug"], str)
        assert isinstance(data["id"], int)
        assert isinstance(data["path"], str)


# ── Existing: GET /api/personas/<slug>/validate ──


class TestApiValidatePersona:
    """Test GET /api/personas/<slug>/validate."""

    def test_valid_active_persona(self, client, db_session):
        """Returns 200 for active persona."""
        persona = _create_persona(db_session)
        db_session.commit()

        response = client.get(f"/api/personas/{persona.slug}/validate")
        assert response.status_code == 200
        data = response.get_json()
        assert data["valid"] is True
        assert data["slug"] == persona.slug

    def test_not_found_returns_404(self, client, db_session):
        """Returns 404 for missing persona."""
        response = client.get("/api/personas/nonexistent/validate")
        assert response.status_code == 404
        data = response.get_json()
        assert data["valid"] is False

    def test_archived_persona_returns_404(self, client, db_session):
        """Returns 404 for archived persona (not active)."""
        persona = _create_persona(db_session, status="archived")
        db_session.commit()

        response = client.get(f"/api/personas/{persona.slug}/validate")
        assert response.status_code == 404


# ── NEW: GET /personas (page route) ──


class TestPersonasPage:
    """Test GET /personas page route."""

    def test_page_returns_200(self, client, db_session):
        """Personas page returns 200."""
        response = client.get("/personas")
        assert response.status_code == 200


# ── NEW: GET /api/personas (list) ──


class TestApiListPersonas:
    """Test GET /api/personas."""

    def test_empty_list(self, client, db_session):
        """Returns empty list when no personas exist."""
        response = client.get("/api/personas")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_returns_persona_list(self, client, db_session):
        """Returns list of personas with correct fields."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role)
        _create_persona(db_session, name="Robbo", role=role, description="Tester")
        db_session.commit()

        response = client.get("/api/personas")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2

        # Check fields
        p = data[0]  # Most recent first (ordered by created_at desc)
        assert "id" in p
        assert "slug" in p
        assert "name" in p
        assert "role" in p
        assert "status" in p
        assert "agent_count" in p
        assert "created_at" in p

    def test_includes_role_name(self, client, db_session):
        """Role name is included in persona data."""
        role = _create_role(db_session, "architect")
        _create_persona(db_session, name="Verner", role=role)
        db_session.commit()

        response = client.get("/api/personas")
        data = response.get_json()
        assert data[0]["role"] == "architect"

    def test_agent_count_is_zero_for_new_persona(self, client, db_session):
        """New persona with no agents has agent_count 0."""
        _create_persona(db_session)
        db_session.commit()

        response = client.get("/api/personas")
        data = response.get_json()
        assert data[0]["agent_count"] == 0


# ── NEW: GET /api/personas/<slug> (detail) ──


class TestApiGetPersona:
    """Test GET /api/personas/<slug>."""

    def test_returns_persona_detail(self, client, db_session):
        """Returns persona detail by slug."""
        role = _create_role(db_session, "developer")
        persona = _create_persona(db_session, name="Con", role=role, description="Backend dev")
        db_session.commit()

        response = client.get(f"/api/personas/{persona.slug}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Con"
        assert data["role"] == "developer"
        assert data["description"] == "Backend dev"
        assert data["status"] == "active"
        assert data["agent_count"] == 0

    def test_not_found_returns_404(self, client, db_session):
        """Returns 404 for non-existent slug."""
        response = client.get("/api/personas/nonexistent-slug")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


# ── NEW: PUT /api/personas/<slug> (update) ──


class TestApiUpdatePersona:
    """Test PUT /api/personas/<slug>."""

    def test_update_name(self, client, db_session):
        """Updates persona name."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            json={"name": "Connor"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Connor"

    def test_update_description(self, client, db_session):
        """Updates persona description."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            json={"description": "A great developer"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["description"] == "A great developer"

    def test_update_status_to_archived(self, client, db_session):
        """Updates persona status to archived."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            json={"status": "archived"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "archived"

    def test_update_status_to_active(self, client, db_session):
        """Updates persona status back to active."""
        persona = _create_persona(db_session, name="Con", status="archived")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            json={"status": "active"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "active"

    def test_empty_name_returns_400(self, client, db_session):
        """Empty name returns 400."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            json={"name": ""},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_invalid_status_returns_400(self, client, db_session):
        """Invalid status returns 400."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            json={"status": "deleted"},
        )
        assert response.status_code == 400

    def test_not_found_returns_404(self, client, db_session):
        """Returns 404 for non-existent slug."""
        response = client.put(
            "/api/personas/nonexistent-slug",
            json={"name": "Foo"},
        )
        assert response.status_code == 404

    def test_no_body_returns_400(self, client, db_session):
        """No request body returns 400."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}",
            content_type="application/json",
        )
        assert response.status_code == 400


# ── NEW: DELETE /api/personas/<slug> ──


class TestApiDeletePersona:
    """Test DELETE /api/personas/<slug>."""

    def test_delete_success(self, client, db_session):
        """Deletes persona with no linked agents."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()
        slug = persona.slug

        response = client.delete(f"/api/personas/{slug}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["deleted"] is True
        assert data["name"] == "Con"

    def test_delete_not_found_returns_404(self, client, db_session):
        """Returns 404 for non-existent slug."""
        response = client.delete("/api/personas/nonexistent-slug")
        assert response.status_code == 404

    def test_delete_blocked_when_agents_linked(self, client, db_session):
        """Returns 409 when persona has linked agents."""
        import uuid

        from claude_headspace.models.agent import Agent
        from claude_headspace.models.project import Project

        role = _create_role(db_session, "developer")
        persona = _create_persona(db_session, name="Con", role=role)

        # Create a project and agent linked to the persona
        project = Project(name="TestProject", slug="test-project", path="/tmp/test")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            project_id=project.id,
            persona_id=persona.id,
            session_uuid=uuid.uuid4(),
        )
        db_session.add(agent)
        db_session.commit()

        response = client.delete(f"/api/personas/{persona.slug}")
        assert response.status_code == 409
        data = response.get_json()
        assert "error" in data
        assert "agents" in data
        assert len(data["agents"]) == 1


# ── NEW: GET /api/roles ──


class TestApiListRoles:
    """Test GET /api/roles."""

    def test_empty_list(self, client, db_session):
        """Returns empty list when no roles exist."""
        response = client.get("/api/roles")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_returns_role_list(self, client, db_session):
        """Returns list of roles with correct fields."""
        _create_role(db_session, "developer")
        _create_role(db_session, "tester")
        db_session.commit()

        response = client.get("/api/roles")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2

        r = data[0]
        assert "id" in r
        assert "name" in r
        assert "description" in r
        assert "created_at" in r

    def test_roles_ordered_by_name(self, client, db_session):
        """Roles are ordered alphabetically by name."""
        _create_role(db_session, "tester")
        _create_role(db_session, "architect")
        _create_role(db_session, "developer")
        db_session.commit()

        response = client.get("/api/roles")
        data = response.get_json()
        names = [r["name"] for r in data]
        assert names == ["architect", "developer", "tester"]


# ── NEW (e8-s16): GET /personas/<slug> (detail page) ──


class TestPersonaDetailPage:
    """Test GET /personas/<slug> detail page route."""

    def test_valid_slug_returns_200(self, client, db_session):
        """Detail page returns 200 for a valid persona slug."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.get(f"/personas/{persona.slug}")
        assert response.status_code == 200

    def test_invalid_slug_returns_404(self, client, db_session):
        """Detail page returns 404 for non-existent slug."""
        response = client.get("/personas/nonexistent-slug-123")
        assert response.status_code == 404


# ── NEW (e8-s16): GET /api/personas/<slug>/skill ──


class TestApiPersonaSkillRead:
    """Test GET /api/personas/<slug>/skill."""

    @patch("claude_headspace.routes.personas.read_skill_file")
    def test_skill_read_success(self, mock_read, client, db_session):
        """Returns content and exists=true when skill file exists."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        mock_read.return_value = "# Skill Content"

        response = client.get(f"/api/personas/{persona.slug}/skill")
        assert response.status_code == 200
        data = response.get_json()
        assert data["content"] == "# Skill Content"
        assert data["exists"] is True

    @patch("claude_headspace.routes.personas.read_skill_file")
    def test_skill_read_not_found(self, mock_read, client, db_session):
        """Returns exists=false when skill file is missing."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        mock_read.return_value = None

        response = client.get(f"/api/personas/{persona.slug}/skill")
        assert response.status_code == 200
        data = response.get_json()
        assert data["content"] == ""
        assert data["exists"] is False

    def test_skill_read_persona_not_found(self, client, db_session):
        """Returns 404 for non-existent persona."""
        response = client.get("/api/personas/nonexistent/skill")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


# ── NEW (e8-s16): PUT /api/personas/<slug>/skill ──


class TestApiPersonaSkillWrite:
    """Test PUT /api/personas/<slug>/skill."""

    @patch("claude_headspace.routes.personas.write_skill_file")
    def test_skill_write_success(self, mock_write, client, db_session):
        """Writes content and returns saved=true."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}/skill",
            json={"content": "# Updated Skill"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["saved"] is True
        mock_write.assert_called_once_with(persona.slug, "# Updated Skill")

    def test_skill_write_no_body(self, client, db_session):
        """Returns 400 when content field is missing."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.put(
            f"/api/personas/{persona.slug}/skill",
            json={},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_skill_write_persona_not_found(self, client, db_session):
        """Returns 404 for non-existent persona."""
        response = client.put(
            "/api/personas/nonexistent/skill",
            json={"content": "# Test"},
        )
        assert response.status_code == 404


# ── NEW (e8-s16): GET /api/personas/<slug>/experience ──


class TestApiPersonaExperienceRead:
    """Test GET /api/personas/<slug>/experience."""

    @patch("claude_headspace.routes.personas.get_experience_mtime")
    @patch("claude_headspace.routes.personas.read_experience_file")
    def test_experience_read_success(self, mock_read, mock_mtime, client, db_session):
        """Returns content, exists, and last_modified."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        mock_read.return_value = "# Experience Log"
        mock_mtime.return_value = "2026-02-23T10:00:00+00:00"

        response = client.get(f"/api/personas/{persona.slug}/experience")
        assert response.status_code == 200
        data = response.get_json()
        assert data["content"] == "# Experience Log"
        assert data["exists"] is True
        assert data["last_modified"] == "2026-02-23T10:00:00+00:00"

    @patch("claude_headspace.routes.personas.get_experience_mtime")
    @patch("claude_headspace.routes.personas.read_experience_file")
    def test_experience_read_empty(self, mock_read, mock_mtime, client, db_session):
        """Returns exists=false when experience file is missing."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        mock_read.return_value = None
        mock_mtime.return_value = None

        response = client.get(f"/api/personas/{persona.slug}/experience")
        assert response.status_code == 200
        data = response.get_json()
        assert data["content"] == ""
        assert data["exists"] is False
        assert data["last_modified"] is None

    def test_experience_read_persona_not_found(self, client, db_session):
        """Returns 404 for non-existent persona."""
        response = client.get("/api/personas/nonexistent/experience")
        assert response.status_code == 404


# ── NEW (e8-s16): GET /api/personas/<slug>/assets ──


class TestApiPersonaAssets:
    """Test GET /api/personas/<slug>/assets."""

    @patch("claude_headspace.routes.personas.check_assets")
    def test_asset_status(self, mock_check, client, db_session):
        """Reports correct file existence."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        mock_check.return_value = AssetStatus(
            skill_exists=True,
            experience_exists=False,
            directory_exists=True,
        )

        response = client.get(f"/api/personas/{persona.slug}/assets")
        assert response.status_code == 200
        data = response.get_json()
        assert data["skill_exists"] is True
        assert data["experience_exists"] is False
        assert data["directory_exists"] is True

    def test_asset_status_persona_not_found(self, client, db_session):
        """Returns 404 for non-existent persona."""
        response = client.get("/api/personas/nonexistent/assets")
        assert response.status_code == 404


# ── NEW (e8-s16): GET /api/personas/<slug>/agents ──


class TestApiPersonaLinkedAgents:
    """Test GET /api/personas/<slug>/agents."""

    def test_linked_agents_with_agents(self, client, db_session):
        """Returns agent details with project name, state, last_seen."""
        import uuid

        from claude_headspace.models.agent import Agent
        from claude_headspace.models.project import Project

        role = _create_role(db_session, "developer")
        persona = _create_persona(db_session, name="Con", role=role)

        project = Project(name="TestProject", slug="test-project", path="/tmp/test")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            project_id=project.id,
            persona_id=persona.id,
            session_uuid=uuid.uuid4(),
        )
        db_session.add(agent)
        db_session.commit()

        response = client.get(f"/api/personas/{persona.slug}/agents")
        assert response.status_code == 200
        data = response.get_json()
        agents = data["agents"]
        assert len(agents) == 1
        assert agents[0]["project_name"] == "TestProject"
        assert "session_uuid" in agents[0]
        assert "state" in agents[0]
        assert "last_seen_at" in agents[0]
        assert data["active_agent_count"] == 1

    def test_linked_agents_excludes_ended_by_default(self, client, db_session):
        """Active-only by default; include_ended=true returns all."""
        import uuid
        from datetime import datetime, timezone

        from claude_headspace.models.agent import Agent
        from claude_headspace.models.project import Project

        role = _create_role(db_session, "developer")
        persona = _create_persona(db_session, name="Con", role=role)

        project = Project(name="TestProject", slug="test-project", path="/tmp/test")
        db_session.add(project)
        db_session.flush()

        # Active agent
        active = Agent(
            project_id=project.id,
            persona_id=persona.id,
            session_uuid=uuid.uuid4(),
        )
        # Ended agent
        ended = Agent(
            project_id=project.id,
            persona_id=persona.id,
            session_uuid=uuid.uuid4(),
            ended_at=datetime.now(timezone.utc),
        )
        db_session.add_all([active, ended])
        db_session.commit()

        # Default: only active
        resp = client.get(f"/api/personas/{persona.slug}/agents")
        data = resp.get_json()
        assert len(data["agents"]) == 1
        assert data["active_agent_count"] == 1

        # include_ended=true: both
        resp2 = client.get(f"/api/personas/{persona.slug}/agents?include_ended=true")
        data2 = resp2.get_json()
        assert len(data2["agents"]) == 2
        assert data2["active_agent_count"] == 1
        # Ended agent should have state overridden
        ended_agents = [a for a in data2["agents"] if a["ended_at"] is not None]
        assert len(ended_agents) == 1
        assert ended_agents[0]["state"] == "ended"

    def test_linked_agents_empty(self, client, db_session):
        """Returns empty array when no agents are linked."""
        persona = _create_persona(db_session, name="Con")
        db_session.commit()

        response = client.get(f"/api/personas/{persona.slug}/agents")
        assert response.status_code == 200
        data = response.get_json()
        assert data["agents"] == []
        assert data["active_agent_count"] == 0

    def test_linked_agents_persona_not_found(self, client, db_session):
        """Returns 404 for non-existent persona."""
        response = client.get("/api/personas/nonexistent/agents")
        assert response.status_code == 404
