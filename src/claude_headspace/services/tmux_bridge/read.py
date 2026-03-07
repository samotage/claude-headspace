"""Pane content capture, pattern polling, and permission dialog parsing."""

import logging
import re
import subprocess
import time

from .types import (
    DEFAULT_SUBPROCESS_TIMEOUT,
    TmuxBridgeErrorType,
    WaitResult,
    _validate_pane_id,
)

logger = logging.getLogger(__name__)


def _diagnostic_dump(pane_id: str, context: str) -> None:
    """Capture pane content and log at WARNING level for debugging.

    Called on timeouts and failure paths to aid post-mortem analysis.

    Args:
        pane_id: The tmux pane ID
        context: Description of why the dump was triggered
    """
    try:
        content = capture_pane(pane_id, lines=100)
        if content:
            truncated = content[:2000]
            if len(content) > 2000:
                truncated += "\n... [truncated]"
            logger.warning(
                f"Diagnostic dump ({context}) for pane {pane_id}:\n{truncated}"
            )
        else:
            logger.warning(
                f"Diagnostic dump ({context}) for pane {pane_id}: "
                f"capture returned empty"
            )
    except Exception as e:
        logger.warning(f"Diagnostic dump ({context}) for pane {pane_id} failed: {e}")


def wait_for_pattern(
    pane_id: str,
    pattern: str,
    timeout_ms: int = 5000,
    poll_interval_ms: int = 200,
    capture_lines: int = 50,
    join_wrapped: bool = False,
) -> WaitResult:
    """Poll a tmux pane until a regex pattern matches captured content.

    Repeatedly captures pane content and searches for the pattern.
    Returns as soon as a match is found, or after timeout_ms.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        pattern: Regex pattern to search for (re.search)
        timeout_ms: Maximum time to wait in milliseconds
        poll_interval_ms: Delay between capture attempts in milliseconds
        capture_lines: Number of pane lines to capture per attempt
        join_wrapped: If True, join wrapped lines in capture (-J flag)

    Returns:
        WaitResult with match status, captured content, and timing
    """
    if not _validate_pane_id(pane_id):
        return WaitResult(
            matched=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    start_time = time.time()
    deadline = start_time + (timeout_ms / 1000.0)
    last_content = ""

    while True:
        content = capture_pane(pane_id, lines=capture_lines, join_wrapped=join_wrapped)
        last_content = content

        if content and re.search(pattern, content, re.MULTILINE):
            elapsed_ms = int((time.time() - start_time) * 1000)
            return WaitResult(
                matched=True,
                content=content,
                elapsed_ms=elapsed_ms,
            )

        now = time.time()
        if now >= deadline:
            elapsed_ms = int((now - start_time) * 1000)
            _diagnostic_dump(pane_id, f"wait_for_pattern timeout ({pattern!r})")
            return WaitResult(
                matched=False,
                content=last_content,
                elapsed_ms=elapsed_ms,
                error_type=TmuxBridgeErrorType.TIMEOUT,
                error_message=f"Pattern {pattern!r} not found after {timeout_ms}ms",
            )

        time.sleep(poll_interval_ms / 1000.0)


def _has_autocomplete_ghost(pane_content: str) -> bool:
    """Check if pane content shows autocomplete ghost text.

    Ghost text is rendered with dim/faint ANSI styling (SGR 2 or color 90).
    We check the last non-empty lines (the input area) for these indicators,
    but skip lines that are purely decorative (separator lines made of
    box-drawing characters, status bars, etc.) since Claude Code renders
    those with dim styling too — causing false positives that trigger
    unwanted Escape sends which clear user input.

    Args:
        pane_content: Pane content captured with escape sequences (-e flag)

    Returns:
        True if autocomplete ghost text is likely present
    """
    if not pane_content:
        return False

    # Check the last few non-empty lines for dim text indicators.
    # SGR 2 = dim/faint, SGR 90 = dark gray (bright black).
    # Claude Code renders autocomplete ghost suggestions with these styles.
    lines = [line for line in pane_content.split("\n") if line.strip()]
    if not lines:
        return False

    # Only check the last 2 lines (input area)
    for line in lines[-2:]:
        if "\x1b[2m" in line or "\x1b[90m" in line:
            # Strip ANSI escape sequences to examine the actual text content
            clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).strip()
            if not clean:
                continue
            # Skip lines that are purely decorative: box-drawing characters
            # (─│┌┐└┘├┤┬┴┼╭╮╰╯═║╔╗╚╝╠╣╦╩╬), dashes, dots, and whitespace.
            # These are Claude Code's separator/border lines rendered with
            # dim styling — NOT autocomplete ghost text.
            stripped = clean.replace(" ", "")
            if stripped and all(
                c in "─│┌┐└┘├┤┬┴┼╭╮╰╯═║╔╗╚╝╠╣╦╩╬-—·•…" for c in stripped
            ):
                continue
            # This line has dim/faint styling AND contains actual text
            # content — likely autocomplete ghost text.
            return True

    return False


def capture_pane(
    pane_id: str,
    lines: int = 50,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    join_wrapped: bool = False,
    include_escapes: bool = False,
) -> str:
    """Capture the last N lines of a tmux pane's visible content.

    Args:
        pane_id: The tmux pane ID
        lines: Number of lines to capture from the end
        timeout: Subprocess timeout in seconds
        join_wrapped: If True, include -J flag to join wrapped lines
        include_escapes: If True, include ANSI escape sequences (-e flag)

    Returns:
        Captured text content (empty string on error)
    """
    if not _validate_pane_id(pane_id):
        return ""

    cmd = ["tmux", "capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"]
    if join_wrapped:
        cmd.append("-J")
    if include_escapes:
        cmd.append("-e")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"capture-pane failed for {pane_id}: {e}")
        return ""


def parse_permission_options(pane_text: str) -> list[dict[str, str]] | None:
    """Parse numbered permission options from tmux pane content.

    Matches lines like:
      1. Yes
      ❯ 2. Yes, and don't ask again
        3. No

    Extracts the LAST group of sequential numbered options starting from 1,
    so earlier numbered lists in the terminal output don't interfere.

    Args:
        pane_text: Raw captured pane text (may contain ANSI escape codes)

    Returns:
        List of {"label": "..."} dicts if >= 2 sequential options found, else None
    """
    if not pane_text:
        return None

    # Strip ANSI escape codes
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", pane_text)

    # Match numbered option lines (with optional arrow indicator prefix).
    # Space after period is optional — tmux wrapping can compress "2. Yes" to "2.Yes"
    # when the cursor arrow (❯) on option 1 shifts alignment.
    pattern = r"^\s*(?:[❯›>]\s*)?(\d+)\.\s*(.+?)\s*$"
    matches = re.findall(pattern, clean, re.MULTILINE)

    if len(matches) < 2:
        return None

    # Find the LAST group of sequential options starting from 1.
    # Earlier numbered lists (agent output, etc.) should be ignored.
    best_group = None
    current_group = []
    for num_str, label in matches:
        num = int(num_str)
        if num == 1:
            # Start a new group
            current_group = [(num, label)]
        elif current_group and num == current_group[-1][0] + 1:
            # Continue the current group
            current_group.append((num, label))
        else:
            # Break in sequence — save current group if valid and reset
            if len(current_group) >= 2:
                best_group = current_group
            current_group = []
    # Check final group
    if len(current_group) >= 2:
        best_group = current_group

    if not best_group:
        return None

    return [{"label": label} for _num, label in best_group]


def parse_permission_context(pane_text: str) -> dict | None:
    """Parse the full permission dialog block from tmux pane content.

    Extracts the tool type header, command text, description, and options from
    a Claude Code permission dialog that looks like:

        Bash command

          curl -s http://localhost:5055/dashboard | sed -n '630,645p'
          Check state-bar HTML around line 634

        Do you want to proceed?
        ❯ 1. Yes
          2. No

    Args:
        pane_text: Raw captured pane text (may contain ANSI escape codes)

    Returns:
        Dict with "tool_type", "command", "description", "options" keys, or None
    """
    if not pane_text:
        return None

    # Strip ANSI escape codes
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", pane_text)

    # Parse options first — if no options, this isn't a permission dialog
    options = parse_permission_options(pane_text)
    if not options:
        return None

    # Find the LAST "Do you want to proceed?" line (or similar prompt)
    prompt_pattern = (
        r"^\s*(Do you want to (?:proceed|allow|continue)\??|Allow this .*\??)\s*$"
    )
    prompt_matches = list(
        re.finditer(prompt_pattern, clean, re.MULTILINE | re.IGNORECASE)
    )
    prompt_match = prompt_matches[-1] if prompt_matches else None

    # Find tool type header — a line like "Bash command", "Read file", etc.
    # Use the LAST match to handle panes with multiple tool outputs.
    tool_type = None
    command_text = None
    description = None

    # Look for known tool header patterns — find the LAST one
    header_pattern = r"^\s*((?:Bash|Read|Write|Edit|Glob|Grep|WebFetch|WebSearch|NotebookEdit)\s+\w*)\s*$"
    header_matches = list(
        re.finditer(header_pattern, clean, re.MULTILINE | re.IGNORECASE)
    )
    header_match = header_matches[-1] if header_matches else None

    if header_match:
        tool_type = header_match.group(1).strip()
        header_end = header_match.end()

        # The command block is indented text between the header and the prompt
        if prompt_match and prompt_match.start() > header_end:
            block_text = clean[header_end : prompt_match.start()]
        else:
            # No prompt found after header — take text up to the first option line after header
            first_option_match = re.search(
                r"^\s*(?:[❯›>]\s*)?\d+\.\s*", clean[header_end:], re.MULTILINE
            )
            if first_option_match:
                block_text = clean[header_end : header_end + first_option_match.start()]
            else:
                block_text = ""

        # Parse the block: indented lines are command/description
        block_lines = [
            line.strip() for line in block_text.strip().splitlines() if line.strip()
        ]

        if block_lines:
            # First non-empty line(s) are the command, last line may be description
            # Heuristic: if last line looks like a description (starts with uppercase,
            # no special command chars), treat it as description
            if len(block_lines) >= 2 and _looks_like_description(block_lines[-1]):
                command_text = "\n".join(block_lines[:-1])
                description = block_lines[-1]
            else:
                command_text = "\n".join(block_lines)

    # Require at least one structural signal that this is actually a
    # permission dialog, not just numbered agent output (e.g. "1. Fix bug,
    # 2. Add test, 3. Refactor").  A valid dialog has a tool header
    # ("Bash command", "Read file") and/or a confirmation prompt
    # ("Do you want to proceed?").
    if not header_match and not prompt_match:
        logger.debug(
            "Rejecting numbered list — no dialog structure found (no header or prompt)"
        )
        return None

    return {
        "tool_type": tool_type,
        "command": command_text,
        "description": description,
        "options": options,
    }


def _looks_like_description(line: str) -> bool:
    """Heuristic: check if a line looks like a human-readable description.

    Descriptions typically:
    - Start with an uppercase letter
    - Don't start with common command prefixes (/, -, $, etc.)
    - Don't contain shell operators (|, >, &&)
    """
    if not line:
        return False
    first_char = line[0]
    if first_char in ("/", "-", "$", ".", "~", "{", "[", "(", "'", '"', "`"):
        return False
    if any(op in line for op in ("|", "&&", ">>", "<<", "$(", "${")):
        return False
    # Starts with uppercase letter — likely description
    return first_char.isupper()


def capture_permission_options(
    pane_id: str,
    max_attempts: int = 10,
    retry_delay_ms: int = 200,
    capture_lines: int = 30,
) -> list[dict[str, str]] | None:
    """Capture tmux pane content and parse permission dialog options.

    Uses wait_for_pattern to poll for numbered option lines, handling
    the race condition where the hook fires before the dialog has fully
    rendered in the terminal.

    Args:
        pane_id: The tmux pane ID
        max_attempts: Number of capture+parse attempts (used to compute timeout)
        retry_delay_ms: Delay in ms between attempts (used as poll interval)
        capture_lines: Number of pane lines to capture

    Returns:
        List of {"label": "..."} dicts if options found, else None
    """
    # Use wait_for_pattern to detect numbered option lines
    timeout_ms = max_attempts * retry_delay_ms + retry_delay_ms
    wait = wait_for_pattern(
        pane_id,
        pattern=r"^\s*(?:[❯›>]\s*)?\d+\.\s*\S",
        timeout_ms=timeout_ms,
        poll_interval_ms=retry_delay_ms,
        capture_lines=capture_lines,
        join_wrapped=True,
    )

    if wait.matched:
        options = parse_permission_options(wait.content)
        if options is not None:
            logger.debug(
                f"Parsed {len(options)} permission options from pane {pane_id} "
                f"({wait.elapsed_ms}ms)"
            )
            return options

    logger.debug(f"No permission options found in pane {pane_id} after {timeout_ms}ms")
    return None


def capture_permission_context(
    pane_id: str,
    max_attempts: int = 10,
    retry_delay_ms: int = 200,
    capture_lines: int = 30,
) -> dict | None:
    """Capture tmux pane content and parse the full permission dialog context.

    Like capture_permission_options but returns the full context dict including
    the command text and description, not just the options list.

    Uses wait_for_pattern to poll for numbered option lines, handling
    the race condition where the hook fires before the dialog has fully
    rendered in the terminal.

    Args:
        pane_id: The tmux pane ID
        max_attempts: Number of capture+parse attempts (used to compute timeout)
        retry_delay_ms: Delay in ms between attempts (used as poll interval)
        capture_lines: Number of pane lines to capture

    Returns:
        Dict with "tool_type", "command", "description", "options" keys, or None
    """
    # Use wait_for_pattern to detect numbered option lines
    timeout_ms = max_attempts * retry_delay_ms + retry_delay_ms
    wait = wait_for_pattern(
        pane_id,
        pattern=r"^\s*(?:[❯›>]\s*)?\d+\.\s*\S",
        timeout_ms=timeout_ms,
        poll_interval_ms=retry_delay_ms,
        capture_lines=capture_lines,
        join_wrapped=True,
    )

    if wait.matched:
        context = parse_permission_context(wait.content)
        if context is not None:
            logger.debug(
                f"Parsed permission context from pane {pane_id} "
                f"({wait.elapsed_ms}ms): tool_type={context.get('tool_type')}"
            )
            return context

    logger.debug(f"No permission context found in pane {pane_id} after {timeout_ms}ms")
    return None
