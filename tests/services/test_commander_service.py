"""Tests for commander service."""

import json
import os
import socket
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.commander_service import (
    CommanderErrorType,
    HealthResult,
    SendResult,
    check_health,
    check_socket_exists,
    get_socket_path,
    send_text,
)


class TestGetSocketPath:
    """Tests for socket path derivation."""

    def test_derives_path_from_session_id(self):
        path = get_socket_path("abc123")
        assert path == "/tmp/claudec-abc123.sock"

    def test_custom_prefix(self):
        path = get_socket_path("abc123", prefix="/var/run/commander-")
        assert path == "/var/run/commander-abc123.sock"

    def test_empty_session_id(self):
        path = get_socket_path("")
        assert path == "/tmp/claudec-.sock"


class TestCheckSocketExists:
    """Tests for socket file existence check."""

    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_socket_exists(self, mock_exists):
        mock_exists.return_value = True
        assert check_socket_exists("abc123") is True
        mock_exists.assert_called_once_with("/tmp/claudec-abc123.sock")

    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_socket_not_exists(self, mock_exists):
        mock_exists.return_value = False
        assert check_socket_exists("abc123") is False


class TestSendText:
    """Tests for send_text function."""

    def test_no_session_id(self):
        result = send_text("", "hello")
        assert result.success is False
        assert result.error_type == CommanderErrorType.NO_SESSION_ID

    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_socket_not_found(self, mock_exists):
        mock_exists.return_value = False
        result = send_text("abc123", "hello")
        assert result.success is False
        assert result.error_type == CommanderErrorType.SOCKET_NOT_FOUND

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_send_success(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps({"status": "sent"}).encode()

        result = send_text("abc123", "1")

        assert result.success is True
        assert result.latency_ms >= 0
        mock_sock.connect.assert_called_once_with("/tmp/claudec-abc123.sock")
        # Verify JSON message sent
        call_args = mock_sock.sendall.call_args[0][0]
        sent_data = json.loads(call_args.decode().strip())
        assert sent_data == {"action": "send", "text": "1"}

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_send_error_response(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps(
            {"status": "error", "error": "invalid action"}
        ).encode()

        result = send_text("abc123", "hello")

        assert result.success is False
        assert result.error_type == CommanderErrorType.SEND_FAILED

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_send_empty_response_treated_as_success(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b""

        result = send_text("abc123", "yes")

        assert result.success is True

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_connection_refused(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError()

        result = send_text("abc123", "hello")

        assert result.success is False
        assert result.error_type == CommanderErrorType.CONNECTION_REFUSED

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_timeout(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = socket.timeout()

        result = send_text("abc123", "hello")

        assert result.success is False
        assert result.error_type == CommanderErrorType.TIMEOUT

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_broken_pipe(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.sendall.side_effect = BrokenPipeError()

        result = send_text("abc123", "hello")

        assert result.success is False
        assert result.error_type == CommanderErrorType.PROCESS_DEAD


class TestCheckHealth:
    """Tests for check_health function."""

    def test_no_session_id(self):
        result = check_health("")
        assert result.available is False
        assert result.error_type == CommanderErrorType.NO_SESSION_ID

    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_socket_not_found(self, mock_exists):
        mock_exists.return_value = False
        result = check_health("abc123")
        assert result.available is False
        assert result.error_type == CommanderErrorType.SOCKET_NOT_FOUND

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_healthy(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = json.dumps(
            {"running": True, "socket": "/tmp/claudec-abc123.sock", "pid": 12345}
        ).encode()

        result = check_health("abc123")

        assert result.available is True
        assert result.running is True
        assert result.pid == 12345

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_connection_refused(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError()

        result = check_health("abc123")

        assert result.available is False
        assert result.error_type == CommanderErrorType.CONNECTION_REFUSED

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_timeout(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.connect.side_effect = socket.timeout()

        result = check_health("abc123")

        assert result.available is False
        assert result.error_type == CommanderErrorType.TIMEOUT

    @patch("claude_headspace.services.commander_service.socket.socket")
    @patch("claude_headspace.services.commander_service.os.path.exists")
    def test_empty_response_treated_as_available(self, mock_exists, mock_socket_class):
        mock_exists.return_value = True
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = b""

        result = check_health("abc123")

        assert result.available is True


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
            error_type=CommanderErrorType.TIMEOUT,
            error_message="Timed out",
            latency_ms=2000,
        )
        assert result.success is False
        assert result.error_type == CommanderErrorType.TIMEOUT


class TestHealthResult:
    """Tests for HealthResult named tuple."""

    def test_available_result(self):
        result = HealthResult(available=True, running=True, pid=12345)
        assert result.available is True
        assert result.pid == 12345

    def test_unavailable_result(self):
        result = HealthResult(
            available=False,
            error_type=CommanderErrorType.SOCKET_NOT_FOUND,
        )
        assert result.available is False


class TestCommanderErrorType:
    """Tests for CommanderErrorType enum."""

    def test_error_types_are_strings(self):
        assert CommanderErrorType.SOCKET_NOT_FOUND == "socket_not_found"
        assert CommanderErrorType.CONNECTION_REFUSED == "connection_refused"
        assert CommanderErrorType.TIMEOUT == "timeout"
        assert CommanderErrorType.PROCESS_DEAD == "process_dead"
        assert CommanderErrorType.SEND_FAILED == "send_failed"
        assert CommanderErrorType.NO_SESSION_ID == "no_session_id"
        assert CommanderErrorType.UNKNOWN == "unknown"
