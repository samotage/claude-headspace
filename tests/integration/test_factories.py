"""Verify each factory produces a valid, persistable model instance."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from claude_headspace.models import (
    Agent,
    Event,
    Objective,
    ObjectiveHistory,
    Project,
    Task,
    TaskState,
    Turn,
    TurnActor,
    TurnIntent,
)

from .factories import (
    AgentFactory,
    EventFactory,
    ObjectiveFactory,
    ObjectiveHistoryFactory,
    ProjectFactory,
    TaskFactory,
    TurnFactory,
)


@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    """Inject the test db_session into all factories."""
    ProjectFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session
    TaskFactory._meta.sqlalchemy_session = db_session
    TurnFactory._meta.sqlalchemy_session = db_session
    EventFactory._meta.sqlalchemy_session = db_session
    ObjectiveFactory._meta.sqlalchemy_session = db_session
    ObjectiveHistoryFactory._meta.sqlalchemy_session = db_session


class TestProjectFactory:
    def test_creates_valid_project(self, db_session):
        project = ProjectFactory()
        db_session.flush()

        result = db_session.execute(
            select(Project).where(Project.id == project.id)
        ).scalar_one()

        assert result.name == project.name
        assert result.path == project.path
        assert result.created_at is not None
        assert result.created_at.tzinfo is not None

    def test_unique_paths(self, db_session):
        p1 = ProjectFactory()
        p2 = ProjectFactory()
        db_session.flush()
        assert p1.path != p2.path


class TestAgentFactory:
    def test_creates_valid_agent(self, db_session):
        agent = AgentFactory()
        db_session.flush()

        result = db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        ).scalar_one()

        assert result.session_uuid is not None
        assert isinstance(result.session_uuid, uuid.UUID)
        assert result.project_id is not None
        assert result.started_at.tzinfo is not None
        assert result.last_seen_at.tzinfo is not None

    def test_creates_parent_project(self, db_session):
        agent = AgentFactory()
        db_session.flush()

        project = db_session.execute(
            select(Project).where(Project.id == agent.project_id)
        ).scalar_one()

        assert project is not None
        assert project.name is not None

    def test_unique_session_uuids(self, db_session):
        a1 = AgentFactory()
        a2 = AgentFactory()
        db_session.flush()
        assert a1.session_uuid != a2.session_uuid


class TestTaskFactory:
    def test_creates_valid_task(self, db_session):
        task = TaskFactory()
        db_session.flush()

        result = db_session.execute(
            select(Task).where(Task.id == task.id)
        ).scalar_one()

        assert result.state == TaskState.IDLE
        assert result.agent_id is not None
        assert result.started_at.tzinfo is not None

    def test_creates_parent_agent(self, db_session):
        task = TaskFactory()
        db_session.flush()

        agent = db_session.execute(
            select(Agent).where(Agent.id == task.agent_id)
        ).scalar_one()

        assert agent is not None
        assert agent.session_uuid is not None


class TestTurnFactory:
    def test_creates_valid_turn(self, db_session):
        turn = TurnFactory()
        db_session.flush()

        result = db_session.execute(
            select(Turn).where(Turn.id == turn.id)
        ).scalar_one()

        assert result.actor == TurnActor.USER
        assert result.intent == TurnIntent.COMMAND
        assert result.text is not None
        assert result.task_id is not None
        assert result.timestamp.tzinfo is not None

    def test_creates_parent_task(self, db_session):
        turn = TurnFactory()
        db_session.flush()

        task = db_session.execute(
            select(Task).where(Task.id == turn.task_id)
        ).scalar_one()

        assert task is not None


class TestEventFactory:
    def test_creates_valid_event(self, db_session):
        event = EventFactory()
        db_session.flush()

        result = db_session.execute(
            select(Event).where(Event.id == event.id)
        ).scalar_one()

        assert result.event_type is not None
        assert result.timestamp.tzinfo is not None
        assert result.payload == {"source": "test"}

    def test_creates_event_with_references(self, db_session):
        project = ProjectFactory()
        agent = AgentFactory(project=project)
        task = TaskFactory(agent=agent)
        turn = TurnFactory(task=task)
        db_session.flush()

        event = EventFactory(
            project_id=project.id,
            agent_id=agent.id,
            task_id=task.id,
            turn_id=turn.id,
        )
        db_session.flush()

        result = db_session.execute(
            select(Event).where(Event.id == event.id)
        ).scalar_one()

        assert result.project_id == project.id
        assert result.agent_id == agent.id
        assert result.task_id == task.id
        assert result.turn_id == turn.id


class TestObjectiveFactory:
    def test_creates_valid_objective(self, db_session):
        objective = ObjectiveFactory()
        db_session.flush()

        result = db_session.execute(
            select(Objective).where(Objective.id == objective.id)
        ).scalar_one()

        assert result.current_text is not None
        assert result.set_at.tzinfo is not None


class TestObjectiveHistoryFactory:
    def test_creates_valid_history(self, db_session):
        history = ObjectiveHistoryFactory()
        db_session.flush()

        result = db_session.execute(
            select(ObjectiveHistory).where(ObjectiveHistory.id == history.id)
        ).scalar_one()

        assert result.text is not None
        assert result.objective_id is not None
        assert result.started_at.tzinfo is not None

    def test_creates_parent_objective(self, db_session):
        history = ObjectiveHistoryFactory()
        db_session.flush()

        objective = db_session.execute(
            select(Objective).where(Objective.id == history.objective_id)
        ).scalar_one()

        assert objective is not None
        assert objective.current_text is not None
