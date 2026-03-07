"""Shared types, enums, and validation for tmux bridge operations."""

import re
import subprocess
from enum import Enum
from typing import NamedTuple


class TmuxBridgeErrorType(str, Enum):
    """Error types for tmux bridge operations."""

    PANE_NOT_FOUND = "pane_not_found"
    TMUX_NOT_INSTALLED = "tmux_not_installed"
    SUBPROCESS_FAILED = "subprocess_failed"
    NO_PANE_ID = "no_pane_id"
    TIMEOUT = "timeout"
    SEND_FAILED = "send_failed"  # Send completed but verification failed (reserved for wait_for_pattern use)
    UNKNOWN = "unknown"


class SendResult(NamedTuple):
    """Result of a send operation."""

    success: bool
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None
    latency_ms: int = 0


class HealthCheckLevel(str, Enum):
    """Level of health check to perform."""

    EXISTS = "exists"  # Pane found in list-panes (cheapest)
    COMMAND = "command"  # + current_command check (default)
    PROCESS_TREE = "process_tree"  # + ps tree walk (most expensive)


# Default process names to check for in health checks
DEFAULT_PROCESS_NAMES = ("claude", "node")


class HealthResult(NamedTuple):
    """Result of a health check operation."""

    available: bool
    running: bool = False
    pid: int | None = None
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


class TtyResult(NamedTuple):
    """Result of a TTY lookup for a tmux pane's client."""

    success: bool
    tty: str | None = None
    session_name: str | None = None
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


class PaneInfo(NamedTuple):
    """Metadata for a tmux pane."""

    pane_id: str
    session_name: str
    current_command: str
    working_directory: str


class WaitResult(NamedTuple):
    """Result of a wait_for_pattern polling operation."""

    matched: bool
    content: str = ""
    elapsed_ms: int = 0
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


_PANE_ID_PATTERN = re.compile(r"^%\d+$")


def _validate_pane_id(pane_id: str | None) -> bool:
    """Validate that a pane ID matches tmux's %N format.

    Args:
        pane_id: The pane ID to validate

    Returns:
        True if valid (e.g. '%0', '%5', '%123'), False otherwise.
    """
    if not pane_id:
        return False
    return bool(_PANE_ID_PATTERN.match(pane_id))


def _classify_subprocess_error(
    error: subprocess.CalledProcessError,
) -> TmuxBridgeErrorType:
    """Classify a tmux subprocess error based on stderr content."""
    stderr = (error.stderr or b"").decode("utf-8", errors="replace").lower()
    if "can't find pane" in stderr or "no such" in stderr or "not found" in stderr:
        return TmuxBridgeErrorType.PANE_NOT_FOUND
    return TmuxBridgeErrorType.SUBPROCESS_FAILED


# Default configuration constants
DEFAULT_SUBPROCESS_TIMEOUT = 5  # seconds
DEFAULT_TEXT_ENTER_DELAY_MS = 120  # ms between text send and Enter
DEFAULT_CLEAR_DELAY_MS = 200  # ms after Escape before sending text
DEFAULT_SEQUENTIAL_SEND_DELAY_MS = 150  # ms between rapid sequential sends
DEFAULT_ENTER_VERIFY_DELAY_MS = 200  # ms between Enter and verification check
DEFAULT_MAX_ENTER_RETRIES = 3  # max Enter retry attempts after verification failure
DEFAULT_ENTER_VERIFY_LINES = 5  # pane lines to capture for Enter verification

# Conservative byte limit for send-keys -l arguments.  tmux versions vary
# in their internal message limits; some reject send-keys above ~2-4 KB.
# Anything larger is routed through load-buffer + paste-buffer instead.
SEND_KEYS_LITERAL_MAX = 4096
