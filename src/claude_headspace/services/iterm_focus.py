"""
iTerm2 focus and pane existence service using AppleScript.

Provides functionality to focus a specific iTerm2 pane by its session ID,
and to silently check whether a pane still exists (for reaper use).
Uses osascript subprocess with timeout to prevent blocking.
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Timeout for AppleScript execution (seconds)
APPLESCRIPT_TIMEOUT = 2

# Cache for pane existence checks (pane_id -> (PaneStatus, timestamp))
_pane_cache: dict[str, tuple] = {}
_PANE_CACHE_TTL = 30  # seconds


class FocusErrorType(str, Enum):
    """Error types for focus operations."""

    PERMISSION_DENIED = "permission_denied"
    PANE_NOT_FOUND = "pane_not_found"
    ITERM_NOT_RUNNING = "iterm_not_running"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class FocusResult(NamedTuple):
    """Result of a focus operation."""

    success: bool
    error_type: FocusErrorType | None = None
    error_message: str | None = None
    latency_ms: int = 0


def _sanitize_pane_id(pane_id: str) -> str:
    """Escape pane_id for safe interpolation into AppleScript strings.

    Prevents injection by escaping backslashes and double quotes.
    """
    return pane_id.replace("\\", "\\\\").replace('"', '\\"')


def _build_applescript(pane_id: str) -> str:
    """
    Build AppleScript to focus a specific iTerm2 pane.

    The script:
    1. Activates iTerm2 (brings to foreground, switches Spaces if needed)
    2. Searches all windows, tabs, and sessions for matching tty
    3. Activates the containing window and tab
    4. Selects the target session

    Args:
        pane_id: The iTerm2 pane/session identifier (e.g., from ITERM_SESSION_ID)

    Returns:
        AppleScript code as string
    """
    # Note: ITERM_SESSION_ID format is typically like "w0t0p0:GUID"
    # We need to match against iTerm's session tty or unique identifier
    safe_pane_id = _sanitize_pane_id(pane_id)
    return f'''
tell application "iTerm"
    activate

    set targetPaneId to "{safe_pane_id}"
    set foundSession to false

    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                try
                    set sessionTty to tty of s
                    set sessionId to unique ID of s

                    -- Match by tty name or session ID
                    if sessionTty contains targetPaneId or sessionId contains targetPaneId or targetPaneId contains sessionTty or targetPaneId contains sessionId then
                        -- Found the session, focus it
                        select t
                        select s

                        -- Bring window to front and restore if minimized
                        set index of w to 1
                        if miniaturized of w then
                            set miniaturized of w to false
                        end if

                        set foundSession to true
                        exit repeat
                    end if
                end try
            end repeat
            if foundSession then exit repeat
        end repeat
        if foundSession then exit repeat
    end repeat

    if not foundSession then
        error "Pane not found: " & targetPaneId
    end if
end tell
'''


def _parse_applescript_error(stderr: str, returncode: int) -> tuple[FocusErrorType, str]:
    """
    Parse AppleScript error output to determine error type.

    Args:
        stderr: Standard error output from osascript
        returncode: Process return code

    Returns:
        Tuple of (error_type, human-readable message)
    """
    stderr_lower = stderr.lower()

    # Check for permission denied (macOS Automation privacy controls)
    if "not authorized" in stderr_lower or "osascript is not allowed" in stderr_lower:
        return (
            FocusErrorType.PERMISSION_DENIED,
            "Automation permission not granted. Go to System Settings → "
            "Privacy & Security → Automation and enable access for this application.",
        )

    # Check for iTerm2 not running
    if "application isn't running" in stderr_lower or "can't get application" in stderr_lower:
        return (
            FocusErrorType.ITERM_NOT_RUNNING,
            "iTerm2 is not running. Please start iTerm2 and try again.",
        )

    # Check for pane not found
    if "pane not found" in stderr_lower:
        return (
            FocusErrorType.PANE_NOT_FOUND,
            "The terminal pane could not be found. The session may have been closed.",
        )

    # Unknown error
    return (
        FocusErrorType.UNKNOWN,
        f"AppleScript execution failed: {stderr.strip() or f'exit code {returncode}'}",
    )


def focus_iterm_pane(pane_id: str) -> FocusResult:
    """
    Focus a specific iTerm2 pane by its session ID.

    Executes AppleScript via osascript to:
    - Activate iTerm2 (brings to foreground, switches Spaces)
    - Find the session matching the pane_id
    - Restore window if minimized
    - Select the target session

    Args:
        pane_id: The iTerm2 session identifier (from ITERM_SESSION_ID env var)

    Returns:
        FocusResult with success status and optional error information
    """
    if not pane_id:
        return FocusResult(
            success=False,
            error_type=FocusErrorType.PANE_NOT_FOUND,
            error_message="No pane ID provided.",
            latency_ms=0,
        )

    start_time = time.time()
    script = _build_applescript(pane_id)

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=APPLESCRIPT_TIMEOUT,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        if result.returncode == 0:
            logger.info(f"Successfully focused iTerm2 pane: {pane_id} ({latency_ms}ms)")
            return FocusResult(success=True, latency_ms=latency_ms)
        else:
            error_type, error_message = _parse_applescript_error(
                result.stderr, result.returncode
            )
            logger.warning(
                f"Failed to focus iTerm2 pane {pane_id}: {error_type.value} - {error_message}"
            )
            return FocusResult(
                success=False,
                error_type=error_type,
                error_message=error_message,
                latency_ms=latency_ms,
            )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Timeout focusing iTerm2 pane {pane_id} after {latency_ms}ms")
        return FocusResult(
            success=False,
            error_type=FocusErrorType.TIMEOUT,
            error_message=f"Focus operation timed out after {APPLESCRIPT_TIMEOUT} seconds. "
            "iTerm2 may be unresponsive.",
            latency_ms=latency_ms,
        )

    except FileNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error("osascript not found - not running on macOS?")
        return FocusResult(
            success=False,
            error_type=FocusErrorType.UNKNOWN,
            error_message="osascript command not found. This feature requires macOS.",
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"Unexpected error focusing iTerm2 pane {pane_id}")
        return FocusResult(
            success=False,
            error_type=FocusErrorType.UNKNOWN,
            error_message=f"Unexpected error: {str(e)}",
            latency_ms=latency_ms,
        )


# --- Pane existence check (silent, no focus) ---


class PaneStatus(str, Enum):
    """Result of a pane existence check."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    ITERM_NOT_RUNNING = "iterm_not_running"
    ERROR = "error"


def _build_check_applescript(pane_id: str) -> str:
    """
    Build AppleScript to silently check if an iTerm2 pane exists.

    Unlike the focus script, this does NOT activate iTerm or change
    window/tab selection. It only reads session properties.

    Args:
        pane_id: The iTerm2 pane/session identifier

    Returns:
        AppleScript code as string
    """
    safe_pane_id = _sanitize_pane_id(pane_id)
    return f'''
tell application "System Events"
    if not (exists process "iTerm2") then
        return "ITERM_NOT_RUNNING"
    end if
end tell
tell application "iTerm"
    set targetPaneId to "{safe_pane_id}"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                try
                    set sessionTty to tty of s
                    set sessionId to unique ID of s
                    if sessionTty contains targetPaneId or sessionId contains targetPaneId or targetPaneId contains sessionTty or targetPaneId contains sessionId then
                        return "FOUND"
                    end if
                end try
            end repeat
        end repeat
    end repeat
    return "NOT_FOUND"
end tell
'''


def check_pane_exists(pane_id: str) -> PaneStatus:
    """
    Silently check if an iTerm2 pane still exists.

    Does NOT activate iTerm2 or focus any windows. Safe to call
    from background threads (e.g., the agent reaper).

    Uses an in-memory cache with 30s TTL to avoid redundant AppleScript calls.

    Args:
        pane_id: The iTerm2 session identifier

    Returns:
        PaneStatus indicating whether the pane was found
    """
    if not pane_id:
        return PaneStatus.NOT_FOUND

    # Check cache first
    cached = _pane_cache.get(pane_id)
    if cached:
        cached_status, cached_at = cached
        if (time.time() - cached_at) < _PANE_CACHE_TTL:
            return cached_status

    script = _build_check_applescript(pane_id)

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=APPLESCRIPT_TIMEOUT,
        )

        if result.returncode == 0:
            stdout = result.stdout.strip()
            if stdout == "FOUND":
                status = PaneStatus.FOUND
            elif stdout == "ITERM_NOT_RUNNING":
                status = PaneStatus.ITERM_NOT_RUNNING
            else:
                status = PaneStatus.NOT_FOUND
            _pane_cache[pane_id] = (status, time.time())
            return status

        # Parse error output
        stderr_lower = result.stderr.lower()
        if "application isn't running" in stderr_lower or "can't get application" in stderr_lower:
            status = PaneStatus.ITERM_NOT_RUNNING
            _pane_cache[pane_id] = (status, time.time())
            return status

        logger.warning(f"Pane check failed for {pane_id}: {result.stderr.strip()}")
        return PaneStatus.ERROR

    except subprocess.TimeoutExpired:
        logger.warning(f"Pane check timed out for {pane_id}")
        return PaneStatus.ERROR

    except FileNotFoundError:
        logger.debug("osascript not found - not running on macOS")
        return PaneStatus.ERROR

    except Exception as e:
        logger.warning(f"Pane check error for {pane_id}: {e}")
        return PaneStatus.ERROR
