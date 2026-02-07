"""Tests for iTerm2 focus service."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.iterm_focus import (
    APPLESCRIPT_TIMEOUT,
    FocusErrorType,
    FocusResult,
    PaneStatus,
    _build_applescript,
    _build_check_applescript,
    _parse_applescript_error,
    check_pane_exists,
    focus_iterm_pane,
)


class TestFocusErrorType:
    """Tests for FocusErrorType enum."""

    def test_error_types_are_strings(self):
        """Error types should be string values."""
        assert FocusErrorType.PERMISSION_DENIED == "permission_denied"
        assert FocusErrorType.PANE_NOT_FOUND == "pane_not_found"
        assert FocusErrorType.ITERM_NOT_RUNNING == "iterm_not_running"
        assert FocusErrorType.TIMEOUT == "timeout"
        assert FocusErrorType.UNKNOWN == "unknown"


class TestFocusResult:
    """Tests for FocusResult named tuple."""

    def test_success_result(self):
        """Test creating a success result."""
        result = FocusResult(success=True, latency_ms=100)
        assert result.success is True
        assert result.error_type is None
        assert result.error_message is None
        assert result.latency_ms == 100

    def test_error_result(self):
        """Test creating an error result."""
        result = FocusResult(
            success=False,
            error_type=FocusErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
            latency_ms=50,
        )
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND
        assert result.error_message == "Pane not found"
        assert result.latency_ms == 50


class TestBuildApplescript:
    """Tests for _build_applescript function."""

    def test_applescript_contains_pane_id(self):
        """Generated AppleScript should contain the pane ID."""
        pane_id = "pty-12345"
        script = _build_applescript(pane_id)
        assert pane_id in script

    def test_applescript_activates_iterm(self):
        """Generated AppleScript should activate iTerm."""
        script = _build_applescript("test-pane")
        assert 'tell application "iTerm"' in script
        assert "activate" in script

    def test_applescript_searches_sessions(self):
        """Generated AppleScript should search through sessions."""
        script = _build_applescript("test-pane")
        assert "repeat with w in windows" in script
        assert "repeat with t in tabs of w" in script
        assert "repeat with s in sessions of t" in script

    def test_applescript_selects_session(self):
        """Generated AppleScript should select found session."""
        script = _build_applescript("test-pane")
        assert "select t" in script
        assert "select s" in script

    def test_applescript_handles_minimized_window(self):
        """Generated AppleScript should restore minimized windows."""
        script = _build_applescript("test-pane")
        assert "miniaturized" in script

    def test_applescript_raises_error_on_not_found(self):
        """Generated AppleScript should error when pane not found."""
        script = _build_applescript("test-pane")
        assert 'error "Pane not found:' in script


class TestParseApplescriptError:
    """Tests for _parse_applescript_error function."""

    def test_permission_denied_not_authorized(self):
        """Test detection of 'not authorized' permission error."""
        error_type, message = _parse_applescript_error(
            "execution error: System Events got an error: "
            "osascript is not authorized to send keystrokes.",
            1,
        )
        assert error_type == FocusErrorType.PERMISSION_DENIED
        assert "System Settings" in message

    def test_permission_denied_not_allowed(self):
        """Test detection of 'not allowed' permission error."""
        error_type, message = _parse_applescript_error(
            "osascript is not allowed assistive access.",
            1,
        )
        assert error_type == FocusErrorType.PERMISSION_DENIED

    def test_iterm_not_running(self):
        """Test detection of iTerm not running."""
        error_type, message = _parse_applescript_error(
            "execution error: Application isn't running.",
            1,
        )
        assert error_type == FocusErrorType.ITERM_NOT_RUNNING
        assert "iTerm2 is not running" in message

    def test_iterm_cant_get_application(self):
        """Test detection of can't get application error."""
        error_type, message = _parse_applescript_error(
            "execution error: Can't get application \"iTerm\".",
            1,
        )
        assert error_type == FocusErrorType.ITERM_NOT_RUNNING

    def test_pane_not_found(self):
        """Test detection of pane not found error."""
        error_type, message = _parse_applescript_error(
            "execution error: Pane not found: pty-12345",
            1,
        )
        assert error_type == FocusErrorType.PANE_NOT_FOUND
        assert "session may have been closed" in message

    def test_unknown_error(self):
        """Test handling of unknown errors."""
        error_type, message = _parse_applescript_error(
            "some random error message",
            1,
        )
        assert error_type == FocusErrorType.UNKNOWN
        assert "AppleScript execution failed" in message

    def test_unknown_error_with_empty_stderr(self):
        """Test handling of unknown error with empty stderr."""
        error_type, message = _parse_applescript_error("", 1)
        assert error_type == FocusErrorType.UNKNOWN
        assert "exit code 1" in message


class TestFocusItermPane:
    """Tests for focus_iterm_pane function."""

    def test_empty_pane_id_returns_error(self):
        """Test that empty pane ID returns an error."""
        result = focus_iterm_pane("")
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND
        assert "No pane ID provided" in result.error_message

    def test_none_pane_id_returns_error(self):
        """Test that None pane ID returns an error."""
        result = focus_iterm_pane(None)
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_successful_focus(self, mock_run):
        """Test successful focus operation."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = focus_iterm_pane("pty-12345")

        assert result.success is True
        assert result.error_type is None
        assert result.latency_ms >= 0

        # Verify osascript was called
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0][0] == "osascript"
        assert args[1]["timeout"] == APPLESCRIPT_TIMEOUT

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_with_permission_denied(self, mock_run):
        """Test focus operation with permission denied."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="osascript is not allowed assistive access.",
        )

        result = focus_iterm_pane("pty-12345")

        assert result.success is False
        assert result.error_type == FocusErrorType.PERMISSION_DENIED

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_with_pane_not_found(self, mock_run):
        """Test focus operation when pane not found."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Pane not found: pty-12345",
        )

        result = focus_iterm_pane("pty-12345")

        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_with_timeout(self, mock_run):
        """Test focus operation when AppleScript times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="osascript",
            timeout=APPLESCRIPT_TIMEOUT,
        )

        result = focus_iterm_pane("pty-12345")

        assert result.success is False
        assert result.error_type == FocusErrorType.TIMEOUT
        assert "timed out" in result.error_message

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_with_osascript_not_found(self, mock_run):
        """Test focus operation when osascript is not found."""
        mock_run.side_effect = FileNotFoundError("osascript not found")

        result = focus_iterm_pane("pty-12345")

        assert result.success is False
        assert result.error_type == FocusErrorType.UNKNOWN
        assert "macOS" in result.error_message

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_with_unexpected_error(self, mock_run):
        """Test focus operation with unexpected error."""
        mock_run.side_effect = Exception("Something unexpected")

        result = focus_iterm_pane("pty-12345")

        assert result.success is False
        assert result.error_type == FocusErrorType.UNKNOWN
        assert "Something unexpected" in result.error_message

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_measures_latency(self, mock_run):
        """Test that focus operation measures latency."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = focus_iterm_pane("pty-12345")

        # Latency should be non-negative
        assert result.latency_ms >= 0

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_focus_uses_correct_timeout(self, mock_run):
        """Test that focus operation uses the configured timeout."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        focus_iterm_pane("pty-12345")

        args = mock_run.call_args
        assert args[1]["timeout"] == APPLESCRIPT_TIMEOUT
        assert args[1]["capture_output"] is True
        assert args[1]["text"] is True


class TestPaneStatus:
    """Tests for PaneStatus enum."""

    def test_pane_status_values(self):
        assert PaneStatus.FOUND == "found"
        assert PaneStatus.NOT_FOUND == "not_found"
        assert PaneStatus.ITERM_NOT_RUNNING == "iterm_not_running"
        assert PaneStatus.ERROR == "error"


class TestBuildCheckApplescript:
    """Tests for _build_check_applescript function."""

    def test_contains_pane_id(self):
        script = _build_check_applescript("pty-99999")
        assert "pty-99999" in script

    def test_does_not_activate_iterm(self):
        """Check script does NOT focus or activate windows."""
        script = _build_check_applescript("test-pane")
        assert "activate" not in script
        assert "select t" not in script
        assert "select s" not in script
        assert "miniaturized" not in script

    def test_checks_system_events_for_iterm(self):
        script = _build_check_applescript("test-pane")
        assert 'tell application "System Events"' in script
        assert 'exists process "iTerm2"' in script

    def test_returns_found_not_found_strings(self):
        script = _build_check_applescript("test-pane")
        assert 'return "FOUND"' in script
        assert 'return "NOT_FOUND"' in script
        assert 'return "ITERM_NOT_RUNNING"' in script


class TestCheckPaneExists:
    """Tests for check_pane_exists function."""

    def setup_method(self):
        """Clear the pane cache before each test."""
        import claude_headspace.services.iterm_focus as itf
        itf._pane_cache.clear()

    def test_empty_pane_id(self):
        assert check_pane_exists("") == PaneStatus.NOT_FOUND

    def test_none_pane_id(self):
        assert check_pane_exists(None) == PaneStatus.NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_pane_found(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="FOUND\n", stderr="")
        assert check_pane_exists("pty-123") == PaneStatus.FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_pane_not_found(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="NOT_FOUND\n", stderr="")
        assert check_pane_exists("pty-123") == PaneStatus.NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_iterm_not_running_via_stdout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ITERM_NOT_RUNNING\n", stderr="")
        assert check_pane_exists("pty-123") == PaneStatus.ITERM_NOT_RUNNING

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_iterm_not_running_via_stderr(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Application isn't running."
        )
        assert check_pane_exists("pty-123") == PaneStatus.ITERM_NOT_RUNNING

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_unknown_error_returns_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="something weird"
        )
        assert check_pane_exists("pty-123") == PaneStatus.ERROR

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_timeout_returns_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="osascript", timeout=2)
        assert check_pane_exists("pty-123") == PaneStatus.ERROR

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_file_not_found_returns_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("osascript not found")
        assert check_pane_exists("pty-123") == PaneStatus.ERROR

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_unexpected_exception_returns_error(self, mock_run):
        mock_run.side_effect = Exception("boom")
        assert check_pane_exists("pty-123") == PaneStatus.ERROR
