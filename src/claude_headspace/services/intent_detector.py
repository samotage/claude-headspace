"""Intent detector service for classifying turn intent."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ..models.task import TaskState
from ..models.turn import TurnActor, TurnIntent

logger = logging.getLogger(__name__)


# Regex patterns for question detection
QUESTION_PATTERNS = [
    # Direct question mark at end (but not in code blocks or URLs)
    r"(?<![`\"\'/])\?\s*$",
    # Common question phrases
    r"(?i)^(?:would you like|should i|do you want|can i|shall i|may i)",
    r"(?i)(?:would you like|should i|do you want|can i|shall i|may i)[\s\S]*\?\s*$",
    # Clarifying questions
    r"(?i)(?:is that correct|does that (?:work|look|sound) (?:okay|good|right)|what do you think)",
    r"(?i)(?:let me know|please confirm|could you clarify|could you tell me)",
]

# Regex patterns for completion detection
COMPLETION_PATTERNS = [
    # Direct completion phrases
    r"(?i)^(?:done|complete|finished|all (?:done|set|finished))[\.!\s]*$",
    # Task completion phrases
    r"(?i)(?:i'?(?:ve|m) (?:finished|completed|done)|task (?:complete|finished|done))",
    r"(?i)(?:successfully (?:completed|finished)|changes (?:have been )?(?:made|applied|committed))",
    # Summary completion phrases
    r"(?i)(?:that'?s all|all changes|everything is|ready (?:to|for))",
    # Implementation complete phrases
    r"(?i)(?:implementation (?:is )?complete|feature (?:is )?(?:ready|done|complete))",
]


@dataclass
class IntentResult:
    """Result of intent detection."""

    intent: TurnIntent
    confidence: float
    matched_pattern: Optional[str] = None


def _match_patterns(text: str, patterns: list[str]) -> Optional[str]:
    """
    Check if text matches any pattern in the list.

    Args:
        text: Text to check
        patterns: List of regex patterns

    Returns:
        The matched pattern string, or None if no match
    """
    for pattern in patterns:
        if re.search(pattern, text):
            return pattern
    return None


def detect_agent_intent(text: Optional[str]) -> IntentResult:
    """
    Detect the intent of an agent turn using regex pattern matching.

    The detection priority is:
    1. Question patterns → TurnIntent.QUESTION
    2. Completion patterns → TurnIntent.COMPLETION
    3. Default → TurnIntent.PROGRESS

    Args:
        text: The text content of the agent's turn. May be None or empty.

    Returns:
        IntentResult with detected intent and confidence
    """
    # Handle missing/empty text - default to progress
    if not text or not text.strip():
        logger.debug("Empty/missing text, defaulting to PROGRESS")
        return IntentResult(
            intent=TurnIntent.PROGRESS,
            confidence=0.5,
            matched_pattern=None,
        )

    text = text.strip()

    # Check for question patterns first
    matched = _match_patterns(text, QUESTION_PATTERNS)
    if matched:
        logger.debug(f"Detected QUESTION intent: pattern={matched}")
        return IntentResult(
            intent=TurnIntent.QUESTION,
            confidence=1.0,
            matched_pattern=matched,
        )

    # Check for completion patterns
    matched = _match_patterns(text, COMPLETION_PATTERNS)
    if matched:
        logger.debug(f"Detected COMPLETION intent: pattern={matched}")
        return IntentResult(
            intent=TurnIntent.COMPLETION,
            confidence=1.0,
            matched_pattern=matched,
        )

    # Default to progress with lower confidence since no pattern matched
    logger.debug("No pattern matched, defaulting to PROGRESS")
    return IntentResult(
        intent=TurnIntent.PROGRESS,
        confidence=0.5,
        matched_pattern=None,
    )


def detect_user_intent(text: Optional[str], current_state: TaskState) -> IntentResult:
    """
    Detect the intent of a user turn based on the current task state.

    The logic is:
    - If current state is AWAITING_INPUT → TurnIntent.ANSWER (user is answering)
    - Otherwise → TurnIntent.COMMAND (user is giving a command)

    Args:
        text: The text content of the user's turn. May be None or empty.
        current_state: The current state of the task

    Returns:
        IntentResult with detected intent and confidence
    """
    # User intent is determined by current state, not text content
    # (In Epic 3, we might analyze text for more nuanced detection)

    if current_state == TaskState.AWAITING_INPUT:
        # User is answering a question
        logger.debug("User responding while AWAITING_INPUT -> ANSWER intent")
        return IntentResult(
            intent=TurnIntent.ANSWER,
            confidence=1.0,
            matched_pattern=None,
        )

    # User is giving a command (new task or continuation)
    logger.debug(f"User turn with state={current_state.value} -> COMMAND intent")
    return IntentResult(
        intent=TurnIntent.COMMAND,
        confidence=1.0,
        matched_pattern=None,
    )


def detect_intent(
    text: Optional[str],
    actor: TurnActor,
    current_state: TaskState,
) -> IntentResult:
    """
    Detect turn intent based on actor and current state.

    This is the main entry point that routes to the appropriate detector.

    Args:
        text: The text content of the turn
        actor: Who produced the turn (USER or AGENT)
        current_state: The current task state

    Returns:
        IntentResult with detected intent and confidence
    """
    if actor == TurnActor.USER:
        return detect_user_intent(text, current_state)
    else:
        return detect_agent_intent(text)
