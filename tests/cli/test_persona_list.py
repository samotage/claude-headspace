"""Tests for the flask persona list CLI command."""

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


class TestPersonaListCommand:
    """Tests for flask persona list command."""

    def test_list_all_personas(self, runner, db_session):
        """Lists all personas in formatted table."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role)
        _create_persona(db_session, name="Robbo", role=role, status="archived")
        db_session.commit()

        result = runner.invoke(args=["persona", "list"])

        assert result.exit_code == 0
        assert "Con" in result.output
        assert "Robbo" in result.output
        assert "developer" in result.output
        # Header row
        assert "Name" in result.output
        assert "Role" in result.output
        assert "Slug" in result.output
        assert "Status" in result.output
        assert "Agents" in result.output

    def test_list_active_only(self, runner, db_session):
        """--active flag filters to active personas only."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role, status="active")
        _create_persona(db_session, name="Robbo", role=role, status="archived")
        db_session.commit()

        result = runner.invoke(args=["persona", "list", "--active"])

        assert result.exit_code == 0
        assert "Con" in result.output
        assert "Robbo" not in result.output

    def test_list_by_role(self, runner, db_session):
        """--role flag filters by role name."""
        dev_role = _create_role(db_session, "developer")
        qa_role = _create_role(db_session, "qa")
        _create_persona(db_session, name="Con", role=dev_role)
        _create_persona(db_session, name="Tester", role=qa_role)
        db_session.commit()

        result = runner.invoke(args=["persona", "list", "--role", "qa"])

        assert result.exit_code == 0
        assert "Tester" in result.output
        assert "Con" not in result.output

    def test_list_empty(self, runner, db_session):
        """No personas shows a friendly message."""
        result = runner.invoke(args=["persona", "list"])

        assert result.exit_code == 0
        assert "No personas found" in result.output

    def test_sorted_by_role_then_name(self, runner, db_session):
        """Output is sorted alphabetically by role, then by name."""
        dev_role = _create_role(db_session, "developer")
        qa_role = _create_role(db_session, "qa")
        _create_persona(db_session, name="Zara", role=dev_role)
        _create_persona(db_session, name="Alice", role=dev_role)
        _create_persona(db_session, name="Bob", role=qa_role)
        db_session.commit()

        result = runner.invoke(args=["persona", "list"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        # Skip header (2 lines: header + separator), exclude summary line (last)
        data_lines = [l for l in lines[2:] if l.strip() and not l.strip()[0].isdigit()]
        names = [line.split()[0] for line in data_lines]
        assert names == ["Alice", "Zara", "Bob"]

    def test_role_filter_case_insensitive(self, runner, db_session):
        """--role filter is case-insensitive."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role)
        db_session.commit()

        result = runner.invoke(args=["persona", "list", "--role", "Developer"])

        assert result.exit_code == 0
        assert "Con" in result.output

    def test_summary_line(self, runner, db_session):
        """Summary line shows total with active/archived breakdown."""
        role = _create_role(db_session, "developer")
        _create_persona(db_session, name="Con", role=role, status="active")
        _create_persona(db_session, name="Robbo", role=role, status="active")
        _create_persona(db_session, name="Old", role=role, status="archived")
        db_session.commit()

        result = runner.invoke(args=["persona", "list"])

        assert result.exit_code == 0
        assert "3 personas (2 active, 1 archived)" in result.output
