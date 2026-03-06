"""Voice channel intent detection — pure regex logic, no Flask or DB."""

import re

# ── Channel intent detection patterns ────────────────────────────────
# Checked in order; first match wins. Patterns use distinctive structural
# markers (colon separators, question marks, "create ... channel") to avoid
# false positives on regular agent commands.

# 1. Send to channel
_SEND_PATTERNS = [
    re.compile(
        r"(?:send|message|tell)\s+(?:to\s+)?(?:the\s+)?(.+?)\s+channel\s*:\s*(.+)",
        re.I,
    ),
    re.compile(
        r"(?:send|message|tell)\s+(?:to\s+)?(?:the\s+)?(.+?):\s*(.+)",
        re.I,
    ),
]

# 2. Channel history
_HISTORY_PATTERNS = [
    re.compile(
        r"what(?:'s|s)\s+(?:happening|going\s+on)\s+in\s+(?:the\s+)?(.+?)(?:\s+channel)?\s*\??$",
        re.I,
    ),
    re.compile(
        r"show\s+(?:the\s+)?(.+?)(?:\s+channel)?\s+messages",
        re.I,
    ),
    re.compile(
        r"(?:channel\s+)?history\s+(?:for\s+)?(?:the\s+)?(.+?)(?:\s+channel)?$",
        re.I,
    ),
]

# 3. List channels
_LIST_PATTERNS = [
    re.compile(r"(?:list|show|my)\s+channels?$", re.I),
    re.compile(
        r"what\s+channels?\s+(?:am\s+I\s+in|do\s+I\s+have|are\s+there)\s*\??$",
        re.I,
    ),
]

# 4. Create channel (with optional members)
_CREATE_PATTERNS = [
    re.compile(
        r"create\s+(?:a\s+)?(\w+)\s+channel\s+(?:called\s+|named\s+)?(.+?)"
        r"(?:\s+with\s+(.+))?$",
        re.I,
    ),
    re.compile(
        r"create\s+(?:a\s+)?channel\s+(?:called\s+|named\s+)?(.+?)"
        r"(?:\s+(?:as|type)\s+(\w+))?"
        r"(?:\s+with\s+(.+))?$",
        re.I,
    ),
]

# 5. Add member
_ADD_MEMBER_PATTERNS = [
    re.compile(r"add\s+(\w+)\s+to\s+this\s+channel$", re.I),
    re.compile(r"add\s+(\w+)\s+to\s+(?:the\s+)?(.+?)(?:\s+channel)?$", re.I),
]

# 6. Complete channel
_COMPLETE_PATTERNS = [
    re.compile(
        r"(?:complete|finish|close|end)\s+(?:the\s+)?(.+?)(?:\s+channel)?$",
        re.I,
    ),
]

# Channel type keyword mapping
_CHANNEL_TYPE_KEYWORDS = {
    "workshop": "workshop",
    "delegation": "delegation",
    "delegate": "delegation",
    "review": "review",
    "standup": "standup",
    "stand up": "standup",
    "broadcast": "broadcast",
    "announce": "broadcast",
    "announcement": "broadcast",
}


def _detect_channel_intent(text: str) -> dict | None:
    """Detect if a voice utterance targets a channel operation.

    Returns a dict with:
      - action: "send" | "history" | "list" | "create" | "add_member" | "complete"
      - channel_ref: extracted channel name/reference (may be "this channel")
      - content: message content (for send action)
      - channel_type: inferred type (for create action)
      - member_ref: persona name reference (for add_member action)
      - member_refs: list of persona name references (for create with members)
    Returns None if the utterance is not channel-targeted.
    """
    # 1. Send patterns
    for pat in _SEND_PATTERNS:
        m = pat.match(text)
        if m:
            return {
                "action": "send",
                "channel_ref": m.group(1).strip(),
                "content": m.group(2).strip(),
            }

    # 2. History patterns
    for pat in _HISTORY_PATTERNS:
        m = pat.match(text)
        if m:
            return {
                "action": "history",
                "channel_ref": m.group(1).strip(),
            }

    # 3. List patterns
    for pat in _LIST_PATTERNS:
        m = pat.match(text)
        if m:
            return {"action": "list"}

    # 4. Create patterns
    for pat in _CREATE_PATTERNS:
        m = pat.match(text)
        if m:
            groups = m.groups()
            if pat == _CREATE_PATTERNS[0]:
                # Pattern 1: "create a [type] channel [called name] [with members]"
                channel_type = groups[0].strip()
                name = groups[1].strip()
                members_text = groups[2]
            else:
                # Pattern 2: "create channel [called name] [as type] [with members]"
                name = groups[0].strip()
                channel_type = groups[1].strip() if groups[1] else None
                members_text = groups[2]

            inferred_type = _infer_channel_type(channel_type or text)
            return {
                "action": "create",
                "name": name,
                "channel_type": inferred_type,
                "member_refs": _extract_member_refs(members_text)
                if members_text
                else [],
            }

    # 5. Add member patterns
    for pat in _ADD_MEMBER_PATTERNS:
        m = pat.match(text)
        if m:
            groups = m.groups()
            if len(groups) == 1:
                # "add X to this channel"
                return {
                    "action": "add_member",
                    "member_ref": groups[0].strip(),
                    "channel_ref": "this channel",
                }
            else:
                return {
                    "action": "add_member",
                    "member_ref": groups[0].strip(),
                    "channel_ref": groups[1].strip(),
                }

    # 6. Complete patterns
    for pat in _COMPLETE_PATTERNS:
        m = pat.match(text)
        if m:
            return {
                "action": "complete",
                "channel_ref": m.group(1).strip(),
            }

    return None


def _infer_channel_type(text: str) -> str:
    """Infer channel type from voice text. Default: workshop."""
    text_lower = text.lower()
    for keyword, channel_type in _CHANNEL_TYPE_KEYWORDS.items():
        if keyword in text_lower:
            return channel_type
    return "workshop"


def _extract_member_refs(members_text: str) -> list[str]:
    """Extract persona name references from 'with X and Y' / 'with X, Y, Z'."""
    if not members_text:
        return []
    # Normalize: split on "and", ",", "&"
    parts = re.split(r"\s+and\s+|,\s*|&\s*", members_text.strip())
    return [p.strip() for p in parts if p.strip()]
