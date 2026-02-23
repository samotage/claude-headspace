"""Unit tests for persona registration service.

Tests the register_persona() service function with a Flask app context
and test database. No CLI or HTTP involvement.
"""

import pytest

from claude_headspace.database import db
from claude_headspace.models.persona import Persona
from claude_headspace.models.role import Role
from claude_headspace.services.persona_registration import (
    RegistrationError,
    RegistrationResult,
    register_persona,
)


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


class TestRegisterPersona:
    """Test the register_persona service function."""

    def test_creates_role_and_persona(self, app, db_session, tmp_path):
        """Successful registration creates both Role and Persona records."""
        result = register_persona(
            name="Con", role_name="developer", project_root=tmp_path
        )

        assert isinstance(result, RegistrationResult)
        assert result.slug.startswith("developer-con-")
        assert isinstance(result.id, int) and result.id > 0
        assert f"developer-con-{result.id}" == result.slug
        assert result.slug in result.path

    def test_creates_filesystem_assets(self, app, db_session, tmp_path):
        """Registration creates directory and template files on disk."""
        result = register_persona(
            name="Con", role_name="developer", project_root=tmp_path
        )

        persona_dir = tmp_path / "data" / "personas" / result.slug
        assert persona_dir.is_dir()
        assert (persona_dir / "skill.md").exists()
        assert (persona_dir / "experience.md").exists()

    def test_reuses_existing_role(self, app, db_session, tmp_path):
        """If role already exists, it is reused (not duplicated)."""
        register_persona(name="Con", role_name="developer", project_root=tmp_path)
        register_persona(name="Rob", role_name="developer", project_root=tmp_path)

        roles = Role.query.filter_by(name="developer").all()
        assert len(roles) == 1

    def test_case_insensitive_role_lookup(self, app, db_session, tmp_path):
        """Role lookup is case-insensitive (input lowercased)."""
        register_persona(name="Con", role_name="developer", project_root=tmp_path)
        result = register_persona(
            name="Rob", role_name="Developer", project_root=tmp_path
        )

        roles = Role.query.all()
        assert len(roles) == 1
        assert roles[0].name == "developer"
        assert "developer-rob" in result.slug

    def test_role_name_stored_lowercase(self, app, db_session, tmp_path):
        """Role name is always stored in lowercase."""
        register_persona(name="Con", role_name="TESTER", project_root=tmp_path)

        role = Role.query.first()
        assert role.name == "tester"

    def test_persona_name_preserves_case(self, app, db_session, tmp_path):
        """Persona name preserves original case in DB."""
        register_persona(name="Con", role_name="developer", project_root=tmp_path)

        persona = Persona.query.first()
        assert persona.name == "Con"

    def test_slug_is_lowercase(self, app, db_session, tmp_path):
        """Generated slug is fully lowercase."""
        result = register_persona(
            name="Con", role_name="Developer", project_root=tmp_path
        )

        assert result.slug == result.slug.lower()

    def test_description_optional(self, app, db_session, tmp_path):
        """Registration works without a description."""
        result = register_persona(
            name="Con", role_name="developer", project_root=tmp_path
        )

        persona = Persona.query.get(result.id)
        assert persona.description is None

    def test_description_stored(self, app, db_session, tmp_path):
        """Description is stored when provided."""
        result = register_persona(
            name="Con",
            role_name="developer",
            description="Backend Python developer",
            project_root=tmp_path,
        )

        persona = Persona.query.get(result.id)
        assert persona.description == "Backend Python developer"

    def test_status_set_to_active(self, app, db_session, tmp_path):
        """Newly created persona has status 'active'."""
        result = register_persona(
            name="Con", role_name="developer", project_root=tmp_path
        )

        persona = Persona.query.get(result.id)
        assert persona.status == "active"

    def test_duplicate_name_role_creates_unique_slugs(self, app, db_session, tmp_path):
        """Duplicate name+role creates new persona with unique slug."""
        r1 = register_persona(name="Con", role_name="developer", project_root=tmp_path)
        r2 = register_persona(name="Con", role_name="developer", project_root=tmp_path)

        assert r1.slug != r2.slug
        assert r1.id != r2.id
        assert Persona.query.count() == 2

    def test_empty_name_raises_error(self, app, db_session, tmp_path):
        """Empty name raises RegistrationError."""
        with pytest.raises(RegistrationError, match="name is required"):
            register_persona(name="", role_name="developer", project_root=tmp_path)

        assert Persona.query.count() == 0
        assert Role.query.count() == 0

    def test_none_name_raises_error(self, app, db_session, tmp_path):
        """None name raises RegistrationError."""
        with pytest.raises(RegistrationError, match="name is required"):
            register_persona(name=None, role_name="developer", project_root=tmp_path)

    def test_empty_role_raises_error(self, app, db_session, tmp_path):
        """Empty role raises RegistrationError."""
        with pytest.raises(RegistrationError, match="Role name is required"):
            register_persona(name="Con", role_name="", project_root=tmp_path)

        assert Persona.query.count() == 0

    def test_none_role_raises_error(self, app, db_session, tmp_path):
        """None role raises RegistrationError."""
        with pytest.raises(RegistrationError, match="Role name is required"):
            register_persona(name="Con", role_name=None, project_root=tmp_path)

    def test_whitespace_only_name_raises_error(self, app, db_session, tmp_path):
        """Whitespace-only name raises RegistrationError."""
        with pytest.raises(RegistrationError, match="name is required"):
            register_persona(name="   ", role_name="developer", project_root=tmp_path)

    def test_whitespace_only_role_raises_error(self, app, db_session, tmp_path):
        """Whitespace-only role raises RegistrationError."""
        with pytest.raises(RegistrationError, match="Role name is required"):
            register_persona(name="Con", role_name="  ", project_root=tmp_path)

    def test_name_stripped(self, app, db_session, tmp_path):
        """Leading/trailing whitespace is stripped from name."""
        result = register_persona(
            name="  Con  ", role_name="developer", project_root=tmp_path
        )

        persona = Persona.query.get(result.id)
        assert persona.name == "Con"

    def test_role_stripped_and_lowered(self, app, db_session, tmp_path):
        """Leading/trailing whitespace is stripped and role is lowercased."""
        register_persona(
            name="Con", role_name="  Developer  ", project_root=tmp_path
        )

        role = Role.query.first()
        assert role.name == "developer"

    def test_partial_failure_filesystem(self, app, db_session, tmp_path, monkeypatch):
        """If filesystem creation fails, error includes persona ID."""
        def failing_create(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(
            "claude_headspace.services.persona_registration.create_persona_assets",
            failing_create,
        )

        with pytest.raises(RegistrationError, match="filesystem creation failed"):
            register_persona(
                name="Con", role_name="developer", project_root=tmp_path
            )

        # DB record should still exist (not rolled back)
        assert Persona.query.count() == 1
