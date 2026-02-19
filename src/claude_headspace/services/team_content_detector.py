"""Detect team-internal content from sub-agent communications.

When a Claude Code agent spawns sub-agents (via Task tool / team creation),
their internal messages (SendMessage JSON, task-notification XML, shutdown
requests, idle notifications) leak into the parent agent's chat.

This module provides a pure function to detect such content so it can be
flagged with is_internal=True on Turn records at creation time.
"""

import json
import re

# Quick regex pre-screens (cheap to check before attempting JSON parse)
# Anchored to START of text: real protocol tags are always injected at the
# beginning of the message. Agents that DISCUSS these tags mid-text (in prose,
# backticks, or code) must not be flagged.
_XML_TAG_PATTERN = re.compile(r"^\s*<(task-notification|system-reminder)\b")
_JSON_TYPE_PATTERN = re.compile(r'"type"\s*:\s*"(message|broadcast|shutdown_request|shutdown_response|plan_approval_request|plan_approval_response|idle)"')

# JSON types that indicate team-internal communication
_INTERNAL_JSON_TYPES = frozenset({
    "message",
    "broadcast",
    "shutdown_request",
    "shutdown_response",
    "plan_approval_request",
    "plan_approval_response",
    "idle",
})


def is_team_internal_content(text: str | None) -> bool:
    """Detect whether text is team-internal sub-agent communication.

    Uses regex pre-screening + JSON parse validation to avoid false
    positives on normal user text that happens to contain keywords.

    Args:
        text: The turn text to check (may be None or empty)

    Returns:
        True if the text is team-internal content that should be hidden
    """
    if not text or not text.strip():
        return False

    stripped = text.strip()

    # Check for XML tags injected by Claude Code for sub-agent comms.
    # Anchored to start of text — real protocol tags always appear at position 0.
    # Agents discussing these tags mid-text are NOT internal content.
    if _XML_TAG_PATTERN.match(stripped):
        return True

    # Quick check: does it look like it might contain a JSON type field?
    if not _JSON_TYPE_PATTERN.search(stripped):
        return False

    # Attempt JSON parse to validate it's actually structured team comms
    # (not just user text that mentions "type": "message")
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return False

    if not isinstance(parsed, dict):
        return False

    msg_type = parsed.get("type")
    if msg_type not in _INTERNAL_JSON_TYPES:
        return False

    # Additional validation per type to reduce false positives
    if msg_type == "message":
        # SendMessage requires a recipient field
        return "recipient" in parsed
    elif msg_type == "broadcast":
        return "content" in parsed
    elif msg_type == "idle":
        return True
    elif msg_type in ("shutdown_request", "shutdown_response"):
        return True
    elif msg_type in ("plan_approval_request", "plan_approval_response"):
        return True

    return False
