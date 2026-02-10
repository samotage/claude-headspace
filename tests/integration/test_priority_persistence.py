"""Integration tests for priority field persistence on Agent model."""

from datetime import datetime, timezone

import pytest

from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project


class TestAgentPriorityPersistence:

    def test_agent_created_without_priority(self, db_session):
        """Agent can be created with null priority fields."""
        project = Project(name="test-project", slug="test-project", path="/test/path")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        fetched = db_session.get(Agent, agent.id)
        assert fetched.priority_score is None
        assert fetched.priority_reason is None
        assert fetched.priority_updated_at is None

    def test_agent_priority_persisted(self, db_session):
        """Agent priority score, reason, and timestamp can be set and persisted."""
        project = Project(name="test-project-2", slug="test-project-2", path="/test/path-2")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="11111111-2222-3333-4444-555555555555",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        now = datetime.now(timezone.utc)
        agent.priority_score = 85
        agent.priority_reason = "Working on auth middleware — directly aligned with shipping authentication."
        agent.priority_updated_at = now
        db_session.flush()

        fetched = db_session.get(Agent, agent.id)
        assert fetched.priority_score == 85
        assert "auth middleware" in fetched.priority_reason
        assert fetched.priority_updated_at is not None

    def test_agent_priority_can_be_updated(self, db_session):
        """Agent priority can be overwritten."""
        project = Project(name="test-project-3", slug="test-project-3", path="/test/path-3")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="22222222-3333-4444-5555-666666666666",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            priority_score=50,
            priority_reason="Default score",
            priority_updated_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        agent.priority_score = 92
        agent.priority_reason = "High priority - directly aligned with objective"
        db_session.flush()

        fetched = db_session.get(Agent, agent.id)
        assert fetched.priority_score == 92
        assert "High priority" in fetched.priority_reason

    def test_agent_priority_score_range(self, db_session):
        """Agent priority score stores boundary values correctly."""
        project = Project(name="test-project-4", slug="test-project-4", path="/test/path-4")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="33333333-4444-5555-6666-777777777777",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            priority_score=0,
        )
        db_session.add(agent)
        db_session.flush()

        fetched = db_session.get(Agent, agent.id)
        assert fetched.priority_score == 0

        agent.priority_score = 100
        db_session.flush()

        fetched = db_session.get(Agent, agent.id)
        assert fetched.priority_score == 100
