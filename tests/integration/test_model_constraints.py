"""Database constraint verification tests.

Verifies that real Postgres constraints are enforced:
- Unique constraints (Project.path, Agent.session_uuid)
- NOT NULL enforcement
- Enum constraint enforcement
- Cascade delete behavior
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

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


class TestUniqueConstraints:
    def test_project_path_unique(self, db_session):
        """Project.path has a unique constraint."""
        ProjectFactory(path="/unique/path")
        db_session.flush()

        with pytest.raises(IntegrityError):
            ProjectFactory(path="/unique/path")
            db_session.flush()

    def test_agent_session_uuid_unique(self, db_session):
        """Agent.session_uuid has a unique index."""
        shared_uuid = uuid.uuid4()
        AgentFactory(session_uuid=shared_uuid)
        db_session.flush()

        with pytest.raises(IntegrityError):
            AgentFactory(session_uuid=shared_uuid)
            db_session.flush()


class TestNotNullConstraints:
    def test_project_name_not_null(self, db_session):
        """Project.name cannot be null."""
        with pytest.raises(IntegrityError):
            project = Project(name=None, slug="test", path="/test/path")
            db_session.add(project)
            db_session.flush()

    def test_project_path_not_null(self, db_session):
        """Project.path cannot be null."""
        with pytest.raises(IntegrityError):
            project = Project(name="test", slug="test", path=None)
            db_session.add(project)
            db_session.flush()

    def test_agent_session_uuid_not_null(self, db_session):
        """Agent.session_uuid cannot be null."""
        project = ProjectFactory()
        db_session.flush()

        with pytest.raises(IntegrityError):
            agent = Agent(session_uuid=None, project_id=project.id)
            db_session.add(agent)
            db_session.flush()

    def test_task_agent_id_not_null(self, db_session):
        """Task.agent_id cannot be null."""
        with pytest.raises(IntegrityError):
            task = Task(agent_id=None, state=TaskState.IDLE, started_at=datetime.now(timezone.utc))
            db_session.add(task)
            db_session.flush()

    def test_turn_text_not_null(self, db_session):
        """Turn.text cannot be null."""
        task = TaskFactory()
        db_session.flush()

        with pytest.raises(IntegrityError):
            turn = Turn(
                task_id=task.id,
                actor=TurnActor.USER,
                intent=TurnIntent.COMMAND,
                text=None,
                timestamp=datetime.now(timezone.utc),
            )
            db_session.add(turn)
            db_session.flush()

    def test_event_type_not_null(self, db_session):
        """Event.event_type cannot be null."""
        with pytest.raises(IntegrityError):
            event = Event(
                event_type=None,
                timestamp=datetime.now(timezone.utc),
            )
            db_session.add(event)
            db_session.flush()

    def test_objective_text_not_null(self, db_session):
        """Objective.current_text cannot be null."""
        with pytest.raises(IntegrityError):
            obj = Objective(current_text=None, set_at=datetime.now(timezone.utc))
            db_session.add(obj)
            db_session.flush()


class TestCascadeDeletes:
    def test_delete_project_cascades_to_agents(self, db_session):
        """Deleting a project should cascade delete its agents."""
        project = ProjectFactory()
        db_session.flush()
        agent = AgentFactory(project=project)
        db_session.flush()

        agent_id = agent.id
        db_session.delete(project)
        db_session.flush()

        result = db_session.execute(
            select(Agent).where(Agent.id == agent_id)
        ).scalar_one_or_none()
        assert result is None

    def test_delete_agent_cascades_to_tasks(self, db_session):
        """Deleting an agent should cascade delete its tasks."""
        agent = AgentFactory()
        db_session.flush()
        task = TaskFactory(agent=agent)
        db_session.flush()

        task_id = task.id
        db_session.delete(agent)
        db_session.flush()

        result = db_session.execute(
            select(Task).where(Task.id == task_id)
        ).scalar_one_or_none()
        assert result is None

    def test_delete_task_cascades_to_turns(self, db_session):
        """Deleting a task should cascade delete its turns."""
        task = TaskFactory()
        db_session.flush()
        turn = TurnFactory(task=task)
        db_session.flush()

        turn_id = turn.id
        db_session.delete(task)
        db_session.flush()

        result = db_session.execute(
            select(Turn).where(Turn.id == turn_id)
        ).scalar_one_or_none()
        assert result is None

    def test_delete_objective_cascades_to_history(self, db_session):
        """Deleting an objective should cascade delete its history."""
        objective = ObjectiveFactory()
        db_session.flush()
        history = ObjectiveHistoryFactory(objective=objective)
        db_session.flush()

        history_id = history.id
        db_session.delete(objective)
        db_session.flush()

        result = db_session.execute(
            select(ObjectiveHistory).where(ObjectiveHistory.id == history_id)
        ).scalar_one_or_none()
        assert result is None

    def test_delete_agent_sets_null_on_event(self, db_session):
        """Deleting an agent should SET NULL on event references (via DB constraint)."""
        project = ProjectFactory()
        db_session.flush()
        agent = AgentFactory(project=project)
        db_session.flush()
        event = EventFactory(agent_id=agent.id)
        db_session.flush()

        event_id = event.id
        agent_id = agent.id

        # Use raw SQL DELETE to trigger the database-level ON DELETE SET NULL
        # (ORM delete triggers cascade="all, delete-orphan" from project, not the FK constraint)
        db_session.execute(delete(Agent).where(Agent.id == agent_id))
        db_session.flush()

        # Expire cached attributes so we re-read from DB
        db_session.expire_all()

        result = db_session.execute(
            select(Event).where(Event.id == event_id)
        ).scalar_one()
        assert result.agent_id is None


class TestEnumConstraints:
    def test_task_state_valid_values(self, db_session):
        """All TaskState enum values are valid in the database."""
        agent = AgentFactory()
        db_session.flush()

        for state in TaskState:
            task = TaskFactory(agent=agent, state=state)
            db_session.flush()
            assert task.state == state

    def test_turn_actor_valid_values(self, db_session):
        """All TurnActor enum values are valid in the database."""
        task = TaskFactory()
        db_session.flush()

        for actor in TurnActor:
            turn = TurnFactory(task=task, actor=actor)
            db_session.flush()
            assert turn.actor == actor

    def test_turn_intent_valid_values(self, db_session):
        """All TurnIntent enum values are valid in the database."""
        task = TaskFactory()
        db_session.flush()

        for intent in TurnIntent:
            turn = TurnFactory(task=task, intent=intent)
            db_session.flush()
            assert turn.intent == intent
