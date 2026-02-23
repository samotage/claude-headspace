"""Route tests for persona management endpoints."""

import pytest

from claude_headspace.database import db
from claude_headspace.models.persona import Persona
from claude_headspace.models.role import Role


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
