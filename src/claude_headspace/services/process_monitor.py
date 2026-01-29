"""Process monitor for background watcher health checking."""

import logging
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default PID file location
DEFAULT_PID_FILE = "/tmp/claude_headspace_watcher.pid"


@dataclass
class WatcherStatus:
    """Status information for the background watcher process."""

    running: bool
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    last_write_timestamp: Optional[datetime] = None
    failed_write_count: int = 0
    error: Optional[str] = None


class ProcessMonitor:
    """
    Monitor for the background watcher process.

    Provides health checking and status reporting for the event
    system's background process.
    """

    def __init__(self, pid_file: str = DEFAULT_PID_FILE) -> None:
        """
        Initialize the process monitor.

        Args:
            pid_file: Path to the PID file written by the watcher process
        """
        self._pid_file = Path(pid_file)
        self._event_writer_metrics: Optional[dict[str, Any]] = None

    def set_event_writer_metrics(self, metrics: dict[str, Any]) -> None:
        """
        Set metrics from the event writer for health reporting.

        Args:
            metrics: Metrics dictionary from EventWriter.get_health_status()
        """
        self._event_writer_metrics = metrics

    def is_watcher_running(self) -> bool:
        """
        Check if the background watcher process is running.

        Returns:
            True if the watcher is running, False otherwise
        """
        pid = self._read_pid()
        if pid is None:
            return False

        return self._is_process_alive(pid)

    def get_watcher_status(self) -> WatcherStatus:
        """
        Get detailed status of the background watcher.

        Returns:
            WatcherStatus with current state information
        """
        pid = self._read_pid()

        if pid is None:
            return WatcherStatus(running=False, error="No PID file found")

        if not self._is_process_alive(pid):
            return WatcherStatus(
                running=False,
                pid=pid,
                error="Process not running (stale PID file)",
            )

        # Process is running - get additional metrics
        last_write = None
        failed_count = 0

        if self._event_writer_metrics:
            metrics = self._event_writer_metrics.get("metrics", {})
            last_write_str = metrics.get("last_write_timestamp")
            if last_write_str:
                last_write = datetime.fromisoformat(last_write_str)
            failed_count = metrics.get("failed_writes", 0)

        return WatcherStatus(
            running=True,
            pid=pid,
            last_write_timestamp=last_write,
            failed_write_count=failed_count,
        )

    def get_health_status(self) -> dict[str, Any]:
        """
        Get health status for integration with /health endpoint.

        Returns:
            Dictionary with health information
        """
        status = self.get_watcher_status()

        result = {
            "watcher_running": status.running,
            "watcher_pid": status.pid,
            "degraded": not status.running,
        }

        if status.last_write_timestamp:
            result["last_write_timestamp"] = status.last_write_timestamp.isoformat()

        if status.failed_write_count > 0:
            result["failed_write_count"] = status.failed_write_count

        if status.error:
            result["error"] = status.error

        return result

    def _read_pid(self) -> Optional[int]:
        """Read the PID from the PID file."""
        if not self._pid_file.exists():
            return None

        try:
            content = self._pid_file.read_text().strip()
            return int(content)
        except (ValueError, OSError) as e:
            logger.warning(f"Error reading PID file: {e}")
            return None

    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process with the given PID is alive."""
        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we don't have permission to signal it
            return True
        except OSError:
            return False


def write_pid_file(pid_file: str = DEFAULT_PID_FILE) -> None:
    """
    Write the current process PID to the PID file.

    Args:
        pid_file: Path to write the PID file
    """
    path = Path(pid_file)
    path.write_text(str(os.getpid()))
    logger.info(f"PID file written: {pid_file}")


def remove_pid_file(pid_file: str = DEFAULT_PID_FILE) -> None:
    """
    Remove the PID file.

    Args:
        pid_file: Path to the PID file to remove
    """
    path = Path(pid_file)
    if path.exists():
        path.unlink()
        logger.info(f"PID file removed: {pid_file}")
