"""Tests for tmux bridge service."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.tmux_bridge import (
    HealthResult,
    PaneInfo,
    SendResult,
    TmuxBridgeErrorType,
    _classify_subprocess_error,
    capture_pane,
    capture_permission_options,
    check_health,
    list_panes,
    parse_permission_options,
    send_keys,
    send_text,
)


class TestTmuxBridgeErrorType:
    """Tests for TmuxBridgeErrorType enum."""

    def test_error_types_are_strings(self):
        assert TmuxBridgeErrorType.PANE_NOT_FOUND == "pane_not_found"
        assert TmuxBridgeErrorType.TMUX_NOT_INSTALLED == "tmux_not_installed"
        assert TmuxBridgeErrorType.SUBPROCESS_FAILED == "subprocess_failed"
        assert TmuxBridgeErrorType.NO_PANE_ID == "no_pane_id"
        assert TmuxBridgeErrorType.TIMEOUT == "timeout"
        assert TmuxBridgeErrorType.SEND_FAILED == "send_failed"
        assert TmuxBridgeErrorType.UNKNOWN == "unknown"


class TestSendResult:
    """Tests for SendResult named tuple."""

    def test_success_result(self):
        result = SendResult(success=True, latency_ms=50)
        assert result.success is True
        assert result.error_type is None
        assert result.latency_ms == 50

    def test_error_result(self):
        result = SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message="Timed out",
            latency_ms=2000,
        )
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT
        assert result.error_message == "Timed out"


class TestHealthResult:
    """Tests for HealthResult named tuple."""

    def test_available_result(self):
        result = HealthResult(available=True, running=True, pid=12345)
        assert result.available is True
        assert result.running is True
        assert result.pid == 12345

    def test_unavailable_result(self):
        result = HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
        )
        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND


class TestClassifySubprocessError:
    """Tests for _classify_subprocess_error."""

    def test_pane_not_found_cant_find(self):
        error = subprocess.CalledProcessError(1, "tmux", stderr=b"can't find pane: %99")
        assert _classify_subprocess_error(error) == TmuxBridgeErrorType.PANE_NOT_FOUND

    def test_pane_not_found_no_such(self):
        error = subprocess.CalledProcessError(1, "tmux", stderr=b"no such session")
        assert _classify_subprocess_error(error) == TmuxBridgeErrorType.PANE_NOT_FOUND

    def test_pane_not_found_not_found(self):
        error = subprocess.CalledProcessError(1, "tmux", stderr=b"pane not found")
        assert _classify_subprocess_error(error) == TmuxBridgeErrorType.PANE_NOT_FOUND

    def test_generic_error(self):
        error = subprocess.CalledProcessError(1, "tmux", stderr=b"some other error")
        assert _classify_subprocess_error(error) == TmuxBridgeErrorType.SUBPROCESS_FAILED

    def test_empty_stderr(self):
        error = subprocess.CalledProcessError(1, "tmux", stderr=b"")
        assert _classify_subprocess_error(error) == TmuxBridgeErrorType.SUBPROCESS_FAILED

    def test_none_stderr(self):
        error = subprocess.CalledProcessError(1, "tmux", stderr=None)
        assert _classify_subprocess_error(error) == TmuxBridgeErrorType.SUBPROCESS_FAILED


class TestSendText:
    """Tests for send_text function."""

    def test_no_pane_id(self):
        result = send_text("", "hello")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_none_pane_id(self):
        result = send_text(None, "hello")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_send_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = send_text("%5", "1", text_enter_delay_ms=0)

        assert result.success is True
        assert result.latency_ms >= 0
        # Two subprocess calls: text send + Enter send
        assert mock_run.call_count == 2

        # First call: literal text
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0] == ["tmux", "send-keys", "-t", "%5", "-l", "1"]

        # Second call: Enter key
        second_call = mock_run.call_args_list[1]
        assert second_call[0][0] == ["tmux", "send-keys", "-t", "%5", "Enter"]

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError("tmux not found")

        result = send_text("%5", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_not_found(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "tmux", stderr=b"can't find pane: %99"
        )

        result = send_text("%99", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

        result = send_text("%5", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_unexpected_error(self, mock_run):
        mock_run.side_effect = RuntimeError("something broke")

        result = send_text("%5", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.UNKNOWN


class TestSendKeys:
    """Tests for send_keys function."""

    def test_no_pane_id(self):
        result = send_keys("", "Enter")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_send_single_key(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = send_keys("%5", "Escape", sequential_delay_ms=0)

        assert result.success is True
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["tmux", "send-keys", "-t", "%5", "Escape"]

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_send_multiple_keys(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = send_keys("%5", "C-u", "Enter", sequential_delay_ms=0)

        assert result.success is True
        assert mock_run.call_count == 2

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = send_keys("%5", "Enter")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED


class TestCheckHealth:
    """Tests for check_health function."""

    def test_no_pane_id(self):
        result = check_health("")
        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_exists_with_claude(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"%0 bash\n%5 claude\n%10 vim\n",
        )

        result = check_health("%5")

        assert result.available is True
        assert result.running is True

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_exists_with_node(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"%5 node\n",
        )

        result = check_health("%5")

        assert result.available is True
        assert result.running is True

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_exists_without_claude(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"%5 bash\n",
        )

        result = check_health("%5")

        assert result.available is True
        assert result.running is False

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"%0 bash\n%10 vim\n",
        )

        result = check_health("%5")

        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = check_health("%5")

        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_server_not_running(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "tmux", stderr=b"no server running on /tmp/tmux-501/default"
        )

        result = check_health("%5")

        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

        result = check_health("%5")

        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT


class TestCapturePane:
    """Tests for capture_pane function."""

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_capture_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"line 1\nline 2\nline 3\n",
        )

        result = capture_pane("%5", lines=50)

        assert result == "line 1\nline 2\nline 3\n"
        mock_run.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_capture_failure_returns_empty(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "tmux")

        result = capture_pane("%5")

        assert result == ""


class TestListPanes:
    """Tests for list_panes function."""

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_list_panes_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"%0\tmain\tbash\t/home/user\n%5\twork\tclaude\t/path/to/project\n",
        )

        result = list_panes()

        assert len(result) == 2
        assert result[0] == PaneInfo("%0", "main", "bash", "/home/user")
        assert result[1] == PaneInfo("%5", "work", "claude", "/path/to/project")

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_list_panes_failure_returns_empty(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = list_panes()

        assert result == []


class TestParsePermissionOptions:
    """Tests for parse_permission_options function."""

    def test_two_options(self):
        text = "  1. Yes\n  2. No\n"
        result = parse_permission_options(text)
        assert result == [{"label": "Yes"}, {"label": "No"}]

    def test_three_options(self):
        text = (
            "  1. Yes\n"
            "  2. Yes, and don't ask again\n"
            "  3. No\n"
        )
        result = parse_permission_options(text)
        assert result == [
            {"label": "Yes"},
            {"label": "Yes, and don't ask again"},
            {"label": "No"},
        ]

    def test_arrow_indicator(self):
        text = (
            "❯ 1. Yes\n"
            "  2. Yes, and don't ask again\n"
            "  3. No\n"
        )
        result = parse_permission_options(text)
        assert result == [
            {"label": "Yes"},
            {"label": "Yes, and don't ask again"},
            {"label": "No"},
        ]

    def test_greater_than_indicator(self):
        text = "> 1. Yes\n  2. No\n"
        result = parse_permission_options(text)
        assert result == [{"label": "Yes"}, {"label": "No"}]

    def test_ansi_escape_codes_stripped(self):
        text = (
            "\x1b[36m  1. Yes\x1b[0m\n"
            "\x1b[36m  2. No\x1b[0m\n"
        )
        result = parse_permission_options(text)
        assert result == [{"label": "Yes"}, {"label": "No"}]

    def test_empty_text(self):
        assert parse_permission_options("") is None

    def test_none_text(self):
        assert parse_permission_options(None) is None

    def test_no_options_found(self):
        text = "Some random output\nNo numbered items here\n"
        assert parse_permission_options(text) is None

    def test_single_option_returns_none(self):
        text = "  1. Yes\n"
        assert parse_permission_options(text) is None

    def test_non_sequential_numbering_returns_none(self):
        text = "  2. Option A\n  3. Option B\n"
        assert parse_permission_options(text) is None

    def test_options_among_other_content(self):
        text = (
            "Do you want to proceed?\n"
            "\n"
            "  1. Yes\n"
            "  2. Yes, and don't ask again\n"
            "  3. No\n"
            "\n"
        )
        result = parse_permission_options(text)
        assert result == [
            {"label": "Yes"},
            {"label": "Yes, and don't ask again"},
            {"label": "No"},
        ]

    def test_labels_are_trimmed(self):
        text = "  1. Yes   \n  2. No   \n"
        result = parse_permission_options(text)
        assert result == [{"label": "Yes"}, {"label": "No"}]


class TestCapturePermissionOptions:
    """Tests for capture_permission_options function."""

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_success_on_first_attempt(self, mock_capture):
        mock_capture.return_value = "  1. Yes\n  2. No\n"

        result = capture_permission_options("%5", retry_delay_ms=0)

        assert result == [{"label": "Yes"}, {"label": "No"}]
        assert mock_capture.call_count == 1

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_retry_on_empty_pane(self, mock_capture):
        mock_capture.side_effect = [
            "",  # First attempt: empty
            "  1. Yes\n  2. No\n",  # Second attempt: success
        ]

        result = capture_permission_options("%5", retry_delay_ms=0)

        assert result == [{"label": "Yes"}, {"label": "No"}]
        assert mock_capture.call_count == 2

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_all_attempts_fail(self, mock_capture):
        mock_capture.return_value = "some random text\n"

        result = capture_permission_options("%5", max_attempts=3, retry_delay_ms=0)

        assert result is None
        assert mock_capture.call_count == 3

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_retry_on_no_options_then_success(self, mock_capture):
        mock_capture.side_effect = [
            "Loading...\n",  # No options yet
            "Loading...\n",  # Still no options
            "  1. Yes\n  2. Yes, and don't ask again\n  3. No\n",  # Options rendered
        ]

        result = capture_permission_options("%5", max_attempts=3, retry_delay_ms=0)

        assert result == [
            {"label": "Yes"},
            {"label": "Yes, and don't ask again"},
            {"label": "No"},
        ]
        assert mock_capture.call_count == 3
