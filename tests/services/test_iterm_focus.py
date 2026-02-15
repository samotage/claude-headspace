"""Tests for iTerm2 focus service."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.iterm_focus import (
    APPLESCRIPT_TIMEOUT,
    AttachResult,
    FocusErrorType,
    FocusResult,
    PaneStatus,
    _build_applescript,
    _build_attach_applescript,
    _build_check_applescript,
    _build_tty_applescript,
    _parse_applescript_error,
    attach_tmux_session,
    check_pane_exists,
    check_tmux_session_exists,
    focus_iterm_by_tty,
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


class TestBuildTtyApplescript:
    """Tests for _build_tty_applescript function."""

    def test_contains_tty_path(self):
        """Generated AppleScript should contain the TTY path."""
        script = _build_tty_applescript("/dev/ttys003")
        assert "/dev/ttys003" in script

    def test_uses_exact_tty_equality(self):
        """Generated AppleScript should match by exact TTY equality, not contains."""
        script = _build_tty_applescript("/dev/ttys003")
        assert "tty of s is targetTty" in script

    def test_does_not_match_by_unique_id(self):
        """TTY script should NOT match by unique ID (that's the whole point)."""
        script = _build_tty_applescript("/dev/ttys003")
        assert "unique ID" not in script

    def test_activates_iterm(self):
        """Generated AppleScript should activate iTerm."""
        script = _build_tty_applescript("/dev/ttys003")
        assert 'tell application "iTerm"' in script
        assert "activate" in script

    def test_selects_session_and_tab(self):
        """Generated AppleScript should select found session and tab."""
        script = _build_tty_applescript("/dev/ttys003")
        assert "select t" in script
        assert "select s" in script

    def test_handles_minimized_window(self):
        """Generated AppleScript should restore minimized windows."""
        script = _build_tty_applescript("/dev/ttys003")
        assert "miniaturized" in script

    def test_raises_error_on_not_found(self):
        """Generated AppleScript should error when pane not found."""
        script = _build_tty_applescript("/dev/ttys003")
        assert 'error "Pane not found:' in script


class TestFocusItermByTty:
    """Tests for focus_iterm_by_tty function."""

    def test_empty_tty_returns_error(self):
        """Test that empty TTY returns an error."""
        result = focus_iterm_by_tty("")
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND
        assert "No TTY path provided" in result.error_message

    def test_none_tty_returns_error(self):
        """Test that None TTY returns an error."""
        result = focus_iterm_by_tty(None)
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_successful_focus(self, mock_run):
        """Test successful focus by TTY."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = focus_iterm_by_tty("/dev/ttys003")

        assert result.success is True
        assert result.error_type is None
        assert result.latency_ms >= 0

        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0][0] == "osascript"
        assert args[1]["timeout"] == APPLESCRIPT_TIMEOUT

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_pane_not_found(self, mock_run):
        """Test focus when no session matches TTY."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Pane not found: /dev/ttys003",
        )

        result = focus_iterm_by_tty("/dev/ttys003")

        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_timeout(self, mock_run):
        """Test focus timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="osascript", timeout=APPLESCRIPT_TIMEOUT,
        )

        result = focus_iterm_by_tty("/dev/ttys003")

        assert result.success is False
        assert result.error_type == FocusErrorType.TIMEOUT
        assert "timed out" in result.error_message

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_osascript_not_found(self, mock_run):
        """Test when osascript is not found."""
        mock_run.side_effect = FileNotFoundError("osascript not found")

        result = focus_iterm_by_tty("/dev/ttys003")

        assert result.success is False
        assert result.error_type == FocusErrorType.UNKNOWN
        assert "macOS" in result.error_message

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_unexpected_error(self, mock_run):
        """Test unexpected exception."""
        mock_run.side_effect = Exception("Something unexpected")

        result = focus_iterm_by_tty("/dev/ttys003")

        assert result.success is False
        assert result.error_type == FocusErrorType.UNKNOWN
        assert "Something unexpected" in result.error_message


class TestCheckTmuxSessionExists:
    """Tests for check_tmux_session_exists function."""

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_session_exists(self, mock_run):
        """Test returns True when tmux has-session succeeds."""
        mock_run.return_value = MagicMock(returncode=0)

        assert check_tmux_session_exists("hs-test-123") is True
        mock_run.assert_called_once_with(
            ["tmux", "has-session", "-t", "hs-test-123"],
            capture_output=True,
            text=True,
            timeout=2,
        )

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_session_not_exists(self, mock_run):
        """Test returns False when tmux has-session fails."""
        mock_run.return_value = MagicMock(returncode=1)

        assert check_tmux_session_exists("hs-nonexistent") is False

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_timeout_returns_false(self, mock_run):
        """Test returns False on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=2)

        assert check_tmux_session_exists("hs-test") is False

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_file_not_found_returns_false(self, mock_run):
        """Test returns False when tmux binary not found."""
        mock_run.side_effect = FileNotFoundError("tmux not found")

        assert check_tmux_session_exists("hs-test") is False

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    def test_unexpected_error_returns_false(self, mock_run):
        """Test returns False on unexpected error."""
        mock_run.side_effect = Exception("boom")

        assert check_tmux_session_exists("hs-test") is False


class TestAttachResult:
    """Tests for AttachResult named tuple."""

    def test_success_result(self):
        """Test creating a success result."""
        result = AttachResult(success=True, method="new_tab", latency_ms=100)
        assert result.success is True
        assert result.method == "new_tab"
        assert result.error_type is None
        assert result.error_message is None
        assert result.latency_ms == 100

    def test_error_result(self):
        """Test creating an error result."""
        result = AttachResult(
            success=False,
            error_type=FocusErrorType.TIMEOUT,
            error_message="Timed out",
            latency_ms=2000,
        )
        assert result.success is False
        assert result.error_type == FocusErrorType.TIMEOUT
        assert result.method is None


class TestBuildAttachApplescript:
    """Tests for _build_attach_applescript function."""

    def test_contains_session_name(self):
        """Generated AppleScript should contain the session name."""
        script = _build_attach_applescript("hs-test-123")
        assert "hs-test-123" in script

    def test_activates_iterm(self):
        """Generated AppleScript should activate iTerm."""
        script = _build_attach_applescript("hs-test")
        assert 'tell application "iTerm"' in script
        assert "activate" in script

    def test_creates_new_tab(self):
        """Generated AppleScript should create a new tab."""
        script = _build_attach_applescript("hs-test")
        assert "create tab with default profile" in script

    def test_runs_tmux_attach(self):
        """Generated AppleScript should run tmux attach command."""
        script = _build_attach_applescript("hs-test-123")
        assert 'write text "tmux attach -t hs-test-123"' in script


class TestAttachTmuxSession:
    """Tests for attach_tmux_session function."""

    def test_empty_session_name_returns_error(self):
        """Test that empty session name returns an error."""
        result = attach_tmux_session("")
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND
        assert "No tmux session name" in result.error_message

    def test_none_session_name_returns_error(self):
        """Test that None session name returns an error."""
        result = attach_tmux_session(None)
        assert result.success is False
        assert result.error_type == FocusErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_new_tab_when_no_clients(self, mock_clients, mock_run):
        """Test opens new tab when no clients are attached."""
        mock_clients.return_value = []
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = attach_tmux_session("hs-test-123")

        assert result.success is True
        assert result.method == "new_tab"
        assert result.latency_ms >= 0

    @patch("claude_headspace.services.iterm_focus.focus_iterm_by_tty")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_reuses_existing_tab(self, mock_clients, mock_focus_tty):
        """Test reuses existing tab when client is already attached."""
        mock_clients.return_value = ["/dev/ttys005"]
        mock_focus_tty.return_value = FocusResult(success=True, latency_ms=50)

        result = attach_tmux_session("hs-test-123")

        assert result.success is True
        assert result.method == "reused_tab"
        mock_focus_tty.assert_called_once_with("/dev/ttys005")

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    @patch("claude_headspace.services.iterm_focus.focus_iterm_by_tty")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_falls_through_to_new_tab_when_reuse_fails(
        self, mock_clients, mock_focus_tty, mock_run,
    ):
        """Test opens new tab when existing client focus fails."""
        mock_clients.return_value = ["/dev/ttys005"]
        mock_focus_tty.return_value = FocusResult(
            success=False, error_type=FocusErrorType.PANE_NOT_FOUND,
            error_message="not found", latency_ms=50,
        )
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = attach_tmux_session("hs-test-123")

        assert result.success is True
        assert result.method == "new_tab"

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_applescript_error(self, mock_clients, mock_run):
        """Test handles AppleScript error on new tab."""
        mock_clients.return_value = []
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Application isn't running.",
        )

        result = attach_tmux_session("hs-test-123")

        assert result.success is False
        assert result.error_type == FocusErrorType.ITERM_NOT_RUNNING

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_timeout(self, mock_clients, mock_run):
        """Test handles timeout on AppleScript execution."""
        mock_clients.return_value = []
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="osascript", timeout=APPLESCRIPT_TIMEOUT,
        )

        result = attach_tmux_session("hs-test-123")

        assert result.success is False
        assert result.error_type == FocusErrorType.TIMEOUT

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_file_not_found(self, mock_clients, mock_run):
        """Test handles osascript not found."""
        mock_clients.return_value = []
        mock_run.side_effect = FileNotFoundError("osascript not found")

        result = attach_tmux_session("hs-test-123")

        assert result.success is False
        assert result.error_type == FocusErrorType.UNKNOWN
        assert "macOS" in result.error_message

    @patch("claude_headspace.services.iterm_focus.subprocess.run")
    @patch("claude_headspace.services.iterm_focus._get_tmux_client_ttys")
    def test_unexpected_error(self, mock_clients, mock_run):
        """Test handles unexpected exception."""
        mock_clients.return_value = []
        mock_run.side_effect = Exception("Something broke")

        result = attach_tmux_session("hs-test-123")

        assert result.success is False
        assert result.error_type == FocusErrorType.UNKNOWN
        assert "Something broke" in result.error_message
