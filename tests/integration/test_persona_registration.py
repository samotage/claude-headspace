"""Integration tests for persona registration.

Uses real PostgreSQL test database with per-test rollback isolation.
Tests the full flow: service function → DB records → filesystem assets.

Note: These tests use the db_session from conftest (raw SQLAlchemy session)
for verification queries, but register_persona uses Flask-SQLAlchemy's
db.session internally. We need the Flask app context to make both work.
"""

import pytest

from claude_headspace.models.persona import Persona
from claude_headspace.models.role import Role
from claude_headspace.services.persona_registration import (
    RegistrationError,
    register_persona,
)
from claude_headspace.services.persona_assets import check_assets


@pytest.fixture
def app_db_session(app):
    """Provide Flask app context with clean database for registration tests.

    Uses Flask-SQLAlchemy's db.session which is what register_persona uses.
    Creates tables before each test and drops them after.
    """
    from claude_headspace.database import db

    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()


class TestPersonaRegistrationIntegration:
    """End-to-end persona registration tests with real DB."""

    def test_full_registration_flow(self, app, app_db_session, tmp_path):
        """Register a persona and verify DB records + filesystem."""
        result = register_persona(
            name="Con",
            role_name="developer",
            description="Backend Python dev",
            project_root=tmp_path,
        )

        # Verify DB: Role
        role = Role.query.filter_by(name="developer").one()
        assert role.name == "developer"

        # Verify DB: Persona
        persona = Persona.query.filter_by(id=result.id).one()
        assert persona.name == "Con"
        assert persona.slug == result.slug
        assert persona.description == "Backend Python dev"
        assert persona.status == "active"
        assert persona.role_id == role.id

        # Verify filesystem
        status = check_assets(result.slug, project_root=tmp_path)
        assert status.directory_exists is True
        assert status.skill_exists is True
        assert status.experience_exists is True

    def test_role_reuse_across_registrations(self, app, app_db_session, tmp_path):
        """Multiple personas with the same role share one Role record."""
        r1 = register_persona(name="Con", role_name="developer", project_root=tmp_path)
        r2 = register_persona(name="Rob", role_name="developer", project_root=tmp_path)

        p1 = Persona.query.filter_by(id=r1.id).one()
        p2 = Persona.query.filter_by(id=r2.id).one()

        assert p1.role_id == p2.role_id
        assert Role.query.count() == 1

    def test_different_roles_create_separate_records(self, app, app_db_session, tmp_path):
        """Different role names create separate Role records."""
        register_persona(name="Con", role_name="developer", project_root=tmp_path)
        register_persona(name="Vern", role_name="tester", project_root=tmp_path)

        assert Role.query.count() == 2

    def test_case_insensitive_role_matching(self, app, app_db_session, tmp_path):
        """Role matching is case-insensitive."""
        r1 = register_persona(name="Con", role_name="developer", project_root=tmp_path)
        r2 = register_persona(name="Rob", role_name="DEVELOPER", project_root=tmp_path)

        p1 = Persona.query.filter_by(id=r1.id).one()
        p2 = Persona.query.filter_by(id=r2.id).one()

        assert p1.role_id == p2.role_id

    def test_duplicate_generates_unique_slugs(self, app, app_db_session, tmp_path):
        """Same name + role registered twice produces unique slugs."""
        r1 = register_persona(name="Con", role_name="developer", project_root=tmp_path)
        r2 = register_persona(name="Con", role_name="developer", project_root=tmp_path)

        assert r1.slug != r2.slug
        # Both have their own filesystem directories
        assert check_assets(r1.slug, project_root=tmp_path).directory_exists
        assert check_assets(r2.slug, project_root=tmp_path).directory_exists

    def test_validation_prevents_db_creation(self, app, app_db_session, tmp_path):
        """Validation failures create no DB records."""
        with pytest.raises(RegistrationError):
            register_persona(name="", role_name="developer", project_root=tmp_path)

        assert Persona.query.count() == 0
        assert Role.query.count() == 0

    def test_slug_format(self, app, app_db_session, tmp_path):
        """Slug follows {role}-{name}-{id} format, all lowercase."""
        result = register_persona(
            name="Con", role_name="Developer", project_root=tmp_path
        )

        persona = Persona.query.filter_by(id=result.id).one()
        expected = f"developer-con-{persona.id}"
        assert persona.slug == expected
        assert result.slug == expected
