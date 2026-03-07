"""Health checks, process tree walking, and Claude PID discovery."""

import logging
import subprocess

from .types import (
    DEFAULT_PROCESS_NAMES,
    DEFAULT_SUBPROCESS_TIMEOUT,
    HealthCheckLevel,
    HealthResult,
    TmuxBridgeErrorType,
    _validate_pane_id,
)

logger = logging.getLogger(__name__)


def get_pane_pid(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> int | None:
    """Get the root PID of a tmux pane's process.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        The pane's PID as an int, or None if not found/error.
    """
    if not _validate_pane_id(pane_id):
        return None

    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{pane_pid}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == pane_id:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
        return None

    except Exception:
        return None


def find_claude_pid(
    pane_id: str,
    process_names: tuple[str, ...] = ("claude",),
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> int | None:
    """Find the PID of the Claude process in a tmux pane's process tree.

    Walks the process tree from the pane's root PID, returning the first
    child whose command name matches.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        process_names: Process names to match (case-insensitive)
        timeout: Subprocess timeout in seconds

    Returns:
        The PID of the Claude process, or None if not found.
    """
    pane_pid = get_pane_pid(pane_id, timeout=timeout)
    if pane_pid is None:
        return None

    try:
        ps_result = subprocess.run(
            ["ps", "-axo", "pid,ppid,comm"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if ps_result.returncode != 0:
            return None

        # Build parent -> children map
        children: dict[str, list[tuple[str, str]]] = {}
        for line in ps_result.stdout.strip().split("\n")[1:]:
            parts = line.split(None, 2)
            if len(parts) >= 3:
                pid, ppid, comm = parts[0], parts[1], parts[2]
                children.setdefault(ppid, []).append((pid, comm))

        # BFS through process tree
        queue = [str(pane_pid)]
        while queue:
            current = queue.pop(0)
            for child_pid, child_comm in children.get(current, []):
                if any(name in child_comm.lower() for name in process_names):
                    try:
                        return int(child_pid)
                    except ValueError:
                        pass
                queue.append(child_pid)

        return None

    except Exception:
        return None


def _is_process_in_tree(
    pane_pid: int,
    process_names: tuple[str, ...] = DEFAULT_PROCESS_NAMES,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> bool | None:
    """Check if any of the named processes are in a pane's process tree.

    Walks children and grandchildren of pane_pid using `ps -axo pid,ppid,comm`.

    Args:
        pane_pid: The root PID of the tmux pane
        process_names: Process names to search for (case-insensitive)
        timeout: Subprocess timeout in seconds

    Returns:
        True if found, False if not found, None on error.
    """
    try:
        ps_result = subprocess.run(
            ["ps", "-axo", "pid,ppid,comm"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if ps_result.returncode != 0:
            return None

        pane_pid_str = str(pane_pid)

        # Build parent→children map
        children: dict[str, list[tuple[str, str]]] = {}
        for line in ps_result.stdout.strip().split("\n")[1:]:  # skip header
            parts = line.split(None, 2)
            if len(parts) >= 3:
                pid, ppid, comm = parts[0], parts[1], parts[2]
                children.setdefault(ppid, []).append((pid, comm))

        # Check direct children
        for child_pid, child_comm in children.get(pane_pid_str, []):
            if any(name in child_comm.lower() for name in process_names):
                return True
            # Check grandchildren (bridge → claude)
            for _gc_pid, gc_comm in children.get(child_pid, []):
                if any(name in gc_comm.lower() for name in process_names):
                    return True

        return False

    except Exception:
        return None


def check_health(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    level: HealthCheckLevel = HealthCheckLevel.COMMAND,
    process_names: tuple[str, ...] = DEFAULT_PROCESS_NAMES,
) -> HealthResult:
    """Check whether a tmux pane exists and whether Claude Code is running in it.

    Three-level check controlled by the `level` parameter:
    - EXISTS: Only checks if the pane exists in `tmux list-panes` (cheapest).
    - COMMAND: Also checks if pane_current_command matches process_names (default).
    - PROCESS_TREE: Also walks the pane's process tree via `ps` (most expensive).

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds
        level: Depth of health check (EXISTS, COMMAND, or PROCESS_TREE)
        process_names: Process names to check for (default: ("claude", "node"))

    Returns:
        HealthResult with availability, running status, and optional PID
    """
    if not _validate_pane_id(pane_id):
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    try:
        # For EXISTS level, we only need pane_id in the output
        fmt = (
            "#{pane_id} #{pane_current_command}"
            if level != HealthCheckLevel.EXISTS
            else "#{pane_id}"
        )
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", fmt],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace")

        for line in output.strip().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) >= 1 and parts[0] == pane_id:
                # Pane exists
                if level == HealthCheckLevel.EXISTS:
                    return HealthResult(available=True, running=False)

                current_command = parts[1] if len(parts) >= 2 else ""
                running = any(proc in current_command.lower() for proc in process_names)

                if level == HealthCheckLevel.COMMAND:
                    return HealthResult(available=True, running=running)

                # PROCESS_TREE level: walk the process tree
                pane_pid = get_pane_pid(pane_id, timeout=timeout)
                if pane_pid is None:
                    # Fallback to COMMAND result if we can't get PID
                    return HealthResult(available=True, running=running, pid=None)

                tree_result = _is_process_in_tree(
                    pane_pid,
                    process_names=process_names,
                    timeout=timeout,
                )
                if tree_result is True:
                    return HealthResult(available=True, running=True, pid=pane_pid)
                elif tree_result is False:
                    return HealthResult(available=True, running=False, pid=pane_pid)
                else:
                    # Can't determine — fall back to command-level result
                    return HealthResult(available=True, running=running, pid=pane_pid)

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
        if (
            "no server running" in stderr_text.lower()
            or "no current" in stderr_text.lower()
        ):
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
