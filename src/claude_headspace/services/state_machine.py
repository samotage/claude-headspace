"""State machine service for task state transitions."""

import logging
from dataclasses import dataclass
from typing import Optional

from ..models.task import TaskState
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
    from_state: TaskState
    to_state: TaskState
    reason: str
    trigger: Optional[str] = None


# Valid transitions mapping
# Format: {(from_state, actor, intent): to_state}
VALID_TRANSITIONS: dict[tuple[TaskState, TurnActor, TurnIntent], TaskState] = {
    # From IDLE: Only user commands can start a task
    (TaskState.IDLE, TurnActor.USER, TurnIntent.COMMAND): TaskState.COMMANDED,
    # From COMMANDED: Agent responds
    (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.PROGRESS): TaskState.PROCESSING,
    (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.QUESTION): TaskState.AWAITING_INPUT,
    (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.COMPLETION): TaskState.COMPLETE,
    (TaskState.COMMANDED, TurnActor.AGENT, TurnIntent.END_OF_TASK): TaskState.COMPLETE,
    # From PROCESSING: Agent continues or asks/completes
    (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.PROGRESS): TaskState.PROCESSING,
    (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.QUESTION): TaskState.AWAITING_INPUT,
    (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.COMPLETION): TaskState.COMPLETE,
    (TaskState.PROCESSING, TurnActor.AGENT, TurnIntent.END_OF_TASK): TaskState.COMPLETE,
    # From PROCESSING: User confirms/approves (continues same task)
    (TaskState.PROCESSING, TurnActor.USER, TurnIntent.ANSWER): TaskState.PROCESSING,
    # From AWAITING_INPUT: User answers and agent resumes
    (TaskState.AWAITING_INPUT, TurnActor.USER, TurnIntent.ANSWER): TaskState.PROCESSING,
    # From AWAITING_INPUT: Agent asks follow-up question or provides progress
    # (e.g., background Task agent completes, main agent outputs additional text)
    (TaskState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.QUESTION): TaskState.AWAITING_INPUT,
    (TaskState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.PROGRESS): TaskState.AWAITING_INPUT,
    # From AWAITING_INPUT: Agent completes while awaiting (session_end forced completion)
    (TaskState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.COMPLETION): TaskState.COMPLETE,
    (TaskState.AWAITING_INPUT, TurnActor.AGENT, TurnIntent.END_OF_TASK): TaskState.COMPLETE,
    # Special case: User command while awaiting input starts NEW task
    # This is handled specially in validate_transition()
}


def validate_transition(
    from_state: TaskState,
    actor: TurnActor,
    intent: TurnIntent,
) -> TransitionResult:
    """
    Validate a proposed state transition.

    This function is pure and stateless - it only checks if the transition
    is valid according to the state machine rules.

    Args:
        from_state: Current task state
        actor: Who is producing the turn
        intent: The detected intent of the turn

    Returns:
        TransitionResult indicating if the transition is valid and why
    """
    trigger = f"{actor.value}:{intent.value}"

    # Special case: User command while awaiting_input
    # This should create a NEW task, not transition the current one
    if (
        from_state == TaskState.AWAITING_INPUT
        and actor == TurnActor.USER
        and intent == TurnIntent.COMMAND
    ):
        return TransitionResult(
            valid=False,
            from_state=from_state,
            to_state=from_state,  # No transition
            reason="User command while awaiting_input - should create new task",
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


def get_valid_transitions_from(state: TaskState) -> list[tuple[TurnActor, TurnIntent, TaskState]]:
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


def is_terminal_state(state: TaskState) -> bool:
    """
    Check if a state is terminal (no valid outgoing transitions).

    Args:
        state: The state to check

    Returns:
        True if the state is terminal
    """
    return state == TaskState.COMPLETE


