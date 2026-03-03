"""Unit tests for PersonaType model, can_create_channel, and get_operator.

Tests the PersonaType lookup table model, the persona_type_id FK on Persona,
the can_create_channel property, the get_operator() classmethod, and
relationship wiring between Persona and PersonaType.
"""

import pytest

from claude_headspace.database import db
from claude_headspace.models.persona import Persona
from claude_headspace.models.persona_type import PersonaType
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


@pytest.fixture
def seed_persona_types(db_session):
    """Ensure the 4 PersonaType rows exist (may already be seeded by conftest).

    The conftest._seed_persona_types autouse fixture handles initial seeding.
    This fixture verifies the rows exist and returns them for test assertions.
    """
    existing = PersonaType.query.count()
    if existing == 0:
        types = [
            PersonaType(id=1, type_key="agent", subtype="internal"),
            PersonaType(id=2, type_key="agent", subtype="external"),
            PersonaType(id=3, type_key="person", subtype="internal"),
            PersonaType(id=4, type_key="person", subtype="external"),
        ]
        for pt in types:
            db.session.add(pt)
        db.session.flush()
    return PersonaType.query.order_by(PersonaType.id).all()


@pytest.fixture
def developer_role(db_session):
    """Create a developer role."""
    role = Role(name="developer")
    db.session.add(role)
    db.session.flush()
    return role


@pytest.fixture
def operator_role(db_session):
    """Create an operator role."""
    role = Role(name="operator", description="System operator")
    db.session.add(role)
    db.session.flush()
    return role


class TestPersonaTypeModel:
    """Test PersonaType model creation and constraints (Task 3.1)."""

    def test_create_persona_type(self, app, db_session):
        """PersonaType can be created with type_key and subtype."""
        # Use a novel combination to avoid conflict with seeded lookup rows
        pt = PersonaType(type_key="test", subtype="custom")
        db.session.add(pt)
        db.session.flush()

        assert pt.id is not None
        assert pt.type_key == "test"
        assert pt.subtype == "custom"

    def test_seed_data_four_rows(self, app, seed_persona_types):
        """Seed data creates exactly 4 rows."""
        count = PersonaType.query.count()
        assert count == 4

    def test_seed_data_correct_values(self, app, seed_persona_types):
        """Seed data has correct type_key/subtype combinations."""
        ai = db.session.get(PersonaType, 1)
        ae = db.session.get(PersonaType, 2)
        pi = db.session.get(PersonaType, 3)
        pe = db.session.get(PersonaType, 4)

        assert ai.type_key == "agent" and ai.subtype == "internal"
        assert ae.type_key == "agent" and ae.subtype == "external"
        assert pi.type_key == "person" and pi.subtype == "internal"
        assert pe.type_key == "person" and pe.subtype == "external"

    def test_unique_constraint_prevents_duplicates(self, app, seed_persona_types):
        """Unique constraint on (type_key, subtype) prevents duplicate quadrants."""
        duplicate = PersonaType(type_key="agent", subtype="internal")
        db.session.add(duplicate)

        with pytest.raises(Exception):  # IntegrityError wrapped by SA
            db.session.flush()

    def test_repr(self, app, seed_persona_types):
        """PersonaType __repr__ includes key fields."""
        pt = db.session.get(PersonaType, 1)
        repr_str = repr(pt)
        assert "PersonaType" in repr_str
        assert "agent" in repr_str
        assert "internal" in repr_str


class TestPersonaFKAndBackfill:
    """Test Persona FK and default value (Task 3.2)."""

    def test_new_persona_defaults_to_agent_internal(self, app, seed_persona_types, developer_role):
        """New personas default to persona_type_id=1 (agent/internal)."""
        persona = Persona(name="Con", role=developer_role)
        db.session.add(persona)
        db.session.flush()

        assert persona.persona_type_id == 1

    def test_persona_type_id_column_is_not_nullable(self, app, db_session):
        """persona_type_id column is defined as NOT NULL in the model."""
        col = Persona.__table__.columns["persona_type_id"]
        assert col.nullable is False

    def test_explicit_persona_type_id(self, app, seed_persona_types, operator_role):
        """Explicit persona_type_id is respected (e.g., person/internal)."""
        persona = Persona(
            name="Sam",
            role=operator_role,
            persona_type_id=3,
        )
        db.session.add(persona)
        db.session.flush()

        assert persona.persona_type_id == 3


class TestCanCreateChannel:
    """Test can_create_channel property for all 4 quadrants (Task 3.3)."""

    def test_agent_internal_can_create(self, app, seed_persona_types, developer_role):
        """agent/internal persona can create channels."""
        persona = Persona(name="Con", role=developer_role, persona_type_id=1)
        db.session.add(persona)
        db.session.flush()

        assert persona.can_create_channel is True

    def test_person_internal_can_create(self, app, seed_persona_types, operator_role):
        """person/internal (operator) can create channels."""
        persona = Persona(name="Sam", role=operator_role, persona_type_id=3)
        db.session.add(persona)
        db.session.flush()

        assert persona.can_create_channel is True

    def test_agent_external_cannot_create(self, app, seed_persona_types, developer_role):
        """agent/external persona cannot create channels."""
        persona = Persona(name="Ext", role=developer_role, persona_type_id=2)
        db.session.add(persona)
        db.session.flush()

        assert persona.can_create_channel is False

    def test_person_external_cannot_create(self, app, seed_persona_types, operator_role):
        """person/external persona cannot create channels."""
        persona = Persona(name="Guest", role=operator_role, persona_type_id=4)
        db.session.add(persona)
        db.session.flush()

        assert persona.can_create_channel is False

    def test_no_persona_type_returns_false(self, app, db_session):
        """If persona_type is None, can_create_channel returns False."""
        # Test the guard clause by mocking the property return
        # Use a simple object with persona_type = None
        class FakePersona:
            can_create_channel = Persona.can_create_channel
            persona_type = None

        fake = FakePersona()
        assert fake.can_create_channel is False


class TestGetOperator:
    """Test Persona.get_operator() classmethod (Task 3.4)."""

    def test_returns_operator_persona(self, app, seed_persona_types, operator_role):
        """get_operator() returns the person/internal Persona."""
        persona = Persona(
            name="Sam",
            role=operator_role,
            persona_type_id=3,
        )
        db.session.add(persona)
        db.session.flush()

        result = Persona.get_operator()
        assert result is not None
        assert result.name == "Sam"
        assert result.persona_type.type_key == "person"
        assert result.persona_type.subtype == "internal"

    def test_returns_none_when_no_operator(self, app, seed_persona_types, developer_role):
        """get_operator() returns None when no person/internal Persona exists."""
        # Create only agent/internal personas
        persona = Persona(name="Con", role=developer_role, persona_type_id=1)
        db.session.add(persona)
        db.session.flush()

        result = Persona.get_operator()
        assert result is None

    def test_returns_none_with_empty_db(self, app, seed_persona_types):
        """get_operator() returns None when no personas exist at all."""
        result = Persona.get_operator()
        assert result is None


class TestRelationshipWiring:
    """Test relationship wiring between Persona and PersonaType (Task 3.5)."""

    def test_persona_to_persona_type(self, app, seed_persona_types, developer_role):
        """persona.persona_type loads the associated PersonaType."""
        persona = Persona(name="Con", role=developer_role, persona_type_id=1)
        db.session.add(persona)
        db.session.flush()

        assert persona.persona_type is not None
        assert persona.persona_type.type_key == "agent"
        assert persona.persona_type.subtype == "internal"

    def test_persona_type_to_personas(self, app, seed_persona_types, developer_role):
        """persona_type.personas loads associated Persona records."""
        p1 = Persona(name="Con", role=developer_role, persona_type_id=1)
        p2 = Persona(name="Rob", role=developer_role, persona_type_id=1)
        db.session.add_all([p1, p2])
        db.session.flush()

        agent_internal = db.session.get(PersonaType, 1)
        assert len(agent_internal.personas) == 2
        names = {p.name for p in agent_internal.personas}
        assert names == {"Con", "Rob"}

    def test_empty_persona_type_has_no_personas(self, app, seed_persona_types):
        """PersonaType with no associated personas returns empty list."""
        person_external = db.session.get(PersonaType, 4)
        assert person_external.personas == []


class TestOperatorPersona:
    """Test operator Persona creation patterns (Task 3.6)."""

    def test_operator_persona_attributes(self, app, seed_persona_types, operator_role):
        """Operator persona has correct attributes."""
        persona = Persona(
            name="Sam",
            role=operator_role,
            persona_type_id=3,
            description="System operator",
            status="active",
        )
        db.session.add(persona)
        db.session.flush()

        assert persona.name == "Sam"
        assert persona.status == "active"
        assert persona.persona_type_id == 3
        assert persona.persona_type.type_key == "person"
        assert persona.persona_type.subtype == "internal"
        assert persona.role.name == "operator"

    def test_operator_slug_format(self, app, seed_persona_types, operator_role):
        """Operator persona slug follows {role}-{name}-{id} format."""
        persona = Persona(
            name="Sam",
            role=operator_role,
            persona_type_id=3,
        )
        db.session.add(persona)
        db.session.flush()

        expected_slug = f"operator-sam-{persona.id}"
        assert persona.slug == expected_slug


class TestExistingPersonaFlows:
    """Test that existing persona flows are not broken (Task 3.7)."""

    def test_registration_defaults_to_agent_internal(self, app, seed_persona_types, tmp_path):
        """PersonaRegistration creates agent/internal personas by default."""
        from claude_headspace.services.persona_registration import register_persona

        result = register_persona(
            name="Con",
            role_name="developer",
            project_root=tmp_path,
        )

        persona = Persona.query.filter_by(id=result.id).one()
        assert persona.persona_type_id == 1
        assert persona.persona_type.type_key == "agent"
        assert persona.persona_type.subtype == "internal"

    def test_multiple_registrations_all_agent_internal(self, app, seed_persona_types, tmp_path):
        """Multiple registrations all default to agent/internal."""
        from claude_headspace.services.persona_registration import register_persona

        r1 = register_persona(name="Con", role_name="developer", project_root=tmp_path)
        r2 = register_persona(name="Rob", role_name="tester", project_root=tmp_path)

        p1 = Persona.query.filter_by(id=r1.id).one()
        p2 = Persona.query.filter_by(id=r2.id).one()

        assert p1.persona_type_id == 1
        assert p2.persona_type_id == 1


class TestModelImport:
    """Test PersonaType is importable from models package (Task 3.7 / 4.4)."""

    def test_importable_from_models(self):
        """PersonaType is importable from claude_headspace.models."""
        from claude_headspace.models import PersonaType as PT
        assert PT is PersonaType

    def test_in_all(self):
        """PersonaType is listed in __all__."""
        from claude_headspace.models import __all__
        assert "PersonaType" in __all__
