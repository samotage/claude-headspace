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
# Persona injection detection
# ---------------------------------------------------------------------------
# When inject_persona_skills() sends a priming message via tmux, Claude Code
# echoes it back as a user_prompt_submit.  If the skill_injection_pending flag
# was already consumed or never set (session lifecycle collision), the hook
# receiver can't distinguish the priming message from real user input.
#
# This content-based detector catches the persona priming message pattern
# regardless of flag state, providing defence-in-depth against duplicate
# persona injection turns creating phantom commands.
# ---------------------------------------------------------------------------

_PERSONA_PRIMING_PREFIX = "You are "
_PERSONA_PRIMING_MIDDLE = ". Read the following skill and experience"
_PERSONA_SKILLS_HEADING = "## Skills"
_GUARDRAILS_PREFIX = "## Platform Guardrails"


def is_persona_injection(text: str | None) -> bool:
    """Detect whether text is a persona injection priming message.

    Matches the pattern produced by skill_injector._compose_priming_message():
      "You are {name}. Read the following skill and experience..."
      followed by "## Skills"

    Also matches the guardrails-prefixed variant where the message starts
    with "## Platform Guardrails" followed by the persona priming pattern.

    Args:
        text: The prompt text to check

    Returns:
        True if the text matches the persona injection pattern
    """
    if not text or len(text) < 100:
        return False

    stripped = text.strip()

    # Direct persona priming (no guardrails prefix)
    if stripped.startswith(_PERSONA_PRIMING_PREFIX):
        first_500 = stripped[:500]
        return _PERSONA_PRIMING_MIDDLE in first_500 and _PERSONA_SKILLS_HEADING in stripped

    # Guardrails-prefixed variant: "## Platform Guardrails\n...\nYou are ..."
    # The guardrails block can be ~10 KB, so the persona priming markers
    # ("You are {name}. Read the following skill and experience …")
    # appear well past position 2000.  Use a 16 KB window to accommodate
    # current and future guardrails growth.
    if stripped.startswith(_GUARDRAILS_PREFIX):
        first_16k = stripped[:16384]
        return (
            _PERSONA_PRIMING_PREFIX in first_16k
            and _PERSONA_PRIMING_MIDDLE in first_16k
            and _PERSONA_SKILLS_HEADING in stripped
        )

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


def is_skill_expansion(text: str | None) -> bool:
    """Detect whether text is expanded skill/command content from Claude Code's Skill tool.

    When a user invokes a slash command (e.g. /opsx:apply), Claude Code's Skill
    tool expands the .md file and fires user-prompt-submit with the FULL file
    content.  This function detects that expanded content across all skill formats:

    - OTL commands: ``# Title`` + ``**Command name:**``
    - OTL SOP/util: ``# Title`` + ``**Goal:**`` or ``**Purpose:**``
    - OPSX commands: ``**Input**:`` or ``**Input:**`` near the start
    - BMAD agents: ``You must fully embody this agent's persona``
    - BMAD workflows: ``IT IS CRITICAL THAT YOU FOLLOW``

    Args:
        text: The prompt text to check

    Returns:
        True if the text is a skill expansion that should be suppressed
    """
    if not text or len(text) < 500:
        return False

    stripped = text.strip()
    first_300 = stripped[:300]

    # OTL commands: "# Title" + "**Command name:**"
    if _SKILL_HEADING_RE.match(stripped) and _COMMAND_NAME_RE.search(first_300):
        return True

    # OTL SOP/util/misc: "# Title" + "**Goal:**" or "**Purpose:**"
    if _SKILL_HEADING_RE.match(stripped) and ("**Goal:**" in first_300 or "**Purpose:**" in first_300):
        return True

    # OPSX skills: contain "**Input**:" or "**Input:**" near the start
    if "**Input**:" in first_300 or "**Input:**" in first_300:
        return True

    # BMAD agents: start with persona activation
    if stripped.startswith("You must fully embody this agent"):
        return True

    # BMAD modules/workflows: start with critical instruction
    if stripped.startswith("IT IS CRITICAL THAT YOU FOLLOW"):
        return True

    # Structured command files: heading + section separators + sub-headings.
    # Catches orch v2 commands and other multi-section .md command files that
    # don't use the legacy **Command name:** / **Goal:** / **Input:** markers.
    if _SKILL_HEADING_RE.match(stripped) and "\n---\n" in stripped and "\n## " in stripped:
        return True

    return False


def filter_skill_expansion(text: str | None) -> str | None:
    """Truncate skill/command expansion content to just the heading line.

    Detects when ``text`` is the expanded content of a .md command file
    (as injected by Claude Code's Skill tool) and returns only the first
    heading line.  Non-expansion text is returned unchanged.

    The same function must be called in both the hook receiver AND the
    transcript reconciler so that content hashes stay consistent.
    """
    if not text or len(text) < 500:
        return text

    stripped = text.strip()

    if not is_skill_expansion(stripped):
        return text

    # Return the first non-empty line as a concise label
    first_line = stripped.split("\n", 1)[0].strip()
    return first_line if first_line else text
