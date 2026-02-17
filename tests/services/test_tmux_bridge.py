"""Tests for tmux bridge service."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.tmux_bridge import (
    DEFAULT_ENTER_VERIFY_LINES,
    HealthCheckLevel,
    HealthResult,
    PaneInfo,
    SendResult,
    TmuxBridgeErrorType,
    TtyResult,
    WaitResult,
    _classify_subprocess_error,
    _diagnostic_dump,
    _get_send_lock,
    _has_autocomplete_ghost,
    _is_process_in_tree,
    _pane_content_changed,
    _send_locks,
    _validate_pane_id,
    _verify_submission,
    capture_pane,
    capture_permission_context,
    capture_permission_options,
    check_health,
    get_pane_pid,
    get_pane_client_tty,
    interrupt_and_send_text,
    kill_session,
    list_panes,
    parse_permission_context,
    parse_permission_options,
    release_send_lock,
    select_pane,
    send_keys,
    send_text,
    wait_for_pattern,
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


class TestValidatePaneId:
    """Tests for _validate_pane_id helper."""

    def test_valid_single_digit(self):
        assert _validate_pane_id("%5") is True

    def test_valid_zero(self):
        assert _validate_pane_id("%0") is True

    def test_valid_multi_digit(self):
        assert _validate_pane_id("%123") is True

    def test_invalid_empty(self):
        assert _validate_pane_id("") is False

    def test_invalid_none(self):
        assert _validate_pane_id(None) is False

    def test_invalid_no_percent(self):
        assert _validate_pane_id("5") is False

    def test_invalid_alpha(self):
        assert _validate_pane_id("%abc") is False

    def test_invalid_prefix(self):
        assert _validate_pane_id("pane-5") is False

    def test_invalid_double_percent(self):
        assert _validate_pane_id("%%5") is False


class TestPaneIdValidationInPublicFunctions:
    """Tests that malformed pane IDs are rejected by all public functions."""

    def test_send_text_rejects_malformed(self):
        result = send_text("5", "hello")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_interrupt_and_send_text_rejects_malformed(self):
        result = interrupt_and_send_text("pane-5", "hello")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_send_keys_rejects_malformed(self):
        result = send_keys("abc", "Enter")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_check_health_rejects_malformed(self):
        result = check_health("5")
        assert result.available is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_capture_pane_rejects_malformed(self):
        result = capture_pane("bad-id")
        assert result == ""

    def test_get_pane_client_tty_rejects_malformed(self):
        result = get_pane_client_tty("pane5")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_select_pane_rejects_malformed(self):
        result = select_pane("5")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID


class TestHasAutocompleteGhost:
    """Tests for _has_autocomplete_ghost detection."""

    def test_empty_content(self):
        assert _has_autocomplete_ghost("") is False

    def test_none_content(self):
        assert _has_autocomplete_ghost(None) is False

    def test_clean_prompt_no_ghost(self):
        assert _has_autocomplete_ghost("> ") is False

    def test_normal_text_no_ghost(self):
        assert _has_autocomplete_ghost("Some output\n> ") is False

    def test_dim_sgr2_detected(self):
        """SGR 2 (dim/faint) indicates autocomplete ghost text."""
        content = "> \x1b[2msome suggestion\x1b[22m"
        assert _has_autocomplete_ghost(content) is True

    def test_gray_sgr90_detected(self):
        """SGR 90 (dark gray) indicates autocomplete ghost text."""
        content = "> \x1b[90msome suggestion\x1b[39m"
        assert _has_autocomplete_ghost(content) is True

    def test_dim_on_earlier_line_ignored(self):
        """Dim text on earlier lines (not input area) is ignored."""
        content = "\x1b[2mdim header\x1b[22m\nsome output\nmore output\n> "
        assert _has_autocomplete_ghost(content) is False

    def test_whitespace_only_lines_skipped(self):
        """Blank lines are filtered out before checking last 2 lines."""
        content = "> \n\n\n"
        assert _has_autocomplete_ghost(content) is False


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

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_send_success_no_ghost(self, mock_run, mock_capture):
        """Without autocomplete ghost text, only text + Enter are sent (no Escape)."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "  # clean prompt, no ghost text

        result = send_text("%5", "1", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=False)

        assert result.success is True
        assert result.latency_ms >= 0
        # Two subprocess calls: text send + Enter send (no Escape)
        assert mock_run.call_count == 2

        # First call: literal text
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0] == ["tmux", "send-keys", "-t", "%5", "-l", "1"]

        # Second call: Enter key
        second_call = mock_run.call_args_list[1]
        assert second_call[0][0] == ["tmux", "send-keys", "-t", "%5", "Enter"]

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_send_success_with_ghost(self, mock_run, mock_capture):
        """With autocomplete ghost text detected pre-typing, Escape is sent first."""
        mock_run.return_value = MagicMock(returncode=0)
        # Pre-typing: ghost text. Post-typing: clean (Escape dismissed it).
        mock_capture.side_effect = [
            "> \x1b[2msome suggestion\x1b[22m",  # pre-typing ghost check
            "> ",  # post-typing ghost check (clean after Escape)
        ]

        result = send_text("%5", "1", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=False)

        assert result.success is True
        # Three subprocess calls: Escape + text send + Enter send
        assert mock_run.call_count == 3

        # First call: Escape to dismiss autocomplete
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0] == ["tmux", "send-keys", "-t", "%5", "Escape"]

        # Second call: literal text
        second_call = mock_run.call_args_list[1]
        assert second_call[0][0] == ["tmux", "send-keys", "-t", "%5", "-l", "1"]

        # Third call: Enter key
        third_call = mock_run.call_args_list[2]
        assert third_call[0][0] == ["tmux", "send-keys", "-t", "%5", "Enter"]

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run, mock_capture):
        mock_capture.return_value = ""
        mock_run.side_effect = FileNotFoundError("tmux not found")

        result = send_text("%5", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_not_found(self, mock_run, mock_capture):
        mock_capture.return_value = ""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "tmux", stderr=b"can't find pane: %99"
        )

        result = send_text("%99", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_timeout(self, mock_run, mock_capture):
        mock_capture.return_value = ""
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

        result = send_text("%5", "hello")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_unexpected_error(self, mock_run, mock_capture):
        mock_capture.return_value = ""
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


class TestCapturePaneJoinWrapped:
    """Tests for capture_pane join_wrapped (-J) flag."""

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_join_wrapped_false_no_j_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"output\n")
        capture_pane("%5", lines=50, join_wrapped=False)
        cmd = mock_run.call_args[0][0]
        assert "-J" not in cmd

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_join_wrapped_true_includes_j_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"output\n")
        capture_pane("%5", lines=50, join_wrapped=True)
        cmd = mock_run.call_args[0][0]
        assert "-J" in cmd

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_default_no_j_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"output\n")
        capture_pane("%5")
        cmd = mock_run.call_args[0][0]
        assert "-J" not in cmd


class TestPermissionCaptureUsesJoinWrapped:
    """Tests that permission capture functions pass join_wrapped=True to wait_for_pattern."""

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_capture_permission_options_uses_join_wrapped(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=True, content="  1. Yes\n  2. No\n", elapsed_ms=10,
        )
        capture_permission_options("%5", retry_delay_ms=0)
        _, kwargs = mock_wait.call_args
        assert kwargs["join_wrapped"] is True

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_capture_permission_context_uses_join_wrapped(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=True,
            content=(
                " Bash command\n\n   git status\n\n"
                " Do you want to proceed?\n ❯ 1. Yes\n   2. No\n"
            ),
            elapsed_ms=10,
        )
        capture_permission_context("%5", retry_delay_ms=0)
        _, kwargs = mock_wait.call_args
        assert kwargs["join_wrapped"] is True


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

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_success_on_first_attempt(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=True,
            content="  1. Yes\n  2. No\n",
            elapsed_ms=10,
        )

        result = capture_permission_options("%5", retry_delay_ms=0)

        assert result == [{"label": "Yes"}, {"label": "No"}]
        mock_wait.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_wait_matches_after_delay(self, mock_wait):
        """wait_for_pattern handles internal retries — returns content on match."""
        mock_wait.return_value = WaitResult(
            matched=True,
            content="  1. Yes\n  2. No\n",
            elapsed_ms=400,
        )

        result = capture_permission_options("%5", retry_delay_ms=200)

        assert result == [{"label": "Yes"}, {"label": "No"}]

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_all_attempts_fail(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=False,
            content="some random text\n",
            elapsed_ms=600,
            error_type=TmuxBridgeErrorType.TIMEOUT,
        )

        result = capture_permission_options("%5", max_attempts=3, retry_delay_ms=0)

        assert result is None

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_three_options_parsed(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=True,
            content="  1. Yes\n  2. Yes, and don't ask again\n  3. No\n",
            elapsed_ms=500,
        )

        result = capture_permission_options("%5", max_attempts=3, retry_delay_ms=0)

        assert result == [
            {"label": "Yes"},
            {"label": "Yes, and don't ask again"},
            {"label": "No"},
        ]


class TestParsePermissionContext:
    """Tests for parse_permission_context function."""

    def test_full_bash_dialog(self):
        text = (
            " Bash command\n"
            "\n"
            "   curl -s http://localhost:5055/dashboard | sed -n '630,645p'\n"
            "   Check state-bar HTML around line 634\n"
            "\n"
            " Do you want to proceed?\n"
            " ❯ 1. Yes\n"
            "   2. No\n"
        )
        result = parse_permission_context(text)
        assert result is not None
        assert result["tool_type"] == "Bash command"
        assert "curl" in result["command"]
        assert result["description"] == "Check state-bar HTML around line 634"
        assert len(result["options"]) == 2
        assert result["options"][0]["label"] == "Yes"

    def test_bash_dialog_no_description(self):
        text = (
            " Bash command\n"
            "\n"
            "   rm -rf /tmp/test-dir\n"
            "\n"
            " Do you want to proceed?\n"
            " ❯ 1. Yes\n"
            "   2. No\n"
        )
        result = parse_permission_context(text)
        assert result is not None
        assert result["tool_type"] == "Bash command"
        assert "rm" in result["command"]
        assert result["description"] is None

    def test_three_options(self):
        text = (
            " Read file\n"
            "\n"
            "   /Users/sam/project/src/app.py\n"
            "\n"
            " Do you want to allow?\n"
            " ❯ 1. Yes\n"
            "   2. Yes, and don't ask again\n"
            "   3. No\n"
        )
        result = parse_permission_context(text)
        assert result is not None
        assert len(result["options"]) == 3

    def test_empty_text_returns_none(self):
        assert parse_permission_context("") is None

    def test_none_text_returns_none(self):
        assert parse_permission_context(None) is None

    def test_no_options_returns_none(self):
        text = "Some random output\nNo numbered items here\n"
        assert parse_permission_context(text) is None

    def test_ansi_codes_stripped(self):
        text = (
            "\x1b[36m Bash command\x1b[0m\n"
            "\n"
            "\x1b[36m   git status\x1b[0m\n"
            "\n"
            " Do you want to proceed?\n"
            " \x1b[36m❯ 1. Yes\x1b[0m\n"
            " \x1b[36m  2. No\x1b[0m\n"
        )
        result = parse_permission_context(text)
        assert result is not None
        assert result["tool_type"] == "Bash command"
        assert "git status" in result["command"]

    def test_options_still_parsed_without_header(self):
        """When no tool header is found, options should still be parsed."""
        text = (
            " Some custom dialog\n"
            "\n"
            " Do you want to proceed?\n"
            " ❯ 1. Yes\n"
            "   2. No\n"
        )
        result = parse_permission_context(text)
        assert result is not None
        assert result["tool_type"] is None
        assert result["options"] is not None
        assert len(result["options"]) == 2

    def test_numbered_agent_output_rejected_without_dialog_structure(self):
        """Numbered agent output must NOT be parsed as permission options.

        When the pane contains numbered discussion points (e.g. resolved items)
        but no tool header or 'Do you want to proceed?' prompt, the function
        should return None — these are not permission dialogs.
        """
        text = (
            " Good. Let me process what's resolved and what needs discussion.\n"
            "\n"
            " Resolved — I'll update the ERDs:\n"
            " 1. Integer PKs, not UUIDs\n"
            " 2. Persona keeps slug and role_type — slug generation belongs to Persona\n"
            " 3. Drop can_use_tools from Role\n"
            " 4. Drop PositionAssignment table — agent status tells you everything\n"
            " 5. Drop availability constraint (2.3) — multiple Cons are fine\n"
            "\n"
            " Needs workshopping — point 3:\n"
        )
        result = parse_permission_context(text)
        assert result is None

    def test_multiline_command(self):
        text = (
            " Bash command\n"
            "\n"
            "   cd /Users/sam/project &&\n"
            "   npm install\n"
            "   Install project dependencies\n"
            "\n"
            " Do you want to proceed?\n"
            " ❯ 1. Yes\n"
            "   2. No\n"
        )
        result = parse_permission_context(text)
        assert result is not None
        assert result["description"] == "Install project dependencies"


class TestCapturePermissionContext:
    """Tests for capture_permission_context function."""

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_success_on_first_attempt(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=True,
            content=(
                " Bash command\n"
                "\n"
                "   git status\n"
                "\n"
                " Do you want to proceed?\n"
                " ❯ 1. Yes\n"
                "   2. No\n"
            ),
            elapsed_ms=10,
        )

        result = capture_permission_context("%5", retry_delay_ms=0)

        assert result is not None
        assert result["tool_type"] == "Bash command"
        assert result["options"] is not None
        mock_wait.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_wait_matches_after_delay(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=True,
            content=(
                " Bash command\n"
                "\n"
                "   ls -la\n"
                "\n"
                " Do you want to proceed?\n"
                " ❯ 1. Yes\n"
                "   2. No\n"
            ),
            elapsed_ms=400,
        )

        result = capture_permission_context("%5", retry_delay_ms=200)

        assert result is not None

    @patch("claude_headspace.services.tmux_bridge.wait_for_pattern")
    def test_all_attempts_fail(self, mock_wait):
        mock_wait.return_value = WaitResult(
            matched=False,
            content="some random text\n",
            elapsed_ms=600,
            error_type=TmuxBridgeErrorType.TIMEOUT,
        )

        result = capture_permission_context("%5", max_attempts=3, retry_delay_ms=0)

        assert result is None


class TestTtyResult:
    """Tests for TtyResult named tuple."""

    def test_success_result(self):
        result = TtyResult(success=True, tty="/dev/ttys003", session_name="main")
        assert result.success is True
        assert result.tty == "/dev/ttys003"
        assert result.session_name == "main"
        assert result.error_type is None

    def test_error_result(self):
        result = TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
            error_message="Pane not found",
        )
        assert result.success is False
        assert result.tty is None
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND


class TestGetPaneClientTty:
    """Tests for get_pane_client_tty function."""

    def test_no_pane_id(self):
        result = get_pane_client_tty("")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_none_pane_id(self):
        result = get_pane_client_tty(None)
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_found_with_client(self, mock_run):
        """Test successful TTY resolution: pane found, client attached."""
        mock_run.side_effect = [
            # list-panes: pane found in session "main"
            MagicMock(
                returncode=0,
                stdout=b"%0 other\n%29 main\n%30 work\n",
            ),
            # list-clients: client attached
            MagicMock(
                returncode=0,
                stdout=b"/dev/ttys003\n",
            ),
        ]

        result = get_pane_client_tty("%29")

        assert result.success is True
        assert result.tty == "/dev/ttys003"
        assert result.session_name == "main"
        assert mock_run.call_count == 2

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_no_client_attached(self, mock_run):
        """Test when pane found but no client attached to session."""
        mock_run.side_effect = [
            # list-panes: pane found
            MagicMock(returncode=0, stdout=b"%29 main\n"),
            # list-clients: empty output (no client)
            MagicMock(returncode=0, stdout=b""),
        ]

        result = get_pane_client_tty("%29")

        assert result.success is False
        assert result.session_name == "main"
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND
        assert "No client attached" in result.error_message

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_not_found(self, mock_run):
        """Test when pane ID not in list-panes output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"%0 main\n%5 work\n",
        )

        result = get_pane_client_tty("%99")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND
        assert mock_run.call_count == 1  # Only list-panes, no list-clients

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run):
        """Test when tmux binary not on PATH."""
        mock_run.side_effect = FileNotFoundError("tmux not found")

        result = get_pane_client_tty("%29")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_list_panes_timeout(self, mock_run):
        """Test timeout during list-panes."""
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

        result = get_pane_client_tty("%29")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_list_clients_timeout(self, mock_run):
        """Test timeout during list-clients (after successful list-panes)."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=b"%29 main\n"),
            subprocess.TimeoutExpired("tmux", 5),
        ]

        result = get_pane_client_tty("%29")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT
        assert result.session_name == "main"

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_list_clients_error(self, mock_run):
        """Test CalledProcessError during list-clients."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=b"%29 main\n"),
            subprocess.CalledProcessError(1, "tmux", stderr=b"no such session"),
        ]

        result = get_pane_client_tty("%29")

        assert result.success is False
        assert result.session_name == "main"
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND


class TestSelectPane:
    """Tests for select_pane function."""

    def test_no_pane_id(self):
        result = select_pane("")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    def test_none_pane_id(self):
        result = select_pane(None)
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_success(self, mock_run):
        """Test successful pane selection (select-window + select-pane)."""
        mock_run.return_value = MagicMock(returncode=0)

        result = select_pane("%29")

        assert result.success is True
        assert result.latency_ms >= 0
        assert mock_run.call_count == 2

        # First call: select-window
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0] == ["tmux", "select-window", "-t", "%29"]

        # Second call: select-pane
        second_call = mock_run.call_args_list[1]
        assert second_call[0][0] == ["tmux", "select-pane", "-t", "%29"]

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_not_found(self, mock_run):
        """Test when pane doesn't exist."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "tmux", stderr=b"can't find pane: %99"
        )

        result = select_pane("%99")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run):
        """Test when tmux binary not on PATH."""
        mock_run.side_effect = FileNotFoundError()

        result = select_pane("%29")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_timeout(self, mock_run):
        """Test timeout during pane selection."""
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

        result = select_pane("%29")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_unexpected_error(self, mock_run):
        """Test unexpected exception during pane selection."""
        mock_run.side_effect = RuntimeError("something broke")

        result = select_pane("%29")

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.UNKNOWN


class TestWaitResult:
    """Tests for WaitResult named tuple."""

    def test_matched_result(self):
        result = WaitResult(matched=True, content="hello", elapsed_ms=100)
        assert result.matched is True
        assert result.content == "hello"
        assert result.elapsed_ms == 100
        assert result.error_type is None

    def test_timeout_result(self):
        result = WaitResult(
            matched=False,
            content="",
            elapsed_ms=5000,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message="not found",
        )
        assert result.matched is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT


class TestWaitForPattern:
    """Tests for wait_for_pattern function."""

    def test_invalid_pane_id(self):
        result = wait_for_pattern("bad", r"hello")
        assert result.matched is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    def test_match_on_first_poll(self, mock_dump, mock_capture):
        mock_capture.return_value = "  1. Yes\n  2. No\n"
        result = wait_for_pattern(
            "%5", r"^\s*\d+\.\s+", timeout_ms=1000, poll_interval_ms=50
        )
        assert result.matched is True
        assert "Yes" in result.content
        assert result.elapsed_ms >= 0
        mock_dump.assert_not_called()

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    def test_match_after_retries(self, mock_dump, mock_capture):
        mock_capture.side_effect = [
            "",
            "Loading...\n",
            "  1. Yes\n  2. No\n",
        ]
        result = wait_for_pattern(
            "%5", r"^\s*\d+\.\s+", timeout_ms=5000, poll_interval_ms=10
        )
        assert result.matched is True
        assert mock_capture.call_count == 3
        mock_dump.assert_not_called()

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    def test_timeout_calls_diagnostic_dump(self, mock_dump, mock_capture):
        mock_capture.return_value = "no match here\n"
        result = wait_for_pattern(
            "%5", r"IMPOSSIBLE_PATTERN", timeout_ms=50, poll_interval_ms=10
        )
        assert result.matched is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT
        assert result.content == "no match here\n"
        mock_dump.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    def test_content_preserved_on_match(self, mock_dump, mock_capture):
        mock_capture.return_value = "prompt $ hello world\n"
        result = wait_for_pattern(
            "%5", r"hello world", timeout_ms=1000, poll_interval_ms=50
        )
        assert result.matched is True
        assert "hello world" in result.content

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    def test_empty_capture_returns_timeout(self, mock_dump, mock_capture):
        mock_capture.return_value = ""
        result = wait_for_pattern(
            "%5", r"anything", timeout_ms=50, poll_interval_ms=10
        )
        assert result.matched is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT


class TestDiagnosticDump:
    """Tests for _diagnostic_dump helper."""

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_logs_content(self, mock_capture):
        mock_capture.return_value = "line 1\nline 2\n"
        with patch("claude_headspace.services.tmux_bridge.logger") as mock_logger:
            _diagnostic_dump("%5", "test context")
            mock_logger.warning.assert_called_once()
            call_msg = mock_logger.warning.call_args[0][0]
            assert "test context" in call_msg
            assert "line 1" in call_msg

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_truncates_long_content(self, mock_capture):
        mock_capture.return_value = "x" * 3000
        with patch("claude_headspace.services.tmux_bridge.logger") as mock_logger:
            _diagnostic_dump("%5", "long output")
            call_msg = mock_logger.warning.call_args[0][0]
            assert "truncated" in call_msg

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_empty_capture(self, mock_capture):
        mock_capture.return_value = ""
        with patch("claude_headspace.services.tmux_bridge.logger") as mock_logger:
            _diagnostic_dump("%5", "empty")
            call_msg = mock_logger.warning.call_args[0][0]
            assert "empty" in call_msg.lower()

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_exception_handled(self, mock_capture):
        mock_capture.side_effect = RuntimeError("boom")
        with patch("claude_headspace.services.tmux_bridge.logger") as mock_logger:
            _diagnostic_dump("%5", "error case")  # should not raise
            mock_logger.warning.assert_called_once()


class TestHealthCheckLevel:
    """Tests for HealthCheckLevel enum."""

    def test_enum_values(self):
        assert HealthCheckLevel.EXISTS == "exists"
        assert HealthCheckLevel.COMMAND == "command"
        assert HealthCheckLevel.PROCESS_TREE == "process_tree"

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_exists_level_only_checks_pane_exists(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5\n%10\n",
        )
        result = check_health("%5", level=HealthCheckLevel.EXISTS)
        assert result.available is True
        # EXISTS level does not determine running status
        assert result.running is False

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_exists_level_pane_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%10\n",
        )
        result = check_health("%5", level=HealthCheckLevel.EXISTS)
        assert result.available is False

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_command_level_detects_claude(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 claude\n",
        )
        result = check_health("%5", level=HealthCheckLevel.COMMAND)
        assert result.available is True
        assert result.running is True

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_command_level_detects_no_claude(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 bash\n",
        )
        result = check_health("%5", level=HealthCheckLevel.COMMAND)
        assert result.available is True
        assert result.running is False

    @patch("claude_headspace.services.tmux_bridge.get_pane_pid")
    @patch("claude_headspace.services.tmux_bridge._is_process_in_tree")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_process_tree_level_claude_running(self, mock_run, mock_tree, mock_pid):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 bash\n",
        )
        mock_pid.return_value = 12345
        mock_tree.return_value = True

        result = check_health("%5", level=HealthCheckLevel.PROCESS_TREE)
        assert result.available is True
        assert result.running is True
        assert result.pid == 12345

    @patch("claude_headspace.services.tmux_bridge.get_pane_pid")
    @patch("claude_headspace.services.tmux_bridge._is_process_in_tree")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_process_tree_level_no_claude(self, mock_run, mock_tree, mock_pid):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 bash\n",
        )
        mock_pid.return_value = 12345
        mock_tree.return_value = False

        result = check_health("%5", level=HealthCheckLevel.PROCESS_TREE)
        assert result.available is True
        assert result.running is False
        assert result.pid == 12345

    @patch("claude_headspace.services.tmux_bridge.get_pane_pid")
    @patch("claude_headspace.services.tmux_bridge._is_process_in_tree")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_process_tree_fallback_on_error(self, mock_run, mock_tree, mock_pid):
        """When tree check returns None, falls back to command-level result."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 node\n",
        )
        mock_pid.return_value = 12345
        mock_tree.return_value = None  # Can't determine

        result = check_health("%5", level=HealthCheckLevel.PROCESS_TREE)
        assert result.available is True
        assert result.running is True  # Falls back to command-level (node detected)

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_custom_process_names(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 python\n",
        )
        result = check_health(
            "%5", level=HealthCheckLevel.COMMAND, process_names=("python",)
        )
        assert result.available is True
        assert result.running is True

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_custom_process_names_no_match(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 bash\n",
        )
        result = check_health(
            "%5", level=HealthCheckLevel.COMMAND, process_names=("python",)
        )
        assert result.available is True
        assert result.running is False

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_default_level_is_command(self, mock_run):
        """Default check_health() behavior should match COMMAND level."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5 claude\n",
        )
        result = check_health("%5")
        assert result.available is True
        assert result.running is True


class TestGetPanePid:
    """Tests for get_pane_pid function."""

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="%5 12345\n%10 99999\n",
        )
        assert get_pane_pid("%5") == 12345

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_pane_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="%10 99999\n",
        )
        assert get_pane_pid("%5") is None

    def test_invalid_pane_id(self):
        assert get_pane_pid("bad") is None

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_failure(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert get_pane_pid("%5") is None


class TestSendLockRegistry:
    """Tests for per-pane send lock registry (WU4)."""

    def test_get_send_lock_returns_rlock(self):
        """_get_send_lock returns a threading.RLock."""
        import threading

        lock = _get_send_lock("%99")
        assert isinstance(lock, type(threading.RLock()))
        # Cleanup
        release_send_lock("%99")

    def test_same_pane_returns_same_lock(self):
        """Same pane ID returns the same lock object."""
        lock1 = _get_send_lock("%88")
        lock2 = _get_send_lock("%88")
        assert lock1 is lock2
        release_send_lock("%88")

    def test_different_panes_return_different_locks(self):
        """Different pane IDs return different lock objects."""
        lock1 = _get_send_lock("%77")
        lock2 = _get_send_lock("%78")
        assert lock1 is not lock2
        release_send_lock("%77")
        release_send_lock("%78")

    def test_release_send_lock_removes_entry(self):
        """release_send_lock removes the pane's lock from the registry."""
        _get_send_lock("%66")
        assert "%66" in _send_locks
        release_send_lock("%66")
        assert "%66" not in _send_locks

    def test_release_nonexistent_lock_is_noop(self):
        """Releasing a lock for a pane that was never registered is safe."""
        release_send_lock("%999")  # Should not raise

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_concurrent_sends_to_same_pane_are_serialized(self, mock_run):
        """Two concurrent send_text calls to the same pane don't interleave."""
        import threading

        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        call_order = []

        original_sleep = __import__("time").sleep

        def tracked_send(label):
            """Send text and record when we enter/exit the lock."""
            call_order.append(f"{label}_start")
            send_text("%50", f"msg_{label}", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=False)
            call_order.append(f"{label}_end")

        t1 = threading.Thread(target=tracked_send, args=("A",))
        t2 = threading.Thread(target=tracked_send, args=("B",))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Both should complete (no deadlock)
        assert "A_start" in call_order
        assert "A_end" in call_order
        assert "B_start" in call_order
        assert "B_end" in call_order
        # One must finish before the other starts (serialized by lock)
        a_end = call_order.index("A_end")
        b_end = call_order.index("B_end")
        a_start = call_order.index("A_start")
        b_start = call_order.index("B_start")
        # Either A finishes before B starts, or B finishes before A starts
        assert (a_end < b_start) or (b_end < a_start), (
            f"Sends were not serialized: {call_order}"
        )
        release_send_lock("%50")

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_sends_to_different_panes_are_independent(self, mock_run):
        """send_text to different panes can proceed concurrently."""
        import threading

        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        results = {}

        def send_to_pane(pane_id, label):
            result = send_text(pane_id, f"msg_{label}", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=False)
            results[label] = result.success

        t1 = threading.Thread(target=send_to_pane, args=("%51", "A"))
        t2 = threading.Thread(target=send_to_pane, args=("%52", "B"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert results["A"] is True
        assert results["B"] is True
        release_send_lock("%51")
        release_send_lock("%52")

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_interrupt_and_send_text_reentrant(self, mock_run, mock_capture):
        """interrupt_and_send_text can call send_text without deadlocking (RLock)."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        mock_capture.return_value = ""

        result = interrupt_and_send_text(
            "%53", "hello",
            text_enter_delay_ms=0,
            interrupt_settle_ms=0,
            verify_enter=False,
        )
        assert result.success is True
        release_send_lock("%53")


class TestKillSession:
    """Tests for kill_session function (WU5)."""

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = kill_session("hs-test-abc123")
        assert result.success is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["tmux", "kill-session", "-t", "hs-test-abc123"]

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_with_socket_path(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = kill_session("hs-test", socket_path="/tmp/tmux-1000/hs")
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert cmd == ["tmux", "-S", "/tmp/tmux-1000/hs", "kill-session", "-t", "hs-test"]

    def test_empty_session_name(self):
        result = kill_session("")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.NO_PANE_ID

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_session_not_found(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "tmux", stderr=b"can't find session: hs-test"
        )
        result = kill_session("hs-test")
        assert result.success is False

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_tmux_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = kill_session("hs-test")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)
        result = kill_session("hs-test")
        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.TIMEOUT


class TestListPanesSocketPath:
    """Tests for list_panes socket_path parameter (WU5)."""

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_default_no_socket(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5\tsession1\tbash\t/home\n",
        )
        result = list_panes()
        cmd = mock_run.call_args[0][0]
        assert "-S" not in cmd

    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_with_socket_path(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"%5\tsession1\tbash\t/home\n",
        )
        result = list_panes(socket_path="/tmp/tmux-hs")
        cmd = mock_run.call_args[0][0]
        assert cmd[1:3] == ["-S", "/tmp/tmux-hs"]


class TestPaneContentChanged:
    """Tests for _pane_content_changed helper."""

    def test_identical_content(self):
        assert _pane_content_changed("line1\nline2\n", "line1\nline2\n") is False

    def test_different_content(self):
        assert _pane_content_changed("line1\nline2\n", "line1\nline3\n") is True

    def test_whitespace_differences_ignored(self):
        assert _pane_content_changed("  line1  \n", "line1\n") is False

    def test_blank_lines_ignored(self):
        assert _pane_content_changed("line1\n\n\n", "line1\n") is False

    def test_both_empty(self):
        assert _pane_content_changed("", "") is False

    def test_empty_vs_content(self):
        assert _pane_content_changed("", "something\n") is True

    def test_content_vs_empty(self):
        assert _pane_content_changed("something\n", "") is True

    def test_additional_line_detected(self):
        assert _pane_content_changed("line1\n", "line1\nline2\n") is True


class TestVerifySubmission:
    """Tests for _verify_submission helper."""

    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_first_attempt_success(self, mock_capture, mock_dump):
        """Content changes on first check → success."""
        mock_capture.return_value = "Processing...\n> "

        result = _verify_submission(
            "%5",
            pre_submit_content="Your input here\n> ",
            timeout=5,
            clear_delay_ms=0,
            verify_delay_ms=0,
            max_retries=3,
        )

        assert result is True
        mock_dump.assert_not_called()

    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_retry_success(self, mock_capture, mock_run, mock_dump):
        """Content unchanged on first check, changes on second → success after retry."""
        mock_run.return_value = MagicMock(returncode=0)
        # First verify check: unchanged. Ghost check: clean. Second verify check: changed.
        mock_capture.side_effect = [
            "Your input here\n> ",  # first verify check (unchanged)
            "> ",  # ghost check (no ghost)
            "Processing...\n",  # second verify check (changed!)
        ]

        result = _verify_submission(
            "%5",
            pre_submit_content="Your input here\n> ",
            timeout=5,
            clear_delay_ms=0,
            verify_delay_ms=0,
            max_retries=3,
        )

        assert result is True
        mock_dump.assert_not_called()
        # Enter was retried once
        enter_calls = [
            c for c in mock_run.call_args_list
            if c[0][0] == ["tmux", "send-keys", "-t", "%5", "Enter"]
        ]
        assert len(enter_calls) == 1

    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_all_retries_exhausted(self, mock_capture, mock_run, mock_dump):
        """Content never changes → returns False after all retries."""
        mock_run.return_value = MagicMock(returncode=0)
        # Always return the same content (unchanged)
        mock_capture.return_value = "Stuck input\n> "

        result = _verify_submission(
            "%5",
            pre_submit_content="Stuck input\n> ",
            timeout=5,
            clear_delay_ms=0,
            verify_delay_ms=0,
            max_retries=2,
        )

        assert result is False
        mock_dump.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge._diagnostic_dump")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    def test_ghost_dismiss_during_retry(self, mock_capture, mock_run, mock_dump):
        """Ghost text detected during retry → dismissed with Escape before retrying Enter."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.side_effect = [
            "Your input here\n> ",  # first verify check (unchanged)
            "> \x1b[2mghost\x1b[22m",  # ghost check: ghost detected!
            "Processing...\n",  # second verify check (changed!)
        ]

        result = _verify_submission(
            "%5",
            pre_submit_content="Your input here\n> ",
            timeout=5,
            clear_delay_ms=0,
            verify_delay_ms=0,
            max_retries=3,
        )

        assert result is True
        # Should have sent Escape (dismiss ghost) + Enter (retry)
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert ["tmux", "send-keys", "-t", "%5", "Escape"] in calls
        assert ["tmux", "send-keys", "-t", "%5", "Enter"] in calls


class TestSendTextVerifyEnter:
    """Tests for send_text with verify_enter=True."""

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_verify_enter_true_calls_verification(self, mock_run, mock_capture, mock_verify):
        """verify_enter=True triggers _verify_submission after Enter."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "
        mock_verify.return_value = True

        result = send_text(
            "%5", "hello", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=True,
        )

        assert result.success is True
        mock_verify.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_verify_enter_false_skips_verification(self, mock_run, mock_capture, mock_verify):
        """verify_enter=False skips _verify_submission entirely."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "

        result = send_text(
            "%5", "hello", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=False,
        )

        assert result.success is True
        mock_verify.assert_not_called()

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_verify_enter_failure_returns_send_failed(self, mock_run, mock_capture, mock_verify):
        """When verification fails, returns SEND_FAILED error."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "
        mock_verify.return_value = False

        result = send_text(
            "%5", "hello", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=True,
        )

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.SEND_FAILED
        assert "Enter key not accepted" in result.error_message

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_detect_ghost_text_false_skips_ghost_detection(self, mock_run, mock_capture):
        """detect_ghost_text=False skips all ghost detection and Escape sends."""
        mock_run.return_value = MagicMock(returncode=0)

        result = send_text(
            "%5", "hello", text_enter_delay_ms=0, clear_delay_ms=0,
            verify_enter=False, detect_ghost_text=False,
        )

        assert result.success is True
        # Only text + Enter — no ghost capture at all
        assert mock_run.call_count == 2
        mock_capture.assert_not_called()

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_skip_verify_hint_skips_verification(self, mock_run, mock_capture, mock_verify):
        """skip_verify_hint=True skips verification even when verify_enter=True."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "

        result = send_text(
            "%5", "hello", text_enter_delay_ms=0, clear_delay_ms=0,
            verify_enter=True, skip_verify_hint=True,
        )

        assert result.success is True
        mock_verify.assert_not_called()


class TestSendTextSanitisation:
    """Tests for send_text text sanitisation (rstrip only)."""

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_newlines_preserved_in_body(self, mock_run, mock_capture, mock_verify):
        """Internal newlines are preserved (not flattened to spaces)."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "
        mock_verify.return_value = True

        text_with_newlines = "line1\nline2\nline3"
        send_text("%5", text_with_newlines, text_enter_delay_ms=0, clear_delay_ms=0)

        # Find the literal text send call (has -l flag)
        text_call = [
            c for c in mock_run.call_args_list
            if "-l" in c[0][0]
        ]
        assert len(text_call) == 1
        # The text should still contain newlines
        sent_text = text_call[0][0][0][-1]
        assert "\n" in sent_text

    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_trailing_whitespace_stripped(self, mock_run, mock_capture):
        """Trailing whitespace is stripped."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "> "

        send_text("%5", "hello   \n\n", text_enter_delay_ms=0, clear_delay_ms=0, verify_enter=False)

        text_call = [c for c in mock_run.call_args_list if "-l" in c[0][0]]
        sent_text = text_call[0][0][0][-1]
        assert sent_text == "hello"


class TestSendKeysVerifyEnter:
    """Tests for send_keys with verify_enter parameter."""

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_verify_enter_true_triggers_verification(self, mock_run, mock_capture, mock_verify):
        """verify_enter=True captures baseline and calls _verify_submission."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "  1. Yes\n  2. No\n"
        mock_verify.return_value = True

        result = send_keys(
            "%5", "Down", "Enter",
            sequential_delay_ms=0, verify_enter=True,
        )

        assert result.success is True
        mock_verify.assert_called_once()
        # Baseline capture should have been called
        mock_capture.assert_called_once()

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_verify_enter_false_skips_verification(self, mock_run, mock_verify):
        """Default verify_enter=False does not verify."""
        mock_run.return_value = MagicMock(returncode=0)

        result = send_keys("%5", "Down", "Enter", sequential_delay_ms=0)

        assert result.success is True
        mock_verify.assert_not_called()

    @patch("claude_headspace.services.tmux_bridge._verify_submission")
    @patch("claude_headspace.services.tmux_bridge.capture_pane")
    @patch("claude_headspace.services.tmux_bridge.subprocess.run")
    def test_verify_enter_failure_returns_send_failed(self, mock_run, mock_capture, mock_verify):
        """When verification fails, returns SEND_FAILED."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_capture.return_value = "options still showing\n"
        mock_verify.return_value = False

        result = send_keys(
            "%5", "Down", "Enter",
            sequential_delay_ms=0, verify_enter=True,
        )

        assert result.success is False
        assert result.error_type == TmuxBridgeErrorType.SEND_FAILED
