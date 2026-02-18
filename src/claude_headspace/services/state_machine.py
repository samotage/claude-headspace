"""State machine service for command state transitions."""

import logging
from dataclasses import dataclass
from typing import Optional

from ..models.command import CommandState
from ..models.turn import TurnActor, TurnIntent

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    """Raised when a state transition violates the state machine rules."""

    def __init__(self, result: "TransitionResult"):
        self.result = result
        super().__init__(result.reason)


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""

    valid: bool
    from_state: CommandState
    to_state: CommandState
    reason: str
    trigger: Optional[str] = None


# Valid transitions mapping
# Format: {(from_state, actor, intent): to_state}
#
# Audit methodology: All 60 possible (state, actor, intent) combinations
# (5 states x 2 actors x 6 intents) were evaluated. Each is classified as:
#   (a) defined below — valid transition
#   (b) handled specially in validate_transition() — e.g., AWAITING_INPUT + USER:COMMAND
#   (c) invalid — kept as InvalidTransitionError (callers handle gracefully)
#
# Defensive transitions added for edge cases that can occur in production:
#   - IDLE + AGENT:* — agent output before user command is processed (race/resumption)
#   - COMMANDED + USER:COMMAND — user follow-up before agent responds
#   - PROCESSING + USER:COMMAND — user sends new command while agent works
VALID_TRANSITIONS: dict[tuple[CommandState, TurnActor, TurnIntent], CommandState] = {
    # From IDLE: User commands start a command
    (CommandState.IDLE, TurnActor.USER, TurnIntent.COMMAND): CommandState.COMMANDED,
    # From IDLE: Agent output before user command processed (race condition, session resumption)
    (CommandState.IDLE, TurnActor.AGENT, TurnIntent.PROGRESS): CommandState.PROCESSING,
    (CommandState.IDLE, TurnActor.AGENT, TurnIntent.QUESTION): CommandState.AWAITING_INPUT,
    (CommandState.IDLE, TurnActor.AGENT, TurnIntent.COMPLETION): CommandState.COMPLETE,
    (CommandState.IDLE, TurnActor.AGENT, TurnIntent.END_OF_COMMAND): CommandState.COMPLETE,
    # From COMMANDED: Agent responds
    (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.PROGRESS): CommandState.PROCESSING,
    (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.QUESTION): CommandState.AWAITING_INPUT,
    (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.COMPLETION): CommandState.COMPLETE,
    (CommandState.COMMANDED, TurnActor.AGENT, TurnIntent.END_OF_COMMAND): CommandState.COMPLETE,
    # From COMMANDED: User sends follow-up command before agent responds
    (CommandState.COMMANDED, TurnActor.USER, TurnIntent.COMMAND): CommandState.COMMANDED,
    # From PROCESSING: Agent continues or asks/completes
    (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.PROGRESS): CommandState.PROCESSING,
    (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.QUESTION): CommandState.AWAITING_INPUT,
    (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.COMPLETION): CommandState.COMPLETE,
    (CommandState.PROCESSING, TurnActor.AGENT, TurnIntent.END_OF_COMMAND): CommandState.COMPLETE,
    # From PROCESSING: User confirms/approves (continues same command)
    (CommandState.PROCESSING, TurnActor.USER, TurnIntent.ANSWER): CommandState.PROCESSING,
    # From PROCESSING: User sends new command while processing
    (CommandState.PROCESSING, TurnActor.USER, TurnIntent.COMMAND): CommandState.PROCESSING,
    # From AWAITING_INPUT: User answers and agent resumes
    (CommandState.AWAITING_INPUT, TurnActor.USER, TurnIntent.ANSWER): CommandState.PROCESSING,
    # From AWAITING_INPUT: Agent asks follow-up question or provides progress
    # (e.g., background agent completes, main agent outputs additional text)
    (CommandState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.QUESTION): CommandState.AWAITING_INPUT,
    (CommandState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.PROGRESS): CommandState.AWAITING_INPUT,
    # From AWAITING_INPUT: Agent completes while awaiting (session_end forced completion)
    (CommandState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.COMPLETION): CommandState.COMPLETE,
    (CommandState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.END_OF_COMMAND): CommandState.COMPLETE,
    # Special case: User command while awaiting input starts NEW command
    # This is handled specially in validate_transition()
}


def validate_transition(
    from_state: CommandState,
    actor: TurnActor,
    intent: TurnIntent,
) -> TransitionResult:
    """
    Validate a proposed state transition.

    This function is pure and stateless - it only checks if the transition
    is valid according to the state machine rules.

    Args:
        from_state: Current command state
        actor: Who is producing the turn
        intent: The detected intent of the turn

    Returns:
        TransitionResult indicating if the transition is valid and why
    """
    trigger = f"{actor.value}:{intent.value}"

    # Special case: User command while awaiting_input
    # This should create a NEW command, not transition the current one
    if (
        from_state == CommandState.AWAITING_INPUT
        and actor == TurnActor.USER
        and intent == TurnIntent.COMMAND
    ):
        return TransitionResult(
            valid=False,
            from_state=from_state,
            to_state=from_state,  # No transition
            reason="User command while awaiting_input - should create new command",
            trigger=trigger,
        )

    # Check the transition mapping
    key = (from_state, actor, intent)
    if key in VALID_TRANSITIONS:
        to_state = VALID_TRANSITIONS[key]
        return TransitionResult(
            valid=True,
            from_state=from_state,
            to_state=to_state,
            reason="Valid transition",
            trigger=trigger,
        )

    # Invalid transition
    return TransitionResult(
        valid=False,
        from_state=from_state,
        to_state=from_state,  # State unchanged
        reason=f"Invalid transition: {from_state.value} + {trigger}",
        trigger=trigger,
    )


def get_valid_transitions_from(state: CommandState) -> list[tuple[TurnActor, TurnIntent, CommandState]]:
    """
    Get all valid transitions from a given state.

    Useful for debugging and documentation.

    Args:
        state: The starting state

    Returns:
        List of (actor, intent, to_state) tuples for valid transitions
    """
    result = []
    for (from_state, actor, intent), to_state in VALID_TRANSITIONS.items():
        if from_state == state:
            result.append((actor, intent, to_state))
    return result


def is_terminal_state(state: CommandState) -> bool:
    """
    Check if a state is terminal (no valid outgoing transitions).

    Args:
        state: The state to check

    Returns:
        True if the state is terminal
    """
    return state == CommandState.COMPLETE
