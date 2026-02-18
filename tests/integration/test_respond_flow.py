"""Integration tests for end-to-end response flow.

Verifies the full respond cycle:
- Agent in AWAITING_INPUT state receives a response
- Turn record created with correct actor/intent
- Command state transitions to PROCESSING
"""

import pytest
from sqlalchemy import select
from unittest.mock import patch, MagicMock

from claude_headspace.models import (
    Agent,
    Command,
    CommandState,
    Turn,
    TurnActor,
    TurnIntent,
)

from .factories import (
    AgentFactory,
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

        command = CommandFactory(
            agent=agent,
            state=CommandState.AWAITING_INPUT,
        )
        db_session.flush()

        # Verify the setup
        retrieved = db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        ).scalar_one()
        assert retrieved.claude_session_id == "test-session-abc"

        retrieved_command = db_session.execute(
            select(Command).where(Command.id == command.id)
        ).scalar_one()
        assert retrieved_command.state == CommandState.AWAITING_INPUT

    def test_turn_created_for_respond(self, db_session):
        """Verify Turn record with USER/ANSWER can be created for a response."""
        project = ProjectFactory(name="respond-turn-test")
        db_session.flush()

        agent = AgentFactory(project=project, claude_session_id="sess-turn-test")
        db_session.flush()

        command = CommandFactory(agent=agent, state=CommandState.AWAITING_INPUT)
        db_session.flush()

        # Create the Turn that the respond route would create
        turn = Turn(
            command_id=command.id,
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
        assert retrieved_turn.command_id == command.id

    def test_state_transition_awaiting_to_processing(self, db_session):
        """Verify command state can transition from AWAITING_INPUT to PROCESSING."""
        project = ProjectFactory(name="respond-transition-test")
        db_session.flush()

        agent = AgentFactory(project=project, claude_session_id="sess-trans-test")
        db_session.flush()

        command = CommandFactory(agent=agent, state=CommandState.AWAITING_INPUT)
        db_session.flush()

        # Perform the transition that the respond route performs
        command.state = CommandState.PROCESSING
        db_session.flush()

        # Verify the transition persisted
        retrieved = db_session.execute(
            select(Command).where(Command.id == command.id)
        ).scalar_one()
        assert retrieved.state == CommandState.PROCESSING

    def test_full_respond_cycle(self, db_session):
        """End-to-end: setup agent, create Turn, transition state, verify all records."""
        # Setup: Project -> Agent -> Command in AWAITING_INPUT
        project = ProjectFactory(name="full-respond-test")
        db_session.flush()

        agent = AgentFactory(
            project=project,
            claude_session_id="sess-full-test",
        )
        db_session.flush()

        # Create AGENT QUESTION turn (what hook_receiver creates)
        command = CommandFactory(agent=agent, state=CommandState.AWAITING_INPUT)
        db_session.flush()

        question_turn = TurnFactory(
            command=command,
            actor=TurnActor.AGENT,
            intent=TurnIntent.QUESTION,
            text="Do you want to proceed?\n1. Yes\n2. No",
        )
        db_session.flush()

        # Act: Simulate what the respond route does
        answer_turn = Turn(
            command_id=command.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text="1",
        )
        db_session.add(answer_turn)
        command.state = CommandState.PROCESSING
        db_session.flush()

        # Verify: Turn chain exists
        turns = db_session.execute(
            select(Turn).where(Turn.command_id == command.id).order_by(Turn.id)
        ).scalars().all()

        assert len(turns) == 2
        assert turns[0].actor == TurnActor.AGENT
        assert turns[0].intent == TurnIntent.QUESTION
        assert turns[1].actor == TurnActor.USER
        assert turns[1].intent == TurnIntent.ANSWER
        assert turns[1].text == "1"

        # Verify: Command state transitioned
        refreshed_command = db_session.execute(
            select(Command).where(Command.id == command.id)
        ).scalar_one()
        assert refreshed_command.state == CommandState.PROCESSING

    def test_agent_tmux_pane_id_stored(self, db_session):
        """Verify tmux_pane_id can be stored on an agent."""
        project = ProjectFactory(name="tmux-pane-test")
        db_session.flush()

        agent = AgentFactory(
            project=project,
            claude_session_id="abc123def",
        )
        db_session.flush()

        agent.tmux_pane_id = "%5"
        db_session.flush()

        retrieved = db_session.execute(
            select(Agent).where(Agent.id == agent.id)
        ).scalar_one()
        assert retrieved.tmux_pane_id == "%5"
