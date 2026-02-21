"""Integration tests for Agent model extensions (persona, position, predecessor).

Verifies real Postgres constraints and behavior:
- Agent.persona_id FK to personas table
- Agent.position_id FK to positions table
- Agent.previous_agent_id self-referential FK to agents table
- Agent.persona, Agent.position, Agent.previous_agent relationships
- Agent.successor_agents reverse relationship
- Persona.agents backref
- Multiple agents sharing same persona (no uniqueness constraint)
- Backward compatibility (all new fields NULL)
- Continuity chain (A → B → C)
- FK integrity errors
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from claude_headspace.models import Agent, Organisation, Persona, Position, Role
from claude_headspace.models.project import Project


@pytest.fixture
def test_project(db_session):
    """Create a test Project for Agent FK."""
    project = Project(name="test-project", slug="test-project", path="/tmp/test-project")
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def dev_role(db_session):
    """Create a developer Role."""
    role = Role(name="developer")
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def test_persona(db_session, dev_role):
    """Create a test Persona."""
    persona = Persona(name="TestBot", role=dev_role)
    db_session.add(persona)
    db_session.flush()
    return persona


@pytest.fixture
def test_org(db_session):
    """Create a test Organisation."""
    org = Organisation(name="TestOrg", status="active")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_position(db_session, test_org, dev_role):
    """Create a test Position."""
    pos = Position(org_id=test_org.id, role_id=dev_role.id, title="Lead Developer")
    db_session.add(pos)
    db_session.flush()
    return pos


def _make_agent(db_session, project, **kwargs):
    """Helper to create an Agent with required fields."""
    agent = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        **kwargs,
    )
    db_session.add(agent)
    db_session.flush()
    return agent


class TestPersonaRelationship:
    """Test Agent.persona FK and relationship."""

    def test_agent_with_persona(self, db_session, test_project, test_persona):
        """Agent.persona returns the associated Persona object."""
        agent = _make_agent(db_session, test_project, persona_id=test_persona.id)

        assert agent.persona_id == test_persona.id
        assert agent.persona is not None
        assert agent.persona.id == test_persona.id
        assert agent.persona.name == "TestBot"

    def test_persona_agents_backref(self, db_session, test_project, test_persona):
        """Persona.agents returns all agents with that persona_id."""
        a1 = _make_agent(db_session, test_project, persona_id=test_persona.id)
        a2 = _make_agent(db_session, test_project, persona_id=test_persona.id)

        assert len(test_persona.agents) == 2
        agent_ids = {a.id for a in test_persona.agents}
        assert agent_ids == {a1.id, a2.id}

    def test_multiple_agents_same_persona(self, db_session, test_project, test_persona):
        """Multiple agents can share the same persona_id (no uniqueness constraint)."""
        a1 = _make_agent(db_session, test_project, persona_id=test_persona.id)
        a2 = _make_agent(db_session, test_project, persona_id=test_persona.id)
        a3 = _make_agent(db_session, test_project, persona_id=test_persona.id)

        assert a1.persona_id == a2.persona_id == a3.persona_id == test_persona.id
        assert len(test_persona.agents) == 3

    def test_persona_id_fk_integrity(self, db_session, test_project):
        """Setting persona_id to non-existent persona raises IntegrityError."""
        with pytest.raises(IntegrityError):
            _make_agent(db_session, test_project, persona_id=99999)


class TestPositionRelationship:
    """Test Agent.position FK and relationship."""

    def test_agent_with_position(self, db_session, test_project, test_position):
        """Agent.position returns the associated Position object."""
        agent = _make_agent(db_session, test_project, position_id=test_position.id)

        assert agent.position_id == test_position.id
        assert agent.position is not None
        assert agent.position.id == test_position.id
        assert agent.position.title == "Lead Developer"

    def test_position_id_fk_integrity(self, db_session, test_project):
        """Setting position_id to non-existent position raises IntegrityError."""
        with pytest.raises(IntegrityError):
            _make_agent(db_session, test_project, position_id=99999)


class TestPreviousAgentRelationship:
    """Test Agent.previous_agent self-referential FK and relationships."""

    def test_agent_with_predecessor(self, db_session, test_project):
        """Agent.previous_agent returns the predecessor Agent."""
        agent_a = _make_agent(db_session, test_project)
        agent_b = _make_agent(db_session, test_project, previous_agent_id=agent_a.id)

        assert agent_b.previous_agent is not None
        assert agent_b.previous_agent.id == agent_a.id

    def test_successor_agents(self, db_session, test_project):
        """Agent.successor_agents returns agents referencing this as predecessor."""
        agent_a = _make_agent(db_session, test_project)
        agent_b = _make_agent(db_session, test_project, previous_agent_id=agent_a.id)
        agent_c = _make_agent(db_session, test_project, previous_agent_id=agent_a.id)

        assert len(agent_a.successor_agents) == 2
        successor_ids = {a.id for a in agent_a.successor_agents}
        assert successor_ids == {agent_b.id, agent_c.id}

    def test_continuity_chain(self, db_session, test_project):
        """Agents can form a continuity chain: A → B → C."""
        agent_a = _make_agent(db_session, test_project)
        agent_b = _make_agent(db_session, test_project, previous_agent_id=agent_a.id)
        agent_c = _make_agent(db_session, test_project, previous_agent_id=agent_b.id)

        # Forward traversal
        assert agent_a.previous_agent is None
        assert agent_b.previous_agent.id == agent_a.id
        assert agent_c.previous_agent.id == agent_b.id

        # Reverse traversal
        assert len(agent_a.successor_agents) == 1
        assert agent_a.successor_agents[0].id == agent_b.id
        assert len(agent_b.successor_agents) == 1
        assert agent_b.successor_agents[0].id == agent_c.id
        assert len(agent_c.successor_agents) == 0

    def test_first_in_chain_null_predecessor(self, db_session, test_project):
        """First agent in a chain has previous_agent_id = NULL."""
        agent = _make_agent(db_session, test_project)

        assert agent.previous_agent_id is None
        assert agent.previous_agent is None

    def test_previous_agent_id_fk_integrity(self, db_session, test_project):
        """Setting previous_agent_id to non-existent agent raises IntegrityError."""
        with pytest.raises(IntegrityError):
            _make_agent(db_session, test_project, previous_agent_id=99999)


class TestBackwardCompatibility:
    """Test that agents with all new fields NULL work correctly."""

    def test_agent_all_new_fields_null(self, db_session, test_project):
        """Agent with no persona, position, or predecessor has all new fields NULL."""
        agent = _make_agent(db_session, test_project)

        assert agent.persona_id is None
        assert agent.position_id is None
        assert agent.previous_agent_id is None
        assert agent.persona is None
        assert agent.position is None
        assert agent.previous_agent is None
        assert agent.successor_agents == []

    def test_existing_agent_properties_still_work(self, db_session, test_project):
        """Existing Agent properties (name, repr) still work with new fields."""
        agent = _make_agent(db_session, test_project)

        # name property should still work
        assert test_project.name in agent.name

        # repr should still work
        assert str(agent.id) in repr(agent)


class TestCombinedFields:
    """Test agent with all three new fields set simultaneously."""

    def test_agent_with_all_fields(self, db_session, test_project, test_persona, test_position):
        """Agent can have persona, position, and predecessor all set."""
        predecessor = _make_agent(db_session, test_project)
        agent = _make_agent(
            db_session, test_project,
            persona_id=test_persona.id,
            position_id=test_position.id,
            previous_agent_id=predecessor.id,
        )

        assert agent.persona.name == "TestBot"
        assert agent.position.title == "Lead Developer"
        assert agent.previous_agent.id == predecessor.id
