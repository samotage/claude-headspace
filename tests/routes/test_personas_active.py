"""Route tests for GET /api/personas/active endpoint."""

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
    persona = Persona(
        name=name, role_id=role.id, role=role,
        description=description, status=status,
    )
    session.add(persona)
    session.flush()
    return persona


class TestApiListActivePersonas:
    """Test GET /api/personas/active."""

    def test_returns_active_personas(self, client, db_session):
        """Returns only active personas."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role, status="active")
        _create_persona(db_session, name="Archived", role=role, status="archived")
        db_session.commit()

        response = client.get("/api/personas/active")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 1
        assert data[0]["name"] == "Con"
        assert data[0]["role"] == "developer"

    def test_excludes_archived_personas(self, client, db_session):
        """Archived personas are excluded from results."""
        role = _create_role(db_session, "tester")
        _create_persona(db_session, name="Old", role=role, status="archived")
        db_session.commit()

        response = client.get("/api/personas/active")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 0

    def test_empty_list_when_no_personas(self, client, db_session):
        """Returns empty array when no personas exist."""
        response = client.get("/api/personas/active")
        assert response.status_code == 200
        data = response.get_json()

        assert data == []

    def test_grouped_by_role_sorted_alphabetically(self, client, db_session):
        """Personas are sorted by role name, then by persona name."""
        dev_role = _create_role(db_session, "developer")
        qa_role = _create_role(db_session, "qa")

        _create_persona(db_session, name="Zara", role=dev_role)
        _create_persona(db_session, name="Alice", role=dev_role)
        _create_persona(db_session, name="Bob", role=qa_role)
        db_session.commit()

        response = client.get("/api/personas/active")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 3
        # developer comes before qa alphabetically
        assert data[0]["name"] == "Alice"
        assert data[0]["role"] == "developer"
        assert data[1]["name"] == "Zara"
        assert data[1]["role"] == "developer"
        assert data[2]["name"] == "Bob"
        assert data[2]["role"] == "qa"

    def test_includes_description(self, client, db_session):
        """Persona description is included in response."""
        role = _create_role(db_session, "developer")
        _create_persona(
            db_session, name="Con", role=role,
            description="Backend Python developer",
        )
        db_session.commit()

        response = client.get("/api/personas/active")
        data = response.get_json()

        assert data[0]["description"] == "Backend Python developer"

    def test_response_fields(self, client, db_session):
        """Response includes expected fields for each persona."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role)
        db_session.commit()

        response = client.get("/api/personas/active")
        data = response.get_json()

        assert len(data) == 1
        persona = data[0]
        assert set(persona.keys()) == {"id", "slug", "name", "role", "description"}
