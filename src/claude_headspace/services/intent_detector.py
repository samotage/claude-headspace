"""Intent detector service for classifying turn intent."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ..models.task import TaskState
from ..models.turn import TurnActor, TurnIntent

logger = logging.getLogger(__name__)


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks (``` delimited) to prevent false positives."""
    return re.sub(r"```[\w]*\n.*?\n```", "", text, flags=re.DOTALL)


def _extract_tail(text: str, max_lines: int = 15) -> str:
    """Extract the last N non-empty lines from text.

    Agent output is often hundreds of lines; the actionable intent
    (questions, completion statements) is typically at the tail.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


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
    # Waiting for input (no question mark)
    r"(?i)\bwaiting for (?:your|the user'?s?) (?:response|input|answer|reply|decision|choice|feedback)\b",
    r"(?i)\bplease (?:respond|reply|answer|select|choose|provide|specify)\b",
    # Offering choices / seeking preference
    r"(?i)\b(?:want me to|how would you like me to|what'?s your preference)\b",
    r"(?i)\bwhich (?:approach|option|method) would you prefer\b",
    # Implicit waiting
    r"(?i)\bbefore I (?:proceed|continue|start)\b",
    # Needing input
    r"(?i)\bI need (?:to know|your (?:input|decision|confirmation))\b",
    r"(?i)\bdo you have a preference\b",
    # Presenting choices
    r"(?i)(?:here are (?:a few|some|the) options:|there are (?:two|three|several) approaches:)",
    # Multiple questions
    r"(?i)\bI have (?:a few|some|several) questions:\b",
]

# Regex patterns for blocked/error detection (mapped to QUESTION intent)
BLOCKED_PATTERNS = [
    r"(?i)(?:I don'?t have (?:permission|access) to|I can'?t access|this requires (?:authentication|authorization))",
    r"(?i)(?:^Error:|Failed to\b|Permission denied)",
    r"(?i)(?:I'?m unable to|I couldn'?t|I was unable to)",
]

# Regex patterns for completion detection
COMPLETION_PATTERNS = [
    # Direct completion phrases
    r"(?i)^(?:done|complete|finished|all (?:done|set|finished))[\.!\s]*$",
    # Task completion phrases
    r"(?i)(?:i'?(?:ve|m) (?:finished|completed|done)|task (?:complete|finished|done))",
    r"(?i)(?:successfully (?:completed|finished)|changes (?:have been )?(?:made|applied|committed))",
    # Summary completion phrases (tightened to avoid false positives)
    r"(?i)(?:that'?s all (?:the changes|I (?:need|have))|all changes (?:have been|are) (?:made|applied|committed|complete)|everything is (?:set|done|ready|in place|complete))[\.!\s]*$",
    # Implementation complete phrases
    r"(?i)(?:implementation (?:is )?complete|feature (?:is )?(?:ready|done|complete))",
    # Detailed completion phrases
    r"(?i)(?:I'?ve made the following changes:)",
    r"(?i)(?:all tests are passing)",
    r"(?i)(?:the PR is ready for review)",
    r"(?i)(?:committed to branch|changes have been pushed)",
    r"(?i)(?:here'?s a summary of what was done)",
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

    Pipeline:
    1. Return PROGRESS(0.5) for empty/None text
    2. Strip code blocks from text
    3. Extract tail (last 15 non-empty lines)
    4. Match tail against: QUESTION → BLOCKED → COMPLETION (confidence=1.0)
    5. If no tail match, match full cleaned text (confidence=0.8)
    6. Default: PROGRESS (confidence=0.5)

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

    # Preprocessing: strip code blocks, then extract tail
    cleaned = _strip_code_blocks(text.strip())
    tail = _extract_tail(cleaned)

    # Phase 1: Match against tail (high confidence)
    for patterns, intent in [
        (QUESTION_PATTERNS, TurnIntent.QUESTION),
        (BLOCKED_PATTERNS, TurnIntent.QUESTION),
        (COMPLETION_PATTERNS, TurnIntent.COMPLETION),
    ]:
        matched = _match_patterns(tail, patterns)
        if matched:
            logger.debug(f"Detected {intent.value} intent in tail: pattern={matched}")
            return IntentResult(
                intent=intent,
                confidence=1.0,
                matched_pattern=matched,
            )

    # Phase 2: Match against full cleaned text (contextual confidence)
    for patterns, intent in [
        (QUESTION_PATTERNS, TurnIntent.QUESTION),
        (BLOCKED_PATTERNS, TurnIntent.QUESTION),
        (COMPLETION_PATTERNS, TurnIntent.COMPLETION),
    ]:
        matched = _match_patterns(cleaned, patterns)
        if matched:
            logger.debug(
                f"Detected {intent.value} intent in full text: pattern={matched}"
            )
            return IntentResult(
                intent=intent,
                confidence=0.8,
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
