"""Parse Claude Code context window usage from tmux pane content.

Extracts the statusline format: [ctx: XX% used, XXXk remaining]
Handles ANSI escape codes and various formatting variations.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Strip ANSI escape codes (same pattern used in tmux_bridge.py)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Match context usage statusline: [ctx: 22% used, 155k remaining]
# Allows for variations in whitespace and number formats
_CTX_RE = re.compile(
    r"\[ctx:\s*(\d+)%\s*used,\s*(\d+\.?\d*[kKmM]?)\s*remaining\]"
)


def parse_context_usage(pane_text: str) -> dict | None:
    """Parse context window usage from tmux pane text.

    Args:
        pane_text: Raw captured pane text (may contain ANSI escape codes)

    Returns:
        Dict with keys: percent_used (int), remaining_tokens (str), raw (str)
        None if no context usage statusline found
    """
    if not pane_text:
        return None

    # Strip ANSI escape codes
    clean = _ANSI_RE.sub("", pane_text)

    match = _CTX_RE.search(clean)
    if not match:
        return None

    percent_used = int(match.group(1))
    remaining_tokens = match.group(2)

    return {
        "percent_used": percent_used,
        "remaining_tokens": remaining_tokens,
        "raw": match.group(0),
    }
