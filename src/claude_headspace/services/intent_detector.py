"""Intent detector service for classifying turn intent."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from ..models.task import TaskState
from ..models.turn import TurnActor, TurnIntent
from .prompt_registry import build_prompt

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

# Completion opener patterns — "Done." / "Complete." etc. at start of a line, followed by detail
# Uses (?m) so ^ matches at each line boundary (not just start of string),
# because the tail contains multiple lines and "Done." may not be the first.
COMPLETION_OPENER_PATTERNS = [
    r"(?im)^(?:done|complete|finished|all (?:done|set|finished))[\.!]\s+\S",
]

# End-of-task: summary openers
END_OF_TASK_SUMMARY_PATTERNS = [
    r"(?i)(?:here'?s a summary of (?:what|the changes|everything))",
    r"(?i)(?:here are the (?:changes|updates|modifications) I (?:made|implemented))",
    r"(?i)(?:to (?:summarise|summarize|recap)|in summary)",
    r"(?i)(?:the following files were (?:modified|created|updated|changed):)",
]

# End-of-task: soft-close offers (open-ended, work is done)
END_OF_TASK_SOFT_CLOSE_PATTERNS = [
    r"(?i)(?:let me know if you'?d like any (?:adjustments|changes|modifications))",
    r"(?i)(?:let me know if there'?s anything else)",
    r"(?i)(?:let me know if you (?:need|want) (?:anything|any) (?:else|other|further))",
    r"(?i)(?:feel free to (?:test|try|review|check))",
    r"(?i)(?:is there anything else you'?d like me to)",
]

# End-of-task: capability handoff
END_OF_TASK_HANDOFF_PATTERNS = [
    r"(?i)(?:you (?:can|should) now (?:be able to )?)",
    r"(?i)(?:everything (?:should be|is) (?:working|in place|ready|set up))",
]

# Continuation patterns (NEGATIVE guard -- vetoes end-of-task)
CONTINUATION_PATTERNS = [
    r"(?i)(?:next I'?ll|now I (?:need to|will|'ll)|moving on to|let me also)",
    r"(?i)(?:I still need to|remaining (?:work|tasks|steps)|TODO)",
    r"(?i)(?:should I (?:proceed|continue|go ahead)|want me to continue)",
    r"(?i)(?:before I can (?:finish|complete)|there'?s (?:one|another) more)",
    r"(?i)(?:working on|starting|beginning|in progress)",
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


def _detect_end_of_task(tail: str, has_continuation: bool) -> Optional[IntentResult]:
    """
    Detect end-of-task in the tail using multi-signal scoring.

    Returns IntentResult with END_OF_TASK intent, or None if not detected.
    Confidence levels:
      - Summary + soft-close: 0.95
      - Summary + handoff: 0.95
      - Soft-close alone: 0.7
      - Summary alone: 0.7
      - Handoff alone: 0.7

    Returns None if continuation patterns were found (has_continuation=True).
    """
    if has_continuation:
        return None

    has_summary = _match_patterns(tail, END_OF_TASK_SUMMARY_PATTERNS)
    has_soft_close = _match_patterns(tail, END_OF_TASK_SOFT_CLOSE_PATTERNS)
    has_handoff = _match_patterns(tail, END_OF_TASK_HANDOFF_PATTERNS)

    if has_summary and (has_soft_close or has_handoff):
        return IntentResult(TurnIntent.END_OF_TASK, 0.95, matched_pattern=has_summary)
    elif has_soft_close:
        return IntentResult(TurnIntent.END_OF_TASK, 0.7, matched_pattern=has_soft_close)
    elif has_summary:
        return IntentResult(TurnIntent.END_OF_TASK, 0.7, matched_pattern=has_summary)
    elif has_handoff:
        return IntentResult(TurnIntent.END_OF_TASK, 0.7, matched_pattern=has_handoff)

    return None


def _detect_completion_opener(tail: str, has_continuation: bool) -> Optional[IntentResult]:
    """
    Detect completion opener at the start of the tail.

    Recognises "Done.", "Complete.", "Finished.", etc. at the **start** of a
    message even when followed by additional detail text.  This catches the
    common real-world pattern where Claude Code says "Done. All files now ..."
    which the standalone COMPLETION_PATTERNS miss because they require the
    word to be the entire text.

    Returns IntentResult with COMPLETION intent, or None if not detected.
    Confidence levels:
      - Opener alone: 0.75
      - Opener + soft-close / summary / handoff signal: 0.9

    Returns None if continuation patterns were found (has_continuation=True).
    """
    if has_continuation:
        return None

    matched = _match_patterns(tail, COMPLETION_OPENER_PATTERNS)
    if not matched:
        return None

    # Check for additional completion signals to boost confidence
    has_soft_close = _match_patterns(tail, END_OF_TASK_SOFT_CLOSE_PATTERNS)
    has_summary = _match_patterns(tail, END_OF_TASK_SUMMARY_PATTERNS)
    has_handoff = _match_patterns(tail, END_OF_TASK_HANDOFF_PATTERNS)

    if has_soft_close or has_summary or has_handoff:
        confidence = 0.9
    else:
        confidence = 0.75

    return IntentResult(
        intent=TurnIntent.COMPLETION,
        confidence=confidence,
        matched_pattern=matched,
    )


def _infer_completion_classification(
    tail: str, inference_service: Any
) -> Optional[IntentResult]:
    """LLM fallback for ambiguous agent output classification."""
    prompt = build_prompt("completion_classification", tail=tail)

    try:
        result = inference_service.infer(
            level="turn",
            purpose="completion_classification",
            input_text=prompt,
        )
        letter = result.text.strip().upper()[:1]
        mapping = {
            "A": IntentResult(TurnIntent.END_OF_TASK, 0.85),
            "B": IntentResult(TurnIntent.PROGRESS, 0.85),
            "C": IntentResult(TurnIntent.QUESTION, 0.85),
            "D": IntentResult(TurnIntent.QUESTION, 0.85),
        }
        return mapping.get(letter)
    except Exception:
        return None


def detect_agent_intent(
    text: Optional[str], inference_service: Any = None
) -> IntentResult:
    """
    Detect the intent of an agent turn using regex pattern matching.

    Pipeline:
    1. Return PROGRESS(0.5) for empty/None text
    2. Strip code blocks from text
    3. Extract tail (last 15 non-empty lines)
    4. Check continuation guard
    5. Tail: END_OF_TASK detection (before QUESTION to catch soft-close offers)
    6. Tail: QUESTION -> BLOCKED -> COMPLETION (confidence=1.0)
    6.5. Tail: COMPLETION OPENER detection (e.g. "Done. All files...")
    7. Full text: END_OF_TASK detection (lower confidence)
    8. Full text: QUESTION -> BLOCKED -> COMPLETION (confidence=0.8)
    9. Optional inference fallback for ambiguous cases
    10. Default: PROGRESS (confidence=0.5)

    Args:
        text: The text content of the agent's turn. May be None or empty.
        inference_service: Optional inference service for LLM fallback.

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

    # Check continuation guard once
    has_continuation = bool(_match_patterns(tail, CONTINUATION_PATTERNS))

    # Phase 0: End-of-task detection on tail (before QUESTION — catches soft-close offers)
    eot_result = _detect_end_of_task(tail, has_continuation)
    if eot_result:
        logger.debug(
            f"Detected END_OF_TASK intent in tail: pattern={eot_result.matched_pattern}"
        )
        return eot_result

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

    # Phase 1.5: Completion opener on tail (e.g. "Done. All files updated...")
    opener_result = _detect_completion_opener(tail, has_continuation)
    if opener_result:
        logger.debug(
            f"Detected COMPLETION opener in tail: pattern={opener_result.matched_pattern}"
        )
        return opener_result

    # Phase 2: End-of-task on full text (lower confidence)
    full_tail = _extract_tail(cleaned, max_lines=30)
    eot_full = _detect_end_of_task(full_tail, has_continuation)
    if eot_full:
        eot_full.confidence = max(0.6, eot_full.confidence - 0.2)
        logger.debug(
            f"Detected END_OF_TASK intent in full text: pattern={eot_full.matched_pattern}"
        )
        return eot_full

    # Phase 3: Match against full cleaned text (contextual confidence)
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

    # Phase 4: Optional inference fallback for ambiguous cases
    if inference_service and getattr(inference_service, "is_available", False):
        inferred = _infer_completion_classification(tail, inference_service)
        if inferred:
            logger.debug(
                f"Inference fallback classified as {inferred.intent.value}"
            )
            return inferred

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
