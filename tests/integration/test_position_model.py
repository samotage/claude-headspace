"""Integration tests for Position model.

Verifies real Postgres constraints and behavior:
- Position creation with field defaults
- Self-referential reporting hierarchy (reports_to, direct_reports)
- Self-referential escalation path (escalates_to differs from reports_to)
- FK relationships to Organisation and Role
- Backref relationships (Organisation.positions, Role.positions)
- Not-null constraints on title, org_id, role_id
- Top-level positions with NULL reports_to and escalates_to
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from claude_headspace.models import Organisation, Position, Role


@pytest.fixture
def dev_org(db_session):
    """Create a test Organisation."""
    org = Organisation(name="Development", status="active")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def dev_role(db_session):
    """Create a test Role."""
    role = Role(name="developer")
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def architect_role(db_session):
    """Create an architect Role."""
    role = Role(name="architect")
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def pm_role(db_session):
    """Create a PM Role."""
    role = Role(name="pm")
    db_session.add(role)
    db_session.flush()
    return role


class TestPositionModel:
    """Task 3.1: Test Position model creation, fields, and defaults."""

    def test_create_position(self, db_session, dev_org, dev_role):
        """A Position can be created with org_id, role_id, and title."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Lead Developer")
        db_session.add(pos)
        db_session.flush()

        assert pos.id is not None
        assert pos.org_id == dev_org.id
        assert pos.role_id == dev_role.id
        assert pos.title == "Lead Developer"
        assert pos.level == 0
        assert pos.is_cross_cutting is False
        assert pos.created_at is not None
        assert pos.created_at.tzinfo is not None

    def test_level_default(self, db_session, dev_org, dev_role):
        """Position.level defaults to 0."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Default Level")
        db_session.add(pos)
        db_session.flush()

        assert pos.level == 0

    def test_level_custom(self, db_session, dev_org, dev_role):
        """Position.level accepts custom integer values."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Deep Position", level=3)
        db_session.add(pos)
        db_session.flush()

        assert pos.level == 3

    def test_is_cross_cutting_default(self, db_session, dev_org, dev_role):
        """Position.is_cross_cutting defaults to False."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Normal Position")
        db_session.add(pos)
        db_session.flush()

        assert pos.is_cross_cutting is False

    def test_is_cross_cutting_true(self, db_session, dev_org, dev_role):
        """Position.is_cross_cutting can be set to True."""
        pos = Position(
            org_id=dev_org.id, role_id=dev_role.id,
            title="Cross-Cutting Position", is_cross_cutting=True
        )
        db_session.add(pos)
        db_session.flush()

        assert pos.is_cross_cutting is True

    def test_created_at_default(self, db_session, dev_org, dev_role):
        """Position.created_at defaults to current UTC time."""
        before = datetime.now(timezone.utc)
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Timestamp Test")
        db_session.add(pos)
        db_session.flush()
        after = datetime.now(timezone.utc)

        assert before <= pos.created_at <= after

    def test_repr(self, db_session, dev_org, dev_role):
        """Position has a meaningful __repr__."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Repr Test")
        db_session.add(pos)
        db_session.flush()

        assert "Repr Test" in repr(pos)
        assert str(pos.id) in repr(pos)


class TestReportingHierarchy:
    """Task 3.2: Test self-referential reporting hierarchy."""

    def test_reports_to_relationship(self, db_session, dev_org, architect_role, dev_role):
        """A position can report to another position."""
        parent = Position(org_id=dev_org.id, role_id=architect_role.id, title="Lead Architect")
        db_session.add(parent)
        db_session.flush()

        child = Position(
            org_id=dev_org.id, role_id=dev_role.id,
            title="Senior Developer", reports_to_id=parent.id, level=1
        )
        db_session.add(child)
        db_session.flush()

        assert child.reports_to is not None
        assert child.reports_to.id == parent.id
        assert child.reports_to.title == "Lead Architect"

    def test_direct_reports_relationship(self, db_session, dev_org, architect_role, dev_role):
        """A position's direct_reports returns all positions reporting to it."""
        parent = Position(org_id=dev_org.id, role_id=architect_role.id, title="Lead Architect")
        db_session.add(parent)
        db_session.flush()

        child1 = Position(
            org_id=dev_org.id, role_id=dev_role.id,
            title="Dev 1", reports_to_id=parent.id, level=1
        )
        child2 = Position(
            org_id=dev_org.id, role_id=dev_role.id,
            title="Dev 2", reports_to_id=parent.id, level=1
        )
        db_session.add_all([child1, child2])
        db_session.flush()

        assert len(parent.direct_reports) == 2
        titles = {r.title for r in parent.direct_reports}
        assert titles == {"Dev 1", "Dev 2"}


class TestEscalationPath:
    """Task 3.3: Test self-referential escalation path."""

    def test_escalation_differs_from_reporting(self, db_session, dev_org, architect_role, pm_role, dev_role):
        """Escalation path can differ from reporting path."""
        architect = Position(org_id=dev_org.id, role_id=architect_role.id, title="Lead Architect")
        pm = Position(org_id=dev_org.id, role_id=pm_role.id, title="PM")
        db_session.add_all([architect, pm])
        db_session.flush()

        dev = Position(
            org_id=dev_org.id, role_id=dev_role.id,
            title="Senior Developer",
            reports_to_id=pm.id,
            escalates_to_id=architect.id,
            level=1
        )
        db_session.add(dev)
        db_session.flush()

        assert dev.reports_to.title == "PM"
        assert dev.escalates_to.title == "Lead Architect"
        assert dev.reports_to_id != dev.escalates_to_id

    def test_escalation_same_as_reporting(self, db_session, dev_org, architect_role, dev_role):
        """Escalation can point to the same position as reporting."""
        parent = Position(org_id=dev_org.id, role_id=architect_role.id, title="Lead Architect")
        db_session.add(parent)
        db_session.flush()

        child = Position(
            org_id=dev_org.id, role_id=dev_role.id,
            title="Developer",
            reports_to_id=parent.id,
            escalates_to_id=parent.id,
            level=1
        )
        db_session.add(child)
        db_session.flush()

        assert child.reports_to_id == child.escalates_to_id


class TestForeignKeyRelationships:
    """Task 3.4: Test Position.role and Position.organisation relationships."""

    def test_position_role_relationship(self, db_session, dev_org, dev_role):
        """Position.role returns the associated Role object."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Developer")
        db_session.add(pos)
        db_session.flush()

        assert pos.role is not None
        assert pos.role.id == dev_role.id
        assert pos.role.name == "developer"

    def test_position_organisation_relationship(self, db_session, dev_org, dev_role):
        """Position.organisation returns the associated Organisation object."""
        pos = Position(org_id=dev_org.id, role_id=dev_role.id, title="Developer")
        db_session.add(pos)
        db_session.flush()

        assert pos.organisation is not None
        assert pos.organisation.id == dev_org.id
        assert pos.organisation.name == "Development"


class TestBackrefRelationships:
    """Task 3.5: Test Organisation.positions and Role.positions backref relationships."""

    def test_organisation_positions(self, db_session, dev_org, dev_role, architect_role):
        """Organisation.positions returns all positions in that org."""
        pos1 = Position(org_id=dev_org.id, role_id=dev_role.id, title="Dev 1")
        pos2 = Position(org_id=dev_org.id, role_id=architect_role.id, title="Architect 1")
        db_session.add_all([pos1, pos2])
        db_session.flush()

        assert len(dev_org.positions) == 2
        titles = {p.title for p in dev_org.positions}
        assert titles == {"Dev 1", "Architect 1"}

    def test_role_positions(self, db_session, dev_org, dev_role):
        """Role.positions returns all positions requiring that role."""
        pos1 = Position(org_id=dev_org.id, role_id=dev_role.id, title="Dev 1")
        pos2 = Position(org_id=dev_org.id, role_id=dev_role.id, title="Dev 2")
        db_session.add_all([pos1, pos2])
        db_session.flush()

        assert len(dev_role.positions) == 2
        titles = {p.title for p in dev_role.positions}
        assert titles == {"Dev 1", "Dev 2"}


class TestConstraints:
    """Task 3.6: Test not-null constraints on title, org_id, role_id."""

    def test_title_not_null(self, db_session, dev_org, dev_role):
        """Position.title cannot be null."""
        with pytest.raises(IntegrityError):
            pos = Position(org_id=dev_org.id, role_id=dev_role.id, title=None)
            db_session.add(pos)
            db_session.flush()

    def test_org_id_not_null(self, db_session, dev_role):
        """Position.org_id cannot be null."""
        with pytest.raises(IntegrityError):
            pos = Position(org_id=None, role_id=dev_role.id, title="No Org")
            db_session.add(pos)
            db_session.flush()

    def test_role_id_not_null(self, db_session, dev_org):
        """Position.role_id cannot be null."""
        with pytest.raises(IntegrityError):
            pos = Position(org_id=dev_org.id, role_id=None, title="No Role")
            db_session.add(pos)
            db_session.flush()


class TestTopLevelPositions:
    """Task 3.7: Test top-level positions with NULL reports_to and escalates_to."""

    def test_top_level_reports_to_null(self, db_session, dev_org, architect_role):
        """Top-level positions have reports_to_id=NULL."""
        pos = Position(org_id=dev_org.id, role_id=architect_role.id, title="Lead Architect")
        db_session.add(pos)
        db_session.flush()

        assert pos.reports_to_id is None
        assert pos.reports_to is None

    def test_top_level_escalates_to_null(self, db_session, dev_org, architect_role):
        """Top-level positions have escalates_to_id=NULL."""
        pos = Position(org_id=dev_org.id, role_id=architect_role.id, title="Lead Architect")
        db_session.add(pos)
        db_session.flush()

        assert pos.escalates_to_id is None
        assert pos.escalates_to is None

    def test_top_level_no_direct_reports(self, db_session, dev_org, architect_role):
        """A position with no children has empty direct_reports."""
        pos = Position(org_id=dev_org.id, role_id=architect_role.id, title="Solo Architect")
        db_session.add(pos)
        db_session.flush()

        assert pos.direct_reports == []
