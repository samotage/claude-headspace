"""Detect and filter special content from agent communications.

Provides pure functions for:
- Team-internal content detection (sub-agent comms -> is_internal=True)
- Skill/command expansion filtering (truncate expanded .md content)
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


# ---------------------------------------------------------------------------
# Skill / command expansion detection
# ---------------------------------------------------------------------------
# When a user invokes a slash command (e.g. /orch:40-test), Claude Code's
# Skill tool expands the .md file and fires user-prompt-submit with the FULL
# file content (often 5-15 KB).  Storing this verbatim pollutes the dashboard
# chat with raw command definitions.
#
# This filter detects expanded skill content and truncates it to the heading
# line.  It MUST be applied identically in both the hook receiver AND the
# transcript reconciler so that content hashes match and no duplicates arise.
# ---------------------------------------------------------------------------

_SKILL_HEADING_RE = re.compile(r"^#\s+.+")
_COMMAND_NAME_RE = re.compile(r"\*\*Command name:\*\*")


def filter_skill_expansion(text: str | None) -> str | None:
    """Truncate skill/command expansion content to just the heading line.

    Detects when ``text`` is the expanded content of a .md command file
    (as injected by Claude Code's Skill tool) and returns only the first
    heading line.  Non-expansion text is returned unchanged.

    The same function must be called in both the hook receiver and the
    transcript reconciler so that content hashes stay consistent.
    """
    if not text or len(text) < 500:
        return text

    stripped = text.strip()

    # Primary pattern: OTL command files start with "# NN: Title" and
    # contain "**Command name:**" within the first 300 chars.
    if _SKILL_HEADING_RE.match(stripped) and _COMMAND_NAME_RE.search(stripped[:300]):
        heading = stripped.split("\n", 1)[0].strip()
        return heading

    return text
