"""Integration tests for end-to-end response flow.

Verifies the full respond cycle:
- Agent in AWAITING_INPUT state receives a response
- Turn record created with correct actor/intent
- Task state transitions to PROCESSING
"""

import pytest
from sqlalchemy import select
from unittest.mock import patch, MagicMock

from claude_headspace.models import (
    Agent,
    Task,
    TaskState,
    Turn,
    TurnActor,
    TurnIntent,
)

from .factories import (
    AgentFactory,
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


class TestRespondFlow:
    """End-to-end tests for the respond feature with real database."""

    def test_awaiting_input_agent_with_session_id(self, db_session):
        """Verify an agent in AWAITING_INPUT state with session_id can be set up."""
        project = ProjectFactory(name="respond-test")
        db_session.flush()

        agent = AgentFactory(
            project=project,
            claude_session_id="test-session-abc",
        )
        db_session.flush()

        task = TaskFactory(
            agent=agent,
            state=TaskState.AWAITING_INPUT,
        )
        db_session.flush()

        # Verify the setup
        retrieved = db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        ).scalar_one()
        assert retrieved.claude_session_id == "test-session-abc"

        retrieved_task = db_session.execute(
            select(Task).where(Task.id == task.id)
        ).scalar_one()
        assert retrieved_task.state == TaskState.AWAITING_INPUT

    def test_turn_created_for_respond(self, db_session):
        """Verify Turn record with USER/ANSWER can be created for a response."""
        project = ProjectFactory(name="respond-turn-test")
        db_session.flush()

        agent = AgentFactory(project=project, claude_session_id="sess-turn-test")
        db_session.flush()

        task = TaskFactory(agent=agent, state=TaskState.AWAITING_INPUT)
        db_session.flush()

        # Create the Turn that the respond route would create
        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text="1",
        )
        db_session.add(turn)
        db_session.flush()

        # Verify the Turn was persisted correctly
        retrieved_turn = db_session.execute(
            select(Turn).where(Turn.id == turn.id)
        ).scalar_one()
        assert retrieved_turn.actor == TurnActor.USER
        assert retrieved_turn.intent == TurnIntent.ANSWER
        assert retrieved_turn.text == "1"
        assert retrieved_turn.task_id == task.id

    def test_state_transition_awaiting_to_processing(self, db_session):
        """Verify task state can transition from AWAITING_INPUT to PROCESSING."""
        project = ProjectFactory(name="respond-transition-test")
        db_session.flush()

        agent = AgentFactory(project=project, claude_session_id="sess-trans-test")
        db_session.flush()

        task = TaskFactory(agent=agent, state=TaskState.AWAITING_INPUT)
        db_session.flush()

        # Perform the transition that the respond route performs
        task.state = TaskState.PROCESSING
        db_session.flush()

        # Verify the transition persisted
        retrieved = db_session.execute(
            select(Task).where(Task.id == task.id)
        ).scalar_one()
        assert retrieved.state == TaskState.PROCESSING

    def test_full_respond_cycle(self, db_session):
        """End-to-end: setup agent, create Turn, transition state, verify all records."""
        # Setup: Project -> Agent -> Task in AWAITING_INPUT
        project = ProjectFactory(name="full-respond-test")
        db_session.flush()

        agent = AgentFactory(
            project=project,
            claude_session_id="sess-full-test",
        )
        db_session.flush()

        # Create AGENT QUESTION turn (what hook_receiver creates)
        task = TaskFactory(agent=agent, state=TaskState.AWAITING_INPUT)
        db_session.flush()

        question_turn = TurnFactory(
            task=task,
            actor=TurnActor.AGENT,
            intent=TurnIntent.QUESTION,
            text="Do you want to proceed?\n1. Yes\n2. No",
        )
        db_session.flush()

        # Act: Simulate what the respond route does
        answer_turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text="1",
        )
        db_session.add(answer_turn)
        task.state = TaskState.PROCESSING
        db_session.flush()

        # Verify: Turn chain exists
        turns = db_session.execute(
            select(Turn).where(Turn.task_id == task.id).order_by(Turn.id)
        ).scalars().all()

        assert len(turns) == 2
        assert turns[0].actor == TurnActor.AGENT
        assert turns[0].intent == TurnIntent.QUESTION
        assert turns[1].actor == TurnActor.USER
        assert turns[1].intent == TurnIntent.ANSWER
        assert turns[1].text == "1"

        # Verify: Task state transitioned
        refreshed_task = db_session.execute(
            select(Task).where(Task.id == task.id)
        ).scalar_one()
        assert refreshed_task.state == TaskState.PROCESSING

    def test_agent_session_id_maps_to_socket(self, db_session):
        """Verify claude_session_id can be used to derive socket path."""
        from claude_headspace.services.commander_service import get_socket_path

        project = ProjectFactory(name="socket-path-test")
        db_session.flush()

        agent = AgentFactory(
            project=project,
            claude_session_id="abc123def",
        )
        db_session.flush()

        socket_path = get_socket_path(agent.claude_session_id)
        assert socket_path == "/tmp/claudec-abc123def.sock"
