"""Tests for state machine service."""

import pytest

from claude_headspace.models.command import CommandState
from claude_headspace.models.turn import TurnActor, TurnIntent
from claude_headspace.services.state_machine import (
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
        key = (CommandState.IDLE, TurnActor.USER, TurnIntent.COMMAND)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.COMMANDED

    def test_commanded_to_processing(self):
        """Agent progress from COMMANDED should transition to PROCESSING."""
        key = (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.PROGRESS)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.PROCESSING

    def test_commanded_to_awaiting_input(self):
        """Agent question from COMMANDED should transition to AWAITING_INPUT."""
        key = (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.QUESTION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.AWAITING_INPUT

    def test_commanded_to_complete(self):
        """Agent completion from COMMANDED should transition to COMPLETE."""
        key = (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.COMPLETION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.COMPLETE

    def test_processing_to_processing(self):
        """Agent progress from PROCESSING should stay in PROCESSING."""
        key = (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.PROGRESS)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.PROCESSING

    def test_processing_to_awaiting_input(self):
        """Agent question from PROCESSING should transition to AWAITING_INPUT."""
        key = (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.QUESTION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.AWAITING_INPUT

    def test_processing_to_complete(self):
        """Agent completion from PROCESSING should transition to COMPLETE."""
        key = (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.COMPLETION)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.COMPLETE

    def test_awaiting_input_to_processing(self):
        """User answer from AWAITING_INPUT should transition to PROCESSING."""
        key = (CommandState.AWAITING_INPUT, TurnActor.USER, TurnIntent.ANSWER)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.PROCESSING


class TestValidateTransition:
    """Tests for validate_transition function."""

    def test_valid_transition_returns_valid_result(self):
        """Valid transition should return valid=True."""
        result = validate_transition(
            CommandState.IDLE, TurnActor.USER, TurnIntent.COMMAND
        )
        assert result.valid is True
        assert result.from_state == CommandState.IDLE
        assert result.to_state == CommandState.COMMANDED
        assert result.trigger == "user:command"

    def test_invalid_transition_returns_invalid_result(self):
        """Invalid transition should return valid=False."""
        # User can't answer from IDLE state (no question asked)
        result = validate_transition(
            CommandState.IDLE, TurnActor.USER, TurnIntent.ANSWER
        )
        assert result.valid is False
        assert result.from_state == CommandState.IDLE
        assert result.to_state == CommandState.IDLE  # Unchanged
        assert "Invalid transition" in result.reason

    def test_user_command_while_awaiting_returns_special_reason(self):
        """User command while AWAITING_INPUT should return special reason."""
        result = validate_transition(
            CommandState.AWAITING_INPUT, TurnActor.USER, TurnIntent.COMMAND
        )
        assert result.valid is False
        assert "should create new command" in result.reason

    def test_agent_action_from_idle_valid(self):
        """Agent actions from IDLE should be valid (defensive transitions for race/resumption)."""
        expected = {
            TurnIntent.PROGRESS: CommandState.PROCESSING,
            TurnIntent.QUESTION: CommandState.AWAITING_INPUT,
            TurnIntent.COMPLETION: CommandState.COMPLETE,
            TurnIntent.END_OF_COMMAND: CommandState.COMPLETE,
        }
        for intent, expected_state in expected.items():
            result = validate_transition(CommandState.IDLE, TurnActor.AGENT, intent)
            assert result.valid is True, f"Expected valid for IDLE + AGENT:{intent.value}"
            assert result.to_state == expected_state

    def test_complete_state_is_terminal(self):
        """No transitions should be valid from COMPLETE state."""
        for actor in [TurnActor.USER, TurnActor.AGENT]:
            for intent in TurnIntent:
                result = validate_transition(CommandState.COMPLETE, actor, intent)
                assert result.valid is False, f"Unexpected valid transition from COMPLETE: {actor.value}:{intent.value}"


class TestGetValidTransitionsFrom:
    """Tests for get_valid_transitions_from function."""

    def test_get_from_idle(self):
        """Get valid transitions from IDLE state."""
        transitions = get_valid_transitions_from(CommandState.IDLE)
        assert len(transitions) == 5  # USER:COMMAND + 4 AGENT defensive transitions
        # Verify USER:COMMAND is present
        user_transitions = [(a, i, s) for a, i, s in transitions if a == TurnActor.USER]
        assert len(user_transitions) == 1
        actor, intent, to_state = user_transitions[0]
        assert actor == TurnActor.USER
        assert intent == TurnIntent.COMMAND
        assert to_state == CommandState.COMMANDED

    def test_get_from_commanded(self):
        """Get valid transitions from COMMANDED state."""
        transitions = get_valid_transitions_from(CommandState.COMMANDED)
        assert len(transitions) == 5  # 4 agent actions + USER:COMMAND follow-up

    def test_get_from_processing(self):
        """Get valid transitions from PROCESSING state."""
        transitions = get_valid_transitions_from(CommandState.PROCESSING)
        assert len(transitions) == 6  # 4 agent actions + USER:ANSWER + USER:COMMAND

    def test_get_from_awaiting_input(self):
        """Get valid transitions from AWAITING_INPUT state."""
        transitions = get_valid_transitions_from(CommandState.AWAITING_INPUT)
        assert len(transitions) == 5  # USER ANSWER, AGENT QUESTION, AGENT PROGRESS, AGENT COMPLETION, AGENT END_OF_COMMAND
        intents = {(a.value, i.value) for a, i, _ in transitions}
        assert ("user", "answer") in intents
        assert ("agent", "question") in intents
        assert ("agent", "progress") in intents
        assert ("agent", "completion") in intents
        assert ("agent", "end_of_command") in intents

    def test_get_from_complete(self):
        """Get valid transitions from COMPLETE state (should be empty)."""
        transitions = get_valid_transitions_from(CommandState.COMPLETE)
        assert len(transitions) == 0


class TestIsTerminalState:
    """Tests for is_terminal_state function."""

    def test_complete_is_terminal(self):
        """COMPLETE should be a terminal state."""
        assert is_terminal_state(CommandState.COMPLETE) is True

    def test_idle_is_not_terminal(self):
        """IDLE should not be a terminal state."""
        assert is_terminal_state(CommandState.IDLE) is False

    def test_commanded_is_not_terminal(self):
        """COMMANDED should not be a terminal state."""
        assert is_terminal_state(CommandState.COMMANDED) is False

    def test_processing_is_not_terminal(self):
        """PROCESSING should not be a terminal state."""
        assert is_terminal_state(CommandState.PROCESSING) is False

    def test_awaiting_input_is_not_terminal(self):
        """AWAITING_INPUT should not be a terminal state."""
        assert is_terminal_state(CommandState.AWAITING_INPUT) is False


class TestTransitionResultDataclass:
    """Tests for TransitionResult dataclass."""

    def test_transition_result_creation(self):
        """TransitionResult should store all fields correctly."""
        result = TransitionResult(
            valid=True,
            from_state=CommandState.IDLE,
            to_state=CommandState.COMMANDED,
            reason="Valid transition",
            trigger="user:command",
        )
        assert result.valid is True
        assert result.from_state == CommandState.IDLE
        assert result.to_state == CommandState.COMMANDED
        assert result.reason == "Valid transition"
        assert result.trigger == "user:command"

    def test_transition_result_optional_trigger(self):
        """TransitionResult should allow None for trigger."""
        result = TransitionResult(
            valid=False,
            from_state=CommandState.IDLE,
            to_state=CommandState.IDLE,
            reason="Invalid",
        )
        assert result.trigger is None


class TestValidateTransitionPure:
    """Tests to verify stateless/pure design."""

    def test_validate_transition_is_pure(self):
        """validate_transition should be a pure function."""
        # Call multiple times with same inputs
        results = [
            validate_transition(CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.PROGRESS)
            for _ in range(5)
        ]

        # All results should be identical
        for result in results:
            assert result.valid == results[0].valid
            assert result.to_state == results[0].to_state
            assert result.reason == results[0].reason


class TestEndOfCommandTransitions:
    """Tests for END_OF_COMMAND transitions."""

    def test_end_of_command_from_commanded(self):
        """Agent END_OF_COMMAND from COMMANDED should transition to COMPLETE."""
        key = (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.END_OF_COMMAND)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.COMPLETE

    def test_end_of_command_from_processing(self):
        """Agent END_OF_COMMAND from PROCESSING should transition to COMPLETE."""
        key = (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.END_OF_COMMAND)
        assert key in VALID_TRANSITIONS
        assert VALID_TRANSITIONS[key] == CommandState.COMPLETE

    def test_end_of_command_validate_from_commanded(self):
        """validate_transition should accept END_OF_COMMAND from COMMANDED."""
        result = validate_transition(
            CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.END_OF_COMMAND
        )
        assert result.valid is True
        assert result.to_state == CommandState.COMPLETE
        assert result.trigger == "agent:end_of_command"

    def test_end_of_command_validate_from_processing(self):
        """validate_transition should accept END_OF_COMMAND from PROCESSING."""
        result = validate_transition(
            CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.END_OF_COMMAND
        )
        assert result.valid is True
        assert result.to_state == CommandState.COMPLETE

    def test_end_of_command_valid_from_idle(self):
        """END_OF_COMMAND from IDLE should be valid (defensive transition)."""
        result = validate_transition(
            CommandState.IDLE, TurnActor.AGENT, TurnIntent.END_OF_COMMAND
        )
        assert result.valid is True
        assert result.to_state == CommandState.COMPLETE

    def test_end_of_command_invalid_from_complete(self):
        """END_OF_COMMAND from COMPLETE should be invalid."""
        result = validate_transition(
            CommandState.COMPLETE, TurnActor.AGENT, TurnIntent.END_OF_COMMAND
        )
        assert result.valid is False

    def test_commanded_now_has_five_transitions(self):
        """COMMANDED should now have 5 valid transitions (4 agent + USER:COMMAND follow-up)."""
        transitions = get_valid_transitions_from(CommandState.COMMANDED)
        assert len(transitions) == 5

    def test_processing_now_has_six_transitions(self):
        """PROCESSING should have 6 valid transitions (4 agent + USER:ANSWER + USER:COMMAND)."""
        transitions = get_valid_transitions_from(CommandState.PROCESSING)
        assert len(transitions) == 6

    def test_user_answer_while_processing_stays_processing(self):
        """User ANSWER while PROCESSING should stay in PROCESSING (confirmation/approval)."""
        result = validate_transition(
            CommandState.PROCESSING, TurnActor.USER, TurnIntent.ANSWER
        )
        assert result.valid is True
        assert result.to_state == CommandState.PROCESSING
        assert result.trigger == "user:answer"
