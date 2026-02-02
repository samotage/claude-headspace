"""Factory Boy factory definitions for all domain models.

Each factory produces a valid, persistable model instance with
correct foreign keys, valid enum values, and non-null required fields.
"""

import uuid
from datetime import datetime, timezone

import factory
from factory.alchemy import SQLAlchemyModelFactory

from claude_headspace.models import (
    Agent,
    Event,
    EventType,
    Objective,
    ObjectiveHistory,
    Project,
    Task,
    TaskState,
    Turn,
    TurnActor,
    TurnIntent,
)


class ProjectFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Project
        sqlalchemy_session = None  # Set via fixture
        sqlalchemy_session_persistence = "commit"

    name = factory.Sequence(lambda n: f"project-{n}")
    path = factory.Sequence(lambda n: f"/home/user/projects/project-{n}")
    github_repo = factory.LazyAttribute(lambda o: f"user/{o.name}")
    current_branch = "main"
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class AgentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Agent
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    session_uuid = factory.LazyFunction(uuid.uuid4)
    claude_session_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    project = factory.SubFactory(ProjectFactory)
    iterm_pane_id = factory.Sequence(lambda n: f"pane-{n}")
    started_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    last_seen_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    ended_at = None


class TaskFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Task
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    agent = factory.SubFactory(AgentFactory)
    state = TaskState.IDLE
    started_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    completed_at = None


class TurnFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Turn
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    task = factory.SubFactory(TaskFactory)
    actor = TurnActor.USER
    intent = TurnIntent.COMMAND
    text = factory.Sequence(lambda n: f"Turn content {n}")
    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class EventFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Event
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    event_type = EventType.SESSION_DISCOVERED
    payload = factory.LazyFunction(lambda: {"source": "test"})
    project_id = None
    agent_id = None
    task_id = None
    turn_id = None


class ObjectiveFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Objective
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    current_text = factory.Sequence(lambda n: f"Objective {n}: Complete the task")
    constraints = "No constraints"
    priority_enabled = True
    set_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class ObjectiveHistoryFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ObjectiveHistory
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    objective = factory.SubFactory(ObjectiveFactory)
    text = factory.Sequence(lambda n: f"Historical objective {n}")
    constraints = None
    started_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    ended_at = None


# All factories for easy iteration
ALL_FACTORIES = [
    ProjectFactory,
    AgentFactory,
    TaskFactory,
    TurnFactory,
    EventFactory,
    ObjectiveFactory,
    ObjectiveHistoryFactory,
]
