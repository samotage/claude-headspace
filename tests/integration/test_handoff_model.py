"""Integration tests for Handoff model.

Verifies real Postgres constraints and behavior:
- Handoff record creation with all fields
- Handoff.agent relationship navigates to Agent
- Agent.handoff returns Handoff record or None
- Cascade delete (agent deletion removes handoff)
- Multiple handoffs for different agents
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from claude_headspace.models import Agent, Handoff
from claude_headspace.models.project import Project


@pytest.fixture
def test_project(db_session):
    """Create a test Project for Agent FK."""
    project = Project(name="test-project", slug="test-project", path="/tmp/test-project")
    db_session.add(project)
    db_session.flush()
    return project


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


class TestHandoffCreation:
    """Test Handoff record creation with all fields."""

    def test_create_handoff_all_fields(self, db_session, test_project):
        """Handoff record can be created with all fields."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(
            agent_id=agent.id,
            reason="context_limit",
            file_path="data/personas/dev/handoffs/20260220T143025-4b6f8a2c.md",
            injection_prompt="Continue from where the previous agent left off.",
        )
        db_session.add(handoff)
        db_session.flush()

        assert handoff.id is not None
        assert handoff.agent_id == agent.id
        assert handoff.reason == "context_limit"
        assert handoff.file_path == "data/personas/dev/handoffs/20260220T143025-4b6f8a2c.md"
        assert handoff.injection_prompt == "Continue from where the previous agent left off."
        assert handoff.created_at is not None

    def test_create_handoff_minimal_fields(self, db_session, test_project):
        """Handoff can be created with only required fields (agent_id, reason)."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(agent_id=agent.id, reason="shift_end")
        db_session.add(handoff)
        db_session.flush()

        assert handoff.id is not None
        assert handoff.reason == "shift_end"
        assert handoff.file_path is None
        assert handoff.injection_prompt is None

    def test_create_handoff_task_boundary_reason(self, db_session, test_project):
        """Handoff with reason='task_boundary' is valid."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(agent_id=agent.id, reason="task_boundary")
        db_session.add(handoff)
        db_session.flush()

        assert handoff.reason == "task_boundary"

    def test_handoff_agent_id_not_nullable(self, db_session):
        """Handoff without agent_id raises IntegrityError."""
        handoff = Handoff(reason="context_limit")
        db_session.add(handoff)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_handoff_fk_integrity(self, db_session):
        """Handoff with non-existent agent_id raises IntegrityError."""
        handoff = Handoff(agent_id=99999, reason="context_limit")
        db_session.add(handoff)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestHandoffAgentRelationship:
    """Test Handoff.agent relationship navigates to Agent."""

    def test_handoff_agent_navigation(self, db_session, test_project):
        """Handoff.agent returns the associated Agent."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(agent_id=agent.id, reason="context_limit")
        db_session.add(handoff)
        db_session.flush()

        assert handoff.agent is not None
        assert handoff.agent.id == agent.id
        assert handoff.agent.session_uuid == agent.session_uuid


class TestAgentHandoffRelationship:
    """Test Agent.handoff returns Handoff record or None."""

    def test_agent_with_handoff(self, db_session, test_project):
        """Agent.handoff returns the associated Handoff."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(
            agent_id=agent.id,
            reason="context_limit",
            file_path="/tmp/handoff.md",
        )
        db_session.add(handoff)
        db_session.flush()

        assert agent.handoff is not None
        assert agent.handoff.id == handoff.id
        assert agent.handoff.reason == "context_limit"

    def test_agent_without_handoff(self, db_session, test_project):
        """Agent.handoff returns None when no handoff exists."""
        agent = _make_agent(db_session, test_project)

        assert agent.handoff is None


class TestCascadeDelete:
    """Test cascade delete — agent deletion removes handoff."""

    def test_delete_agent_cascades_to_handoff(self, db_session, test_project):
        """Deleting an Agent also deletes its Handoff record."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(agent_id=agent.id, reason="context_limit")
        db_session.add(handoff)
        db_session.flush()

        handoff_id = handoff.id
        db_session.delete(agent)
        db_session.flush()

        # Expire cached objects so the next query hits the DB
        db_session.expire_all()

        # Handoff should be gone (DB-level ON DELETE CASCADE)
        result = db_session.get(Handoff, handoff_id)
        assert result is None


class TestMultipleHandoffs:
    """Test multiple handoffs for different agents."""

    def test_multiple_agents_each_with_handoff(self, db_session, test_project):
        """Multiple agents can each have their own handoff."""
        agent_a = _make_agent(db_session, test_project)
        agent_b = _make_agent(db_session, test_project)

        handoff_a = Handoff(agent_id=agent_a.id, reason="context_limit")
        handoff_b = Handoff(agent_id=agent_b.id, reason="shift_end")
        db_session.add_all([handoff_a, handoff_b])
        db_session.flush()

        assert agent_a.handoff.reason == "context_limit"
        assert agent_b.handoff.reason == "shift_end"
        assert agent_a.handoff.id != agent_b.handoff.id


class TestHandoffRepr:
    """Test Handoff __repr__."""

    def test_repr(self, db_session, test_project):
        """Handoff repr shows id, agent_id, and reason."""
        agent = _make_agent(db_session, test_project)
        handoff = Handoff(agent_id=agent.id, reason="context_limit")
        db_session.add(handoff)
        db_session.flush()

        r = repr(handoff)
        assert "Handoff" in r
        assert str(handoff.id) in r
        assert "context_limit" in r
