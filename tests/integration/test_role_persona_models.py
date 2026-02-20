"""Integration tests for Role and Persona models.

Verifies real Postgres constraints and behavior:
- Role creation with unique name constraint
- Persona creation with slug generation
- Slug uniqueness enforcement
- Bidirectional relationships
- Status field defaults
- Foreign key constraints
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from claude_headspace.models import Role, Persona


class TestRoleModel:
    """Task 3.1: Test Role model creation, fields, and defaults."""

    def test_create_role(self, db_session):
        """A Role can be created with a unique name and description."""
        role = Role(name="developer", description="Backend Python development")
        db_session.add(role)
        db_session.flush()

        assert role.id is not None
        assert role.name == "developer"
        assert role.description == "Backend Python development"
        assert role.created_at is not None
        assert role.created_at.tzinfo is not None  # timezone-aware

    def test_role_created_at_default(self, db_session):
        """Role.created_at defaults to current UTC time."""
        before = datetime.now(timezone.utc)
        role = Role(name="tester")
        db_session.add(role)
        db_session.flush()
        after = datetime.now(timezone.utc)

        assert before <= role.created_at <= after

    def test_role_description_nullable(self, db_session):
        """Role.description is nullable."""
        role = Role(name="pm")
        db_session.add(role)
        db_session.flush()

        assert role.description is None

    def test_role_repr(self, db_session):
        """Role has a meaningful __repr__."""
        role = Role(name="architect")
        db_session.add(role)
        db_session.flush()

        assert "architect" in repr(role)
        assert str(role.id) in repr(role)


class TestPersonaModel:
    """Task 3.2: Test Persona model creation and slug generation."""

    def test_create_persona_with_slug_generation(self, db_session):
        """Persona slug is generated as {role_name}-{persona_name}-{id}."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Con", role=role)
        db_session.add(persona)
        db_session.flush()

        assert persona.id is not None
        assert persona.slug == f"developer-con-{persona.id}"
        assert persona.name == "Con"
        assert persona.role_id == role.id

    def test_slug_is_lowercase(self, db_session):
        """Slug components are lowercased."""
        role = Role(name="Developer")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="CON", role=role)
        db_session.add(persona)
        db_session.flush()

        assert persona.slug == f"developer-con-{persona.id}"

    def test_persona_created_at_default(self, db_session):
        """Persona.created_at defaults to current UTC time."""
        role = Role(name="tester")
        db_session.add(role)
        db_session.flush()

        before = datetime.now(timezone.utc)
        persona = Persona(name="Verner", role=role)
        db_session.add(persona)
        db_session.flush()
        after = datetime.now(timezone.utc)

        assert before <= persona.created_at <= after

    def test_persona_description_nullable(self, db_session):
        """Persona.description is nullable."""
        role = Role(name="pm")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Gavin", role=role)
        db_session.add(persona)
        db_session.flush()

        assert persona.description is None

    def test_persona_with_description(self, db_session):
        """Persona can be created with a description."""
        role = Role(name="architect")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Robbo", role=role, description="System architect persona")
        db_session.add(persona)
        db_session.flush()

        assert persona.description == "System architect persona"

    def test_generate_slug_method(self, db_session):
        """The generate_slug method returns the correct format."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Con", role=role)
        db_session.add(persona)
        db_session.flush()

        assert persona.generate_slug() == f"developer-con-{persona.id}"


class TestSlugUniqueness:
    """Task 3.3: Test slug uniqueness via id component."""

    def test_duplicate_names_different_slugs(self, db_session):
        """Two personas with same name and role get different slugs via id."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        persona1 = Persona(name="Con", role=role)
        db_session.add(persona1)
        db_session.flush()

        persona2 = Persona(name="Con", role=role)
        db_session.add(persona2)
        db_session.flush()

        assert persona1.slug != persona2.slug
        assert persona1.slug == f"developer-con-{persona1.id}"
        assert persona2.slug == f"developer-con-{persona2.id}"


class TestBidirectionalRelationships:
    """Task 3.4: Test Role.personas and Persona.role relationships."""

    def test_role_personas_returns_list(self, db_session):
        """Role.personas returns a list of associated Persona objects."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        persona1 = Persona(name="Con", role=role)
        persona2 = Persona(name="Dev", role=role)
        db_session.add_all([persona1, persona2])
        db_session.flush()

        assert len(role.personas) == 2
        assert persona1 in role.personas
        assert persona2 in role.personas

    def test_persona_role_returns_role(self, db_session):
        """Persona.role returns the associated Role object."""
        role = Role(name="tester")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Verner", role=role)
        db_session.add(persona)
        db_session.flush()

        assert persona.role is role
        assert persona.role.name == "tester"

    def test_role_with_no_personas(self, db_session):
        """Role.personas returns empty list when no personas assigned."""
        role = Role(name="pm")
        db_session.add(role)
        db_session.flush()

        assert role.personas == []


class TestStatusField:
    """Task 3.5: Test status field defaults and values."""

    def test_status_defaults_to_active(self, db_session):
        """Persona.status defaults to 'active'."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Con", role=role)
        db_session.add(persona)
        db_session.flush()

        assert persona.status == "active"

    def test_status_accepts_archived(self, db_session):
        """Persona.status accepts 'archived'."""
        role = Role(name="tester")
        db_session.add(role)
        db_session.flush()

        persona = Persona(name="Verner", role=role, status="archived")
        db_session.add(persona)
        db_session.flush()

        assert persona.status == "archived"


class TestConstraints:
    """Task 3.7: Test database constraints."""

    def test_role_name_unique_constraint(self, db_session):
        """Role.name has a unique constraint at database level."""
        role1 = Role(name="developer")
        db_session.add(role1)
        db_session.flush()

        with pytest.raises(IntegrityError):
            role2 = Role(name="developer")
            db_session.add(role2)
            db_session.flush()

    def test_persona_slug_unique_constraint(self, db_session):
        """Persona.slug has a unique constraint at database level."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        # Insert first row with a specific slug via raw SQL (bypasses after_insert event)
        db_session.execute(text(
            "INSERT INTO personas (slug, name, status, role_id, created_at) "
            "VALUES ('duplicate-slug', 'First', 'active', :role_id, NOW())"
        ), {"role_id": role.id})
        db_session.flush()

        # Attempt to insert second row with the same slug — should raise IntegrityError
        with pytest.raises(IntegrityError):
            db_session.execute(text(
                "INSERT INTO personas (slug, name, status, role_id, created_at) "
                "VALUES ('duplicate-slug', 'Second', 'active', :role_id, NOW())"
            ), {"role_id": role.id})
            db_session.flush()

    def test_persona_role_id_not_null(self, db_session):
        """Persona.role_id cannot be null."""
        with pytest.raises(IntegrityError):
            persona = Persona(name="Orphan", role_id=None, slug="orphan-slug")
            db_session.add(persona)
            db_session.flush()

    def test_persona_name_not_null(self, db_session):
        """Persona.name cannot be null."""
        role = Role(name="developer")
        db_session.add(role)
        db_session.flush()

        with pytest.raises(IntegrityError):
            persona = Persona(name=None, role=role, slug="test-slug")
            db_session.add(persona)
            db_session.flush()

    def test_role_name_not_null(self, db_session):
        """Role.name cannot be null."""
        with pytest.raises(IntegrityError):
            role = Role(name=None)
            db_session.add(role)
            db_session.flush()

    def test_persona_foreign_key_integrity(self, db_session):
        """Persona.role_id must reference an existing Role."""
        with pytest.raises(IntegrityError):
            persona = Persona(name="Ghost", role_id=99999, slug="ghost-slug")
            db_session.add(persona)
            db_session.flush()
