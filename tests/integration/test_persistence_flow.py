"""End-to-end persistence flow tests.

Verifies the complete entity chain: Project -> Agent -> Command -> Turn -> Event
can be created, persisted, retrieved, and all relationships are intact.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from claude_headspace.models import (
    Agent,
    Event,
    EventType,
    Objective,
    ObjectiveHistory,
    Project,
    Command,
    CommandState,
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
    CommandFactory,
    TurnFactory,
)


@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    """Inject the test db_session into all factories."""
    ProjectFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session
    CommandFactory._meta.sqlalchemy_session = db_session
    TurnFactory._meta.sqlalchemy_session = db_session
    EventFactory._meta.sqlalchemy_session = db_session
    ObjectiveFactory._meta.sqlalchemy_session = db_session
    ObjectiveHistoryFactory._meta.sqlalchemy_session = db_session


class TestFullEntityChain:
    """Verify the complete Project -> Agent -> Command -> Turn -> Event chain."""

    def test_create_and_retrieve_full_chain(self, db_session):
        """FR9: Create full entity chain, persist, retrieve, assert integrity."""
        # Create the chain
        project = ProjectFactory(
            name="test-project",
            path="/home/user/test-project",
            github_repo="user/test-project",
            current_branch="main",
        )
        db_session.flush()

        agent = AgentFactory(
            project=project,
            iterm_pane_id="pane-42",
        )
        db_session.flush()

        command = CommandFactory(
            agent=agent,
            state=CommandState.PROCESSING,
        )
        db_session.flush()

        turn = TurnFactory(
            command=command,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Implement the feature",
        )
        db_session.flush()

        event = EventFactory(
            project_id=project.id,
            agent_id=agent.id,
            command_id=command.id,
            turn_id=turn.id,
            event_type=EventType.TURN_DETECTED,
            payload={"action": "user_command"},
        )
        db_session.flush()

        # Retrieve all entities from fresh queries
        retrieved_project = db_session.execute(
            select(Project).where(Project.id == project.id)
        ).scalar_one()
        retrieved_agent = db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        ).scalar_one()
        retrieved_command = db_session.execute(
            select(Command).where(Command.id == command.id)
        ).scalar_one()
        retrieved_turn = db_session.execute(
            select(Turn).where(Turn.id == turn.id)
        ).scalar_one()
        retrieved_event = db_session.execute(
            select(Event).where(Event.id == event.id)
        ).scalar_one()

        # Assert Project fields
        assert retrieved_project.name == "test-project"
        assert retrieved_project.path == "/home/user/test-project"
        assert retrieved_project.github_repo == "user/test-project"
        assert retrieved_project.current_branch == "main"

        # Assert Agent fields and relationship
        assert retrieved_agent.project_id == project.id
        assert retrieved_agent.session_uuid == agent.session_uuid
        assert retrieved_agent.iterm_pane_id == "pane-42"

        # Assert Command fields and relationship
        assert retrieved_command.agent_id == agent.id
        assert retrieved_command.state == CommandState.PROCESSING

        # Assert Turn fields and relationship
        assert retrieved_turn.command_id == command.id
        assert retrieved_turn.actor == TurnActor.USER
        assert retrieved_turn.intent == TurnIntent.COMMAND
        assert retrieved_turn.text == "Implement the feature"

        # Assert Event fields and relationships
        assert retrieved_event.project_id == project.id
        assert retrieved_event.agent_id == agent.id
        assert retrieved_event.command_id == command.id
        assert retrieved_event.turn_id == turn.id
        assert retrieved_event.event_type == EventType.TURN_DETECTED
        assert retrieved_event.payload == {"action": "user_command"}

    def test_multiple_turns_per_command(self, db_session):
        """Verify a command can have multiple turns."""
        command = CommandFactory(state=CommandState.PROCESSING)
        db_session.flush()

        turns = [
            TurnFactory(command=command, actor=TurnActor.USER, intent=TurnIntent.COMMAND, text="Do X"),
            TurnFactory(command=command, actor=TurnActor.AGENT, intent=TurnIntent.PROGRESS, text="Working on X"),
            TurnFactory(command=command, actor=TurnActor.AGENT, intent=TurnIntent.COMPLETION, text="Done with X"),
        ]
        db_session.flush()

        results = db_session.execute(
            select(Turn).where(Turn.command_id == command.id)
        ).scalars().all()

        assert len(results) == 3
        actors = {t.actor for t in results}
        assert TurnActor.USER in actors
        assert TurnActor.AGENT in actors

    def test_multiple_commands_per_agent(self, db_session):
        """Verify an agent can have multiple commands."""
        agent = AgentFactory()
        db_session.flush()

        commands = [
            CommandFactory(agent=agent, state=CommandState.COMPLETE),
            CommandFactory(agent=agent, state=CommandState.IDLE),
        ]
        db_session.flush()

        results = db_session.execute(
            select(Command).where(Command.agent_id == agent.id)
        ).scalars().all()

        assert len(results) == 2

    def test_multiple_agents_per_project(self, db_session):
        """Verify a project can have multiple agents."""
        project = ProjectFactory()
        db_session.flush()

        agents = [
            AgentFactory(project=project),
            AgentFactory(project=project),
        ]
        db_session.flush()

        results = db_session.execute(
            select(Agent).where(Agent.project_id == project.id)
        ).scalars().all()

        assert len(results) == 2
        assert results[0].session_uuid != results[1].session_uuid


class TestObjectiveChain:
    """Verify Objective -> ObjectiveHistory persistence."""

    def test_objective_with_history(self, db_session):
        """Create an objective with history entries."""
        objective = ObjectiveFactory(
            current_text="Current goal",
            constraints="Must be fast",
        )
        db_session.flush()

        history1 = ObjectiveHistoryFactory(
            objective=objective,
            text="Previous goal 1",
            constraints="Old constraints",
        )
        history2 = ObjectiveHistoryFactory(
            objective=objective,
            text="Previous goal 2",
        )
        db_session.flush()

        # Retrieve and verify
        retrieved = db_session.execute(
            select(Objective).where(Objective.id == objective.id)
        ).scalar_one()

        assert retrieved.current_text == "Current goal"
        assert retrieved.constraints == "Must be fast"

        histories = db_session.execute(
            select(ObjectiveHistory).where(ObjectiveHistory.objective_id == objective.id)
        ).scalars().all()

        assert len(histories) == 2
        texts = {h.text for h in histories}
        assert "Previous goal 1" in texts
        assert "Previous goal 2" in texts


class TestEventAuditTrail:
    """Verify Event can reference various entity combinations."""

    def test_event_with_no_references(self, db_session):
        """Events can exist without any entity references."""
        event = EventFactory(
            event_type=EventType.NOTIFICATION_SENT,
            payload={"message": "hello"},
        )
        db_session.flush()

        result = db_session.execute(
            select(Event).where(Event.id == event.id)
        ).scalar_one()

        assert result.project_id is None
        assert result.agent_id is None
        assert result.command_id is None
        assert result.turn_id is None

    def test_event_with_partial_references(self, db_session):
        """Events can reference only some entities."""
        project = ProjectFactory()
        db_session.flush()

        event = EventFactory(
            project_id=project.id,
            event_type=EventType.SESSION_DISCOVERED,
        )
        db_session.flush()

        result = db_session.execute(
            select(Event).where(Event.id == event.id)
        ).scalar_one()

        assert result.project_id == project.id
        assert result.agent_id is None

    def test_event_jsonb_payload(self, db_session):
        """Verify JSONB payload stores and retrieves complex data."""
        payload = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "bool": True,
            "null_val": None,
        }
        event = EventFactory(event_type=EventType.STATE_TRANSITION, payload=payload)
        db_session.flush()

        result = db_session.execute(
            select(Event).where(Event.id == event.id)
        ).scalar_one()

        assert result.payload["nested"]["key"] == "value"
        assert result.payload["list"] == [1, 2, 3]
        assert result.payload["bool"] is True
        assert result.payload["null_val"] is None
