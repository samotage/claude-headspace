"""tmux bridge service for sending input to Claude Code sessions via tmux send-keys.

Replaces the commander socket transport with tmux subprocess calls. Text is sent
via `send-keys -l` (literal) followed by a separate Enter keystroke, which tmux
delivers through its PTY layer at a level that Ink's onSubmit handler recognises
as genuine keyboard input.
"""

import logging
import re
import subprocess
import time
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SUBPROCESS_TIMEOUT = 5  # seconds
DEFAULT_TEXT_ENTER_DELAY_MS = 100  # ms between text send and Enter
DEFAULT_SEQUENTIAL_SEND_DELAY_MS = 150  # ms between rapid sequential sends


class TmuxBridgeErrorType(str, Enum):
    """Error types for tmux bridge operations."""

    PANE_NOT_FOUND = "pane_not_found"
    TMUX_NOT_INSTALLED = "tmux_not_installed"
    SUBPROCESS_FAILED = "subprocess_failed"
    NO_PANE_ID = "no_pane_id"
    TIMEOUT = "timeout"
    SEND_FAILED = "send_failed"
    UNKNOWN = "unknown"


class SendResult(NamedTuple):
    """Result of a send operation."""

    success: bool
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None
    latency_ms: int = 0


class HealthResult(NamedTuple):
    """Result of a health check operation."""

    available: bool
    running: bool = False
    pid: int | None = None
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


class PaneInfo(NamedTuple):
    """Metadata for a tmux pane."""

    pane_id: str
    session_name: str
    current_command: str
    working_directory: str


def _classify_subprocess_error(error: subprocess.CalledProcessError) -> TmuxBridgeErrorType:
    """Classify a tmux subprocess error based on stderr content."""
    stderr = (error.stderr or b"").decode("utf-8", errors="replace").lower()
    if "can't find pane" in stderr or "no such" in stderr or "not found" in stderr:
        return TmuxBridgeErrorType.PANE_NOT_FOUND
    return TmuxBridgeErrorType.SUBPROCESS_FAILED


def send_text(
    pane_id: str,
    text: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    text_enter_delay_ms: int = DEFAULT_TEXT_ENTER_DELAY_MS,
) -> SendResult:
    """Send text followed by Enter to a Claude Code session's tmux pane.

    Sends literal text via `send-keys -l` then Enter as a separate call
    with a configurable delay between them to prevent race conditions.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        text: The text to send
        timeout: Subprocess timeout in seconds
        text_enter_delay_ms: Delay in ms between text send and Enter send

    Returns:
        SendResult with success status and optional error information
    """
    if not pane_id:
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message="No pane ID provided.",
        )

    start_time = time.time()

    try:
        # Send literal text (does NOT interpret key names)
        subprocess.run(
            ["tmux", "send-keys", "-t", pane_id, "-l", text],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        # Delay between text and Enter
        time.sleep(text_enter_delay_ms / 1000.0)

        # Send Enter as a key (triggers Ink's onSubmit)
        subprocess.run(
            ["tmux", "send-keys", "-t", pane_id, "Enter"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Sent text to tmux pane {pane_id} ({latency_ms}ms)")
        return SendResult(success=True, latency_ms=latency_ms)

    except FileNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning("tmux binary not found on PATH")
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
            latency_ms=latency_ms,
        )

    except subprocess.CalledProcessError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = _classify_subprocess_error(e)
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        logger.warning(f"tmux send-keys failed for pane {pane_id}: {stderr_text}")
        return SendResult(
            success=False,
            error_type=error_type,
            error_message=f"tmux send-keys failed: {stderr_text}" if stderr_text else "tmux send-keys failed",
            latency_ms=latency_ms,
        )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"tmux send-keys timed out for pane {pane_id}")
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux subprocess timed out after {timeout}s.",
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"Unexpected error sending to tmux pane {pane_id}")
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
            latency_ms=latency_ms,
        )


def send_keys(
    pane_id: str,
    *keys: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    sequential_delay_ms: int = DEFAULT_SEQUENTIAL_SEND_DELAY_MS,
) -> SendResult:
    """Send special keys to a tmux pane.

    Sends keys without the -l flag so tmux interprets key names
    (Enter, Escape, Up, Down, C-c, C-u, etc.).

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        *keys: Key names to send (e.g., "Enter", "Escape", "C-c")
        timeout: Subprocess timeout in seconds
        sequential_delay_ms: Delay in ms between sequential key sends

    Returns:
        SendResult with success status
    """
    if not pane_id:
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message="No pane ID provided.",
        )

    start_time = time.time()

    try:
        for i, key in enumerate(keys):
            if i > 0:
                time.sleep(sequential_delay_ms / 1000.0)
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, key],
                check=True,
                timeout=timeout,
                capture_output=True,
            )

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Sent keys {keys} to tmux pane {pane_id} ({latency_ms}ms)")
        return SendResult(success=True, latency_ms=latency_ms)

    except FileNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
            latency_ms=latency_ms,
        )

    except subprocess.CalledProcessError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = _classify_subprocess_error(e)
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return SendResult(
            success=False,
            error_type=error_type,
            error_message=f"tmux send-keys failed: {stderr_text}" if stderr_text else "tmux send-keys failed",
            latency_ms=latency_ms,
        )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux subprocess timed out after {timeout}s.",
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
            latency_ms=latency_ms,
        )


def check_health(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> HealthResult:
    """Check whether a tmux pane exists and whether Claude Code is running in it.

    Two-level check:
    1. Pane exists: pane ID found in `tmux list-panes -a`
    2. Claude Code running: pane_current_command contains 'claude' or 'node'

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        HealthResult with availability and running status
    """
    if not pane_id:
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message="No pane ID provided.",
        )

    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{pane_current_command}"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace")

        for line in output.strip().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) >= 1 and parts[0] == pane_id:
                # Pane exists
                current_command = parts[1] if len(parts) >= 2 else ""
                running = any(
                    proc in current_command.lower()
                    for proc in ("claude", "node")
                )
                return HealthResult(available=True, running=running)

        # Pane not found in list
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
            error_message=f"tmux pane {pane_id} not found.",
        )

    except FileNotFoundError:
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
        )

    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        # tmux may not be running (no server)
        if "no server running" in stderr_text.lower() or "no current" in stderr_text.lower():
            return HealthResult(
                available=False,
                error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
                error_message="tmux server is not running.",
            )
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.SUBPROCESS_FAILED,
            error_message=f"tmux list-panes failed: {stderr_text}",
        )

    except subprocess.TimeoutExpired:
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux health check timed out after {timeout}s.",
        )

    except Exception as e:
        logger.warning(f"Unexpected health check error for pane {pane_id}: {e}")
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
        )


def capture_pane(
    pane_id: str,
    lines: int = 50,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> str:
    """Capture the last N lines of a tmux pane's visible content.

    Args:
        pane_id: The tmux pane ID
        lines: Number of lines to capture from the end
        timeout: Subprocess timeout in seconds

    Returns:
        Captured text content (empty string on error)
    """
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"],
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

    Args:
        pane_text: Raw captured pane text (may contain ANSI escape codes)

    Returns:
        List of {"label": "..."} dicts if >= 2 sequential options found, else None
    """
    if not pane_text:
        return None

    # Strip ANSI escape codes
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", pane_text)

    # Match numbered option lines (with optional arrow indicator prefix)
    pattern = r"^\s*(?:[❯›>]\s*)?(\d+)\.\s+(.+?)\s*$"
    matches = re.findall(pattern, clean, re.MULTILINE)

    if len(matches) < 2:
        return None

    # Validate sequential numbering starting from 1
    for i, (num_str, _label) in enumerate(matches):
        if int(num_str) != i + 1:
            return None

    return [{"label": label} for _num, label in matches]


def capture_permission_options(
    pane_id: str,
    max_attempts: int = 3,
    retry_delay_ms: int = 200,
    capture_lines: int = 30,
) -> list[dict[str, str]] | None:
    """Capture tmux pane content and parse permission dialog options.

    Retries to handle the race condition where the hook fires before
    the dialog has fully rendered in the terminal.

    Args:
        pane_id: The tmux pane ID
        max_attempts: Number of capture+parse attempts
        retry_delay_ms: Delay in ms between attempts
        capture_lines: Number of pane lines to capture

    Returns:
        List of {"label": "..."} dicts if options found, else None
    """
    for attempt in range(max_attempts):
        pane_text = capture_pane(pane_id, lines=capture_lines)
        options = parse_permission_options(pane_text)
        if options is not None:
            logger.debug(
                f"Parsed {len(options)} permission options from pane {pane_id} "
                f"(attempt {attempt + 1})"
            )
            return options
        if attempt < max_attempts - 1:
            time.sleep(retry_delay_ms / 1000.0)

    logger.debug(f"No permission options found in pane {pane_id} after {max_attempts} attempts")
    return None


def list_panes(
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> list[PaneInfo]:
    """List all tmux panes with metadata.

    Returns:
        List of PaneInfo with pane_id, session_name, current_command, working_directory
    """
    try:
        result = subprocess.run(
            [
                "tmux", "list-panes", "-a", "-F",
                "#{pane_id}\t#{session_name}\t#{pane_current_command}\t#{pane_current_path}",
            ],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        panes = []
        for line in result.stdout.decode("utf-8", errors="replace").strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                panes.append(PaneInfo(
                    pane_id=parts[0],
                    session_name=parts[1],
                    current_command=parts[2],
                    working_directory=parts[3],
                ))
        return panes

    except Exception as e:
        logger.warning(f"list-panes failed: {e}")
        return []
