"""Tests for domain models (Sprint 3)."""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from claude_headspace.app import create_app
from claude_headspace.database import db
from claude_headspace.models import (
    Objective,
    ObjectiveHistory,
    Project,
    Agent,
    Command,
    Turn,
    Event,
    CommandState,
    TurnActor,
    TurnIntent,
    EventType,
)


@pytest.fixture
def app_with_db():
    """Create a Flask application with database for testing."""
    project_root = Path(__file__).parent.parent
    original_cwd = os.getcwd()
    os.chdir(project_root)

    app = create_app(config_path=str(project_root / "config.yaml"))
    app.config.update({
        "TESTING": True,
    })

    with app.app_context():
        yield app

    os.chdir(original_cwd)


@pytest.fixture
def db_session(app_with_db):
    """Provide a database session for testing."""
    with app_with_db.app_context():
        yield db.session
        db.session.rollback()


class TestEnumDefinitions:
    """Test enum definitions."""

    def test_commandstate_has_five_values(self):
        """Test CommandState enum has exactly 5 values."""
        values = list(CommandState)
        assert len(values) == 5
        assert CommandState.IDLE in values
        assert CommandState.COMMANDED in values
        assert CommandState.PROCESSING in values
        assert CommandState.AWAITING_INPUT in values
        assert CommandState.COMPLETE in values

    def test_commandstate_values(self):
        """Test CommandState enum values."""
        assert CommandState.IDLE.value == "idle"
        assert CommandState.COMMANDED.value == "commanded"
        assert CommandState.PROCESSING.value == "processing"
        assert CommandState.AWAITING_INPUT.value == "awaiting_input"
        assert CommandState.COMPLETE.value == "complete"

    def test_turnactor_has_two_values(self):
        """Test TurnActor enum has exactly 2 values."""
        values = list(TurnActor)
        assert len(values) == 2
        assert TurnActor.USER in values
        assert TurnActor.AGENT in values

    def test_turnactor_values(self):
        """Test TurnActor enum values."""
        assert TurnActor.USER.value == "user"
        assert TurnActor.AGENT.value == "agent"

    def test_turnintent_has_six_values(self):
        """Test TurnIntent enum has exactly 6 values."""
        values = list(TurnIntent)
        assert len(values) == 6
        assert TurnIntent.COMMAND in values
        assert TurnIntent.ANSWER in values
        assert TurnIntent.QUESTION in values
        assert TurnIntent.COMPLETION in values
        assert TurnIntent.PROGRESS in values
        assert TurnIntent.END_OF_COMMAND in values

    def test_turnintent_values(self):
        """Test TurnIntent enum values."""
        assert TurnIntent.COMMAND.value == "command"
        assert TurnIntent.ANSWER.value == "answer"
        assert TurnIntent.QUESTION.value == "question"
        assert TurnIntent.COMPLETION.value == "completion"
        assert TurnIntent.PROGRESS.value == "progress"


class TestEventTypeConstants:
    """Test EventType constants."""

    def test_event_type_constants(self):
        """Test EventType has all expected constants."""
        assert EventType.SESSION_DISCOVERED == "session_discovered"
        assert EventType.SESSION_ENDED == "session_ended"
        assert EventType.TURN_DETECTED == "turn_detected"
        assert EventType.STATE_TRANSITION == "state_transition"
        assert EventType.HOOK_RECEIVED == "hook_received"
        assert EventType.OBJECTIVE_CHANGED == "objective_changed"


class TestModelInstantiation:
    """Test that all models can be instantiated."""

    def test_objective_instantiation(self, db_session):
        """Test Objective model can be instantiated."""
        obj = Objective(current_text="Build feature X")
        assert obj.current_text == "Build feature X"
        assert obj.constraints is None
        # Note: defaults are applied at INSERT time, not instantiation

    def test_objective_with_constraints(self, db_session):
        """Test Objective with constraints."""
        obj = Objective(
            current_text="Build feature X",
            constraints="Must use existing API"
        )
        assert obj.constraints == "Must use existing API"

    def test_objective_history_instantiation(self, db_session):
        """Test ObjectiveHistory model can be instantiated."""
        history = ObjectiveHistory(
            objective_id=1,
            text="Previous objective",
            started_at=datetime.now(timezone.utc)
        )
        assert history.text == "Previous objective"
        assert history.ended_at is None

    def test_project_instantiation(self, db_session):
        """Test Project model can be instantiated."""
        project = Project(
            name="Test Project",
            path="/path/to/project"
        )
        assert project.name == "Test Project"
        assert project.path == "/path/to/project"
        assert project.github_repo is None
        assert project.current_branch is None
        # Note: defaults are applied at INSERT time, not instantiation

    def test_project_with_github(self, db_session):
        """Test Project with GitHub repo."""
        project = Project(
            name="Test Project",
            path="/path/to/project",
            github_repo="https://github.com/user/repo",
            current_branch="main"
        )
        assert project.github_repo == "https://github.com/user/repo"
        assert project.current_branch == "main"

    def test_agent_instantiation(self, db_session):
        """Test Agent model can be instantiated."""
        session_uuid = uuid4()
        agent = Agent(
            session_uuid=session_uuid,
            project_id=1
        )
        assert agent.session_uuid == session_uuid
        assert agent.project_id == 1
        assert agent.iterm_pane_id is None
        # Note: defaults are applied at INSERT time, not instantiation

    def test_command_instantiation(self, db_session):
        """Test Command model can be instantiated."""
        command = Command(agent_id=1)
        assert command.agent_id == 1
        # Note: defaults are applied at INSERT time, not instantiation
        assert command.completed_at is None

    def test_command_with_state(self, db_session):
        """Test Command with specific state."""
        command = Command(agent_id=1, state=CommandState.PROCESSING)
        assert command.state == CommandState.PROCESSING

    def test_turn_instantiation(self, db_session):
        """Test Turn model can be instantiated."""
        turn = Turn(
            command_id=1,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Do something"
        )
        assert turn.command_id == 1
        assert turn.actor == TurnActor.USER
        assert turn.intent == TurnIntent.COMMAND
        assert turn.text == "Do something"
        # Note: defaults are applied at INSERT time, not instantiation

    def test_event_instantiation(self, db_session):
        """Test Event model can be instantiated."""
        event = Event(
            event_type=EventType.SESSION_DISCOVERED,
            payload={"session_id": "abc123"}
        )
        assert event.event_type == EventType.SESSION_DISCOVERED
        assert event.payload == {"session_id": "abc123"}
        assert event.project_id is None
        assert event.agent_id is None
        assert event.command_id is None
        assert event.turn_id is None

    def test_event_with_partial_fks(self, db_session):
        """Test Event with some FKs set."""
        event = Event(
            event_type=EventType.STATE_TRANSITION,
            project_id=1,
            agent_id=2
        )
        assert event.project_id == 1
        assert event.agent_id == 2
        assert event.command_id is None
        assert event.turn_id is None


class TestModelRelationships:
    """Test model relationships are properly defined."""

    def test_project_has_agents_relationship(self):
        """Test Project has agents relationship."""
        project = Project(name="Test", path="/test")
        assert hasattr(project, 'agents')

    def test_agent_has_project_relationship(self):
        """Test Agent has project relationship."""
        agent = Agent(session_uuid=uuid4(), project_id=1)
        assert hasattr(agent, 'project')

    def test_agent_has_commands_relationship(self):
        """Test Agent has commands relationship."""
        agent = Agent(session_uuid=uuid4(), project_id=1)
        assert hasattr(agent, 'commands')

    def test_command_has_agent_relationship(self):
        """Test Command has agent relationship."""
        command = Command(agent_id=1)
        assert hasattr(command, 'agent')

    def test_command_has_turns_relationship(self):
        """Test Command has turns relationship."""
        command = Command(agent_id=1)
        assert hasattr(command, 'turns')

    def test_turn_has_command_relationship(self):
        """Test Turn has command relationship."""
        turn = Turn(command_id=1, actor=TurnActor.USER, intent=TurnIntent.COMMAND, text="test")
        assert hasattr(turn, 'command')

    def test_objective_has_history_relationship(self):
        """Test Objective has history relationship."""
        obj = Objective(current_text="Test")
        assert hasattr(obj, 'history')

    def test_objective_history_has_objective_relationship(self):
        """Test ObjectiveHistory has objective relationship."""
        history = ObjectiveHistory(objective_id=1, text="Test", started_at=datetime.now(timezone.utc))
        assert hasattr(history, 'objective')


class TestAgentStateDerivedProperty:
    """Test Agent.state derived property."""

    def test_agent_has_state_property(self):
        """Test Agent has state property defined."""
        # Check that state is a property on the Agent class
        assert isinstance(Agent.__dict__.get('state'), property)

    def test_agent_has_get_current_command_method(self):
        """Test Agent has get_current_command method."""
        agent = Agent(session_uuid=uuid4(), project_id=1)
        assert hasattr(agent, 'get_current_command')
        assert callable(agent.get_current_command)


class TestCommandInstructionAndCompletionFields:
    """Test Command model new fields: instruction, instruction_generated_at,
    completion_summary, completion_summary_generated_at."""

    def test_command_has_instruction_field(self):
        """Test Command has instruction field defaulting to None."""
        command = Command(agent_id=1)
        assert hasattr(command, 'instruction')
        assert command.instruction is None

    def test_command_has_instruction_generated_at_field(self):
        """Test Command has instruction_generated_at field defaulting to None."""
        command = Command(agent_id=1)
        assert hasattr(command, 'instruction_generated_at')
        assert command.instruction_generated_at is None

    def test_command_has_completion_summary_field(self):
        """Test Command has completion_summary field defaulting to None."""
        command = Command(agent_id=1)
        assert hasattr(command, 'completion_summary')
        assert command.completion_summary is None

    def test_command_has_completion_summary_generated_at_field(self):
        """Test Command has completion_summary_generated_at field defaulting to None."""
        command = Command(agent_id=1)
        assert hasattr(command, 'completion_summary_generated_at')
        assert command.completion_summary_generated_at is None

    def test_command_instruction_accepts_text(self):
        """Test Command instruction field can store text."""
        command = Command(agent_id=1, instruction="Refactor the auth module")
        assert command.instruction == "Refactor the auth module"

    def test_command_completion_summary_accepts_text(self):
        """Test Command completion_summary field can store text."""
        command = Command(agent_id=1, completion_summary="Auth module refactored successfully")
        assert command.completion_summary == "Auth module refactored successfully"


class TestCommandQueryMethods:
    """Test Command query methods."""

    def test_command_has_get_recent_turns_method(self):
        """Test Command has get_recent_turns method."""
        command = Command(agent_id=1)
        assert hasattr(command, 'get_recent_turns')
        assert callable(command.get_recent_turns)


class TestModelRepr:
    """Test model __repr__ methods."""

    def test_objective_repr(self):
        """Test Objective __repr__."""
        obj = Objective(current_text="Test")
        repr_str = repr(obj)
        assert "Objective" in repr_str

    def test_project_repr(self):
        """Test Project __repr__."""
        project = Project(name="Test", path="/test")
        repr_str = repr(project)
        assert "Project" in repr_str
        assert "Test" in repr_str

    def test_agent_repr(self):
        """Test Agent __repr__."""
        session_uuid = uuid4()
        agent = Agent(session_uuid=session_uuid, project_id=1)
        repr_str = repr(agent)
        assert "Agent" in repr_str

    def test_command_repr(self):
        """Test Command __repr__."""
        command = Command(agent_id=1, state=CommandState.PROCESSING)
        repr_str = repr(command)
        assert "Command" in repr_str
        assert "processing" in repr_str

    def test_turn_repr(self):
        """Test Turn __repr__."""
        turn = Turn(command_id=1, actor=TurnActor.USER, intent=TurnIntent.COMMAND, text="test")
        repr_str = repr(turn)
        assert "Turn" in repr_str
        assert "user" in repr_str
        assert "command" in repr_str

    def test_event_repr(self):
        """Test Event __repr__."""
        event = Event(event_type=EventType.SESSION_DISCOVERED)
        repr_str = repr(event)
        assert "Event" in repr_str
        assert "session_discovered" in repr_str

    def test_objective_history_repr(self):
        """Test ObjectiveHistory __repr__."""
        history = ObjectiveHistory(objective_id=1, text="Test", started_at=datetime.now(timezone.utc))
        repr_str = repr(history)
        assert "ObjectiveHistory" in repr_str
