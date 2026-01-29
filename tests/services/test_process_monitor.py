"""Tests for process monitor."""

import os
import tempfile
from pathlib import Path

import pytest

from claude_headspace.services.process_monitor import (
    ProcessMonitor,
    WatcherStatus,
    write_pid_file,
    remove_pid_file,
)


class TestWatcherStatus:
    """Test WatcherStatus dataclass."""

    def test_running_status(self):
        """Test running status."""
        status = WatcherStatus(running=True, pid=12345)
        assert status.running is True
        assert status.pid == 12345
        assert status.error is None

    def test_not_running_status(self):
        """Test not running status."""
        status = WatcherStatus(running=False, error="No PID file found")
        assert status.running is False
        assert status.error == "No PID file found"


class TestProcessMonitor:
    """Test ProcessMonitor class."""

    @pytest.fixture
    def temp_pid_file(self):
        """Create a temporary PID file path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            pid_file = f.name

        yield pid_file

        # Cleanup
        if os.path.exists(pid_file):
            os.unlink(pid_file)

    def test_is_watcher_running_no_pid_file(self, temp_pid_file):
        """Test is_watcher_running when no PID file exists."""
        os.unlink(temp_pid_file)  # Remove the temp file
        monitor = ProcessMonitor(pid_file=temp_pid_file)

        assert monitor.is_watcher_running() is False

    def test_is_watcher_running_with_current_process(self, temp_pid_file):
        """Test is_watcher_running with current process PID."""
        # Write current process PID
        Path(temp_pid_file).write_text(str(os.getpid()))

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        assert monitor.is_watcher_running() is True

    def test_is_watcher_running_with_stale_pid(self, temp_pid_file):
        """Test is_watcher_running with non-existent PID."""
        # Write a PID that doesn't exist (very high number)
        Path(temp_pid_file).write_text("999999999")

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        assert monitor.is_watcher_running() is False

    def test_get_watcher_status_no_pid_file(self, temp_pid_file):
        """Test get_watcher_status when no PID file exists."""
        os.unlink(temp_pid_file)
        monitor = ProcessMonitor(pid_file=temp_pid_file)

        status = monitor.get_watcher_status()

        assert status.running is False
        assert "No PID file" in status.error

    def test_get_watcher_status_running(self, temp_pid_file):
        """Test get_watcher_status when process is running."""
        Path(temp_pid_file).write_text(str(os.getpid()))

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        status = monitor.get_watcher_status()

        assert status.running is True
        assert status.pid == os.getpid()
        assert status.error is None

    def test_get_watcher_status_stale_pid(self, temp_pid_file):
        """Test get_watcher_status with stale PID file."""
        Path(temp_pid_file).write_text("999999999")

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        status = monitor.get_watcher_status()

        assert status.running is False
        assert "stale PID" in status.error

    def test_get_health_status_running(self, temp_pid_file):
        """Test get_health_status when running."""
        Path(temp_pid_file).write_text(str(os.getpid()))

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        health = monitor.get_health_status()

        assert health["watcher_running"] is True
        assert health["watcher_pid"] == os.getpid()
        assert health["degraded"] is False

    def test_get_health_status_not_running(self, temp_pid_file):
        """Test get_health_status when not running."""
        os.unlink(temp_pid_file)

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        health = monitor.get_health_status()

        assert health["watcher_running"] is False
        assert health["degraded"] is True
        assert "error" in health

    def test_set_event_writer_metrics(self, temp_pid_file):
        """Test setting event writer metrics."""
        Path(temp_pid_file).write_text(str(os.getpid()))

        monitor = ProcessMonitor(pid_file=temp_pid_file)
        monitor.set_event_writer_metrics({
            "metrics": {
                "last_write_timestamp": "2024-01-01T12:00:00+00:00",
                "failed_writes": 5,
            }
        })

        status = monitor.get_watcher_status()

        assert status.last_write_timestamp is not None
        assert status.failed_write_count == 5

    def test_invalid_pid_file_content(self, temp_pid_file):
        """Test handling invalid PID file content."""
        Path(temp_pid_file).write_text("not-a-number")

        monitor = ProcessMonitor(pid_file=temp_pid_file)

        assert monitor.is_watcher_running() is False


class TestPidFileHelpers:
    """Test PID file helper functions."""

    @pytest.fixture
    def temp_pid_file(self):
        """Create a temporary PID file path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            pid_file = f.name
        os.unlink(pid_file)  # Start with no file

        yield pid_file

        # Cleanup
        if os.path.exists(pid_file):
            os.unlink(pid_file)

    def test_write_pid_file(self, temp_pid_file):
        """Test writing PID file."""
        write_pid_file(temp_pid_file)

        content = Path(temp_pid_file).read_text()
        assert content == str(os.getpid())

    def test_remove_pid_file(self, temp_pid_file):
        """Test removing PID file."""
        # First create it
        write_pid_file(temp_pid_file)
        assert os.path.exists(temp_pid_file)

        # Then remove it
        remove_pid_file(temp_pid_file)
        assert not os.path.exists(temp_pid_file)

    def test_remove_nonexistent_pid_file(self, temp_pid_file):
        """Test removing non-existent PID file doesn't error."""
        # Should not raise
        remove_pid_file(temp_pid_file)
