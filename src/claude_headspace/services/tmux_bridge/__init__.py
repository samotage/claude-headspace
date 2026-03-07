"""tmux bridge service for sending input to Claude Code sessions via tmux.

This package is split by concern:
- types: Enums, NamedTuples, validation, constants
- send: Text delivery pipeline (send_text, send_keys, interrupt_and_send_text)
- read: Pane capture, pattern polling, permission dialog parsing
- health: Health checks, process tree walking, PID discovery
- session: Kill, list, TTY lookup, pane selection

All public symbols are re-exported here for backward compatibility.
"""

# --- types ---
# --- health ---
from .health import (
    _is_process_in_tree,
    check_health,
    find_claude_pid,
    get_pane_pid,
)

# --- read ---
from .read import (
    _diagnostic_dump,
    _has_autocomplete_ghost,
    _looks_like_description,
    capture_pane,
    capture_permission_context,
    capture_permission_options,
    parse_permission_context,
    parse_permission_options,
    wait_for_pattern,
)

# --- send ---
from .send import (
    _extract_verification_snippet,
    _get_send_lock,
    _pane_content_changed,
    _send_literal_text,
    _send_locks,
    _verify_submission,
    interrupt_and_send_text,
    release_send_lock,
    send_keys,
    send_text,
)

# --- session ---
from .session import (
    get_pane_client_tty,
    kill_session,
    list_panes,
    select_pane,
)
from .types import (
    DEFAULT_CLEAR_DELAY_MS,
    DEFAULT_ENTER_VERIFY_DELAY_MS,
    DEFAULT_ENTER_VERIFY_LINES,
    DEFAULT_MAX_ENTER_RETRIES,
    DEFAULT_PROCESS_NAMES,
    DEFAULT_SEQUENTIAL_SEND_DELAY_MS,
    DEFAULT_SUBPROCESS_TIMEOUT,
    DEFAULT_TEXT_ENTER_DELAY_MS,
    SEND_KEYS_LITERAL_MAX,
    HealthCheckLevel,
    HealthResult,
    PaneInfo,
    SendResult,
    TmuxBridgeErrorType,
    TtyResult,
    WaitResult,
    _classify_subprocess_error,
    _validate_pane_id,
)

__all__ = [
    # types
    "DEFAULT_CLEAR_DELAY_MS",
    "DEFAULT_ENTER_VERIFY_DELAY_MS",
    "DEFAULT_ENTER_VERIFY_LINES",
    "DEFAULT_MAX_ENTER_RETRIES",
    "DEFAULT_PROCESS_NAMES",
    "DEFAULT_SEQUENTIAL_SEND_DELAY_MS",
    "DEFAULT_SUBPROCESS_TIMEOUT",
    "DEFAULT_TEXT_ENTER_DELAY_MS",
    "SEND_KEYS_LITERAL_MAX",
    "HealthCheckLevel",
    "HealthResult",
    "PaneInfo",
    "SendResult",
    "TmuxBridgeErrorType",
    "TtyResult",
    "WaitResult",
    "_classify_subprocess_error",
    "_validate_pane_id",
    # send
    "_extract_verification_snippet",
    "_get_send_lock",
    "_pane_content_changed",
    "_send_literal_text",
    "_send_locks",
    "_verify_submission",
    "interrupt_and_send_text",
    "release_send_lock",
    "send_keys",
    "send_text",
    # read
    "_diagnostic_dump",
    "_has_autocomplete_ghost",
    "_looks_like_description",
    "capture_pane",
    "capture_permission_context",
    "capture_permission_options",
    "parse_permission_context",
    "parse_permission_options",
    "wait_for_pattern",
    # health
    "_is_process_in_tree",
    "check_health",
    "find_claude_pid",
    "get_pane_pid",
    # session
    "get_pane_client_tty",
    "kill_session",
    "list_panes",
    "select_pane",
]
