"""Session-level operations — kill, list, TTY lookup, pane selection."""

import logging
import subprocess
import time

from .types import (
    DEFAULT_SUBPROCESS_TIMEOUT,
    PaneInfo,
    SendResult,
    TmuxBridgeErrorType,
    TtyResult,
    _classify_subprocess_error,
    _validate_pane_id,
)

logger = logging.getLogger(__name__)


def kill_session(
    session_name: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    socket_path: str | None = None,
) -> SendResult:
    """Kill a tmux session by name.

    Args:
        session_name: The tmux session name to kill
        timeout: Subprocess timeout in seconds
        socket_path: Optional tmux socket path (-S flag) for socket isolation

    Returns:
        SendResult with success status
    """
    if not session_name:
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message="Empty session name",
        )

    start_time = time.time()
    cmd = ["tmux"]
    if socket_path:
        cmd.extend(["-S", socket_path])
    cmd.extend(["kill-session", "-t", session_name])

    try:
        subprocess.run(
            cmd,
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Killed tmux session '{session_name}' ({latency_ms}ms)")
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
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return SendResult(
            success=False,
            error_type=_classify_subprocess_error(e),
            error_message=f"tmux kill-session failed: {stderr_text}"
            if stderr_text
            else "tmux kill-session failed",
            latency_ms=latency_ms,
        )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux kill-session timed out after {timeout}s.",
            latency_ms=latency_ms,
        )


def list_panes(
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    socket_path: str | None = None,
) -> list[PaneInfo]:
    """List all tmux panes with metadata.

    Args:
        timeout: Subprocess timeout in seconds
        socket_path: Optional tmux socket path (-S flag) for socket isolation

    Returns:
        List of PaneInfo with pane_id, session_name, current_command, working_directory
    """
    try:
        cmd = ["tmux"]
        if socket_path:
            cmd.extend(["-S", socket_path])
        cmd.extend(
            [
                "list-panes",
                "-a",
                "-F",
                "#{pane_id}\t#{session_name}\t#{pane_current_command}\t#{pane_current_path}",
            ]
        )
        result = subprocess.run(
            cmd,
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        panes = []
        for line in (
            result.stdout.decode("utf-8", errors="replace").strip().splitlines()
        ):
            parts = line.split("\t")
            if len(parts) >= 4:
                panes.append(
                    PaneInfo(
                        pane_id=parts[0],
                        session_name=parts[1],
                        current_command=parts[2],
                        working_directory=parts[3],
                    )
                )
        return panes

    except Exception as e:
        logger.warning(f"list-panes failed: {e}")
        return []


def get_pane_client_tty(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> TtyResult:
    """Resolve a tmux pane ID to the client TTY that owns it.

    Two-step lookup:
    1. Find which tmux session contains the pane via `tmux list-panes -a`
    2. Find the client TTY attached to that session via `tmux list-clients`

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        TtyResult with the client TTY path (e.g., /dev/ttys003)
    """
    if not _validate_pane_id(pane_id):
        return TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    # Step 1: Find which session contains this pane
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{session_name}"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace")
        session_name = None
        for line in output.strip().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) >= 2 and parts[0] == pane_id:
                session_name = parts[1]
                break

        if session_name is None:
            return TtyResult(
                success=False,
                error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
                error_message=f"tmux pane {pane_id} not found.",
            )

    except FileNotFoundError:
        return TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
        )

    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return TtyResult(
            success=False,
            error_type=_classify_subprocess_error(e),
            error_message=f"tmux list-panes failed: {stderr_text}"
            if stderr_text
            else "tmux list-panes failed",
        )

    except subprocess.TimeoutExpired:
        return TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux list-panes timed out after {timeout}s.",
        )

    # Step 2: Find client TTY for that session
    try:
        result = subprocess.run(
            ["tmux", "list-clients", "-t", session_name, "-F", "#{client_tty}"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace").strip()
        if not output:
            return TtyResult(
                success=False,
                session_name=session_name,
                error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
                error_message=f"No client attached to tmux session '{session_name}'.",
            )

        # Take the first client TTY
        client_tty = output.splitlines()[0].strip()
        return TtyResult(
            success=True,
            tty=client_tty,
            session_name=session_name,
        )

    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return TtyResult(
            success=False,
            session_name=session_name,
            error_type=_classify_subprocess_error(e),
            error_message=f"tmux list-clients failed: {stderr_text}"
            if stderr_text
            else "tmux list-clients failed",
        )

    except subprocess.TimeoutExpired:
        return TtyResult(
            success=False,
            session_name=session_name,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux list-clients timed out after {timeout}s.",
        )


def select_pane(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> SendResult:
    """Select a tmux pane, switching to its window first.

    Runs `tmux select-window -t <pane_id>` then `tmux select-pane -t <pane_id>`.
    tmux resolves the %N pane ID to the correct window automatically.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        SendResult with success status
    """
    if not _validate_pane_id(pane_id):
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    start_time = time.time()

    try:
        subprocess.run(
            ["tmux", "select-window", "-t", pane_id],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        subprocess.run(
            ["tmux", "select-pane", "-t", pane_id],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Selected tmux pane {pane_id} ({latency_ms}ms)")
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
            error_message=f"tmux select failed: {stderr_text}"
            if stderr_text
            else "tmux select failed",
            latency_ms=latency_ms,
        )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux select timed out after {timeout}s.",
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
