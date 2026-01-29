"""Tests for state machine service."""

import pytest

from claude_headspace.models.task import TaskState
from claude_headspace.models.turn import TurnActor, TurnIntent
from claude_headspace.services.state_machine import (
    StateMachine,
    TransitionResult,
    VALID_TRANSITIONS,
    get_valid_transitions_from,
    is_terminal_state,
    validate_transition,
)


class TestValidTransitions:
    """Tests for VALID_TRANSITIONS mapping."""

    def test_transitions_mapping_exists(self):
        """VALID_TRANSITIONS should be defined."""
        assert VALID_TRANSITIONS is not None
        assert len(VALID_TRANSITIONS) > 0

    def test_idle_to_commanded(self):
        """User command from IDLE should transition to COMMANDED."""
        key = (TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.COMMANDED

    def test_commanded_to_processing(self):
        """Agent progress from COMMANDED should transition to PROCESSING."""
        key = (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.PROGRESS)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.PROCESSING

    def test_commanded_to_awaiting_input(self):
        """Agent question from COMMANDED should transition to AWAITING_INPUT."""
        key = (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.QUESTION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.AWAITING_INPUT

    def test_commanded_to_complete(self):
        """Agent completion from COMMANDED should transition to COMPLETE."""
        key = (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.COMPLETION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.COMPLETE

    def test_processing_to_processing(self):
        """Agent progress from PROCESSING should stay in PROCESSING."""
        key = (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.PROGRESS)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.PROCESSING

    def test_processing_to_awaiting_input(self):
        """Agent question from PROCESSING should transition to AWAITING_INPUT."""
        key = (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.QUESTION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.AWAITING_INPUT

    def test_processing_to_complete(self):
        """Agent completion from PROCESSING should transition to COMPLETE."""
        key = (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.COMPLETION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.COMPLETE

    def test_awaiting_input_to_processing(self):
        """User answer from AWAITING_INPUT should transition to PROCESSING."""
        key = (TaskState.AWAITING_INPUT, TurnActor.USER, TurnIntent.ANSWER)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == TaskState.PROCESSING


class TestValidateTransition:
    """Tests for validate_transition function."""

    def test_valid_transition_returns_valid_result(self):
        """Valid transition should return valid=True."""
        result = validate_transition(
            TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND
        )
        assert result.valid is True
        assert result.from_state == TaskState.IDLE
        assert result.to_state == TaskState.COMMANDED
        assert result.trigger == "user:command"

    def test_invalid_transition_returns_invalid_result(self):
        """Invalid transition should return valid=False."""
        # Agent can't act from IDLE state
        result = validate_transition(
            TaskState.IDLE, TurnActor.AGENT, TurnIntent.PROGRESS
        )
        assert result.valid is False
        assert result.from_state == TaskState.IDLE
        assert result.to_state == TaskState.IDLE  # Unchanged
        assert "Invalid transition" in result.reason

    def test_user_command_while_awaiting_returns_special_reason(self):
        """User command while AWAITING_INPUT should return special reason."""
        result = validate_transition(
            TaskState.AWAITING_INPUT, TurnActor.USER, TurnIntent.COMMAND
        )
        assert result.valid is False
        assert "should create new task" in result.reason

    def test_agent_action_from_idle_invalid(self):
        """Agent actions from IDLE should be invalid."""
        for intent in [TurnIntent.PROGRESS, TurnIntent.QUESTION, TurnIntent.COMPLETION]:
            result = validate_transition(TaskState.IDLE, TurnActor.AGENT, intent)
            assert result.valid is False

    def test_complete_state_is_terminal(self):
        """No transitions should be valid from COMPLETE state."""
        for actor in [TurnActor.USER, TurnActor.AGENT]:
            for intent in TurnIntent:
                result = validate_transition(TaskState.COMPLETE, actor, intent)
                assert result.valid is False, f"Unexpected valid transition from COMPLETE: {actor.value}:{intent.value}"


class TestStateMachineClass:
    """Tests for StateMachine class."""

    @pytest.fixture
    def state_machine(self):
        """Create a StateMachine instance."""
        return StateMachine()

    def test_transition_valid(self, state_machine):
        """Transition method should process valid transitions."""
        result = state_machine.transition(
            TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND
        )
        assert result.valid is True
        assert result.to_state == TaskState.COMMANDED

    def test_transition_invalid_logs_warning(self, state_machine, caplog):
        """Transition method should log warning for invalid transitions."""
        import logging
        caplog.set_level(logging.WARNING)

        result = state_machine.transition(
            TaskState.IDLE, TurnActor.AGENT, TurnIntent.PROGRESS
        )
        assert result.valid is False
        assert "Invalid state transition rejected" in caplog.text

    def test_can_transition_valid(self, state_machine):
        """can_transition should return True for valid transitions."""
        assert state_machine.can_transition(
            TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND
        ) is True

    def test_can_transition_invalid(self, state_machine):
        """can_transition should return False for invalid transitions."""
        assert state_machine.can_transition(
            TaskState.IDLE, TurnActor.AGENT, TurnIntent.PROGRESS
        ) is False


class TestGetValidTransitionsFrom:
    """Tests for get_valid_transitions_from function."""

    def test_get_from_idle(self):
        """Get valid transitions from IDLE state."""
        transitions = get_valid_transitions_from(TaskState.IDLE)
        assert len(transitions) == 1
        actor, intent, to_state = transitions[0]
        assert actor == TurnActor.USER
        assert intent == TurnIntent.COMMAND
        assert to_state == TaskState.COMMANDED

    def test_get_from_commanded(self):
        """Get valid transitions from COMMANDED state."""
        transitions = get_valid_transitions_from(TaskState.COMMANDED)
        assert len(transitions) == 3
        # All should be agent actions
        for actor, intent, to_state in transitions:
            assert actor == TurnActor.AGENT

    def test_get_from_processing(self):
        """Get valid transitions from PROCESSING state."""
        transitions = get_valid_transitions_from(TaskState.PROCESSING)
        assert len(transitions) == 3

    def test_get_from_awaiting_input(self):
        """Get valid transitions from AWAITING_INPUT state."""
        transitions = get_valid_transitions_from(TaskState.AWAITING_INPUT)
        assert len(transitions) == 1
        actor, intent, to_state = transitions[0]
        assert actor == TurnActor.USER
        assert intent == TurnIntent.ANSWER

    def test_get_from_complete(self):
        """Get valid transitions from COMPLETE state (should be empty)."""
        transitions = get_valid_transitions_from(TaskState.COMPLETE)
        assert len(transitions) == 0


class TestIsTerminalState:
    """Tests for is_terminal_state function."""

    def test_complete_is_terminal(self):
        """COMPLETE should be a terminal state."""
        assert is_terminal_state(TaskState.COMPLETE) is True

    def test_idle_is_not_terminal(self):
        """IDLE should not be a terminal state."""
        assert is_terminal_state(TaskState.IDLE) is False

    def test_commanded_is_not_terminal(self):
        """COMMANDED should not be a terminal state."""
        assert is_terminal_state(TaskState.COMMANDED) is False

    def test_processing_is_not_terminal(self):
        """PROCESSING should not be a terminal state."""
        assert is_terminal_state(TaskState.PROCESSING) is False

    def test_awaiting_input_is_not_terminal(self):
        """AWAITING_INPUT should not be a terminal state."""
        assert is_terminal_state(TaskState.AWAITING_INPUT) is False


class TestTransitionResultDataclass:
    """Tests for TransitionResult dataclass."""

    def test_transition_result_creation(self):
        """TransitionResult should store all fields correctly."""
        result = TransitionResult(
            valid=True,
            from_state=TaskState.IDLE,
            to_state=TaskState.COMMANDED,
            reason="Valid transition",
            trigger="user:command",
        )
        assert result.valid is True
        assert result.from_state == TaskState.IDLE
        assert result.to_state == TaskState.COMMANDED
        assert result.reason == "Valid transition"
        assert result.trigger == "user:command"

    def test_transition_result_optional_trigger(self):
        """TransitionResult should allow None for trigger."""
        result = TransitionResult(
            valid=False,
            from_state=TaskState.IDLE,
            to_state=TaskState.IDLE,
            reason="Invalid",
        )
        assert result.trigger is None


class TestStateMachineStateless:
    """Tests to verify stateless/reentrant design."""

    def test_multiple_transitions_same_machine(self):
        """StateMachine should handle multiple transitions without state."""
        sm = StateMachine()

        # First transition
        r1 = sm.transition(TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND)
        assert r1.to_state == TaskState.COMMANDED

        # Second transition (with different starting state)
        r2 = sm.transition(TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.QUESTION)
        assert r2.to_state == TaskState.AWAITING_INPUT

        # First transition again (should produce same result)
        r3 = sm.transition(TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND)
        assert r3.to_state == r1.to_state

    def test_validate_transition_is_pure(self):
        """validate_transition should be a pure function."""
        # Call multiple times with same inputs
        results = [
            validate_transition(TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.PROGRESS)
            for _ in range(5)
        ]

        # All results should be identical
        for result in results:
            assert result.valid == results[0].valid
            assert result.to_state == results[0].to_state
            assert result.reason == results[0].reason
