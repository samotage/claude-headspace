"""Commander service for communicating with claude-commander Unix domain sockets.

Provides functionality to send text input to Claude Code sessions via the
claude-commander (claudec) socket protocol, and to check socket health/availability.
"""

import json
import logging
import os
import socket
import time
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SOCKET_TIMEOUT = 2  # seconds
DEFAULT_SOCKET_PATH_PREFIX = "/tmp/claudec-"


class CommanderErrorType(str, Enum):
    """Error types for commander operations."""

    SOCKET_NOT_FOUND = "socket_not_found"
    CONNECTION_REFUSED = "connection_refused"
    TIMEOUT = "timeout"
    PROCESS_DEAD = "process_dead"
    SEND_FAILED = "send_failed"
    NO_SESSION_ID = "no_session_id"
    UNKNOWN = "unknown"


class SendResult(NamedTuple):
    """Result of a send operation."""

    success: bool
    error_type: CommanderErrorType | None = None
    error_message: str | None = None
    latency_ms: int = 0


class HealthResult(NamedTuple):
    """Result of a health check operation."""

    available: bool
    running: bool = False
    pid: int | None = None
    error_type: CommanderErrorType | None = None
    error_message: str | None = None


def get_socket_path(session_id: str, prefix: str = DEFAULT_SOCKET_PATH_PREFIX) -> str:
    """Derive the commander socket path from a Claude Code session ID.

    Args:
        session_id: The claude_session_id from the Agent model
        prefix: Socket path prefix (default: /tmp/claudec-)

    Returns:
        Full path to the Unix domain socket
    """
    return f"{prefix}{session_id}.sock"


def check_socket_exists(session_id: str, prefix: str = DEFAULT_SOCKET_PATH_PREFIX) -> bool:
    """Check if the commander socket file exists on the filesystem.

    Args:
        session_id: The claude_session_id from the Agent model
        prefix: Socket path prefix

    Returns:
        True if the socket file exists
    """
    path = get_socket_path(session_id, prefix)
    return os.path.exists(path)


def send_text(
    session_id: str,
    text: str,
    prefix: str = DEFAULT_SOCKET_PATH_PREFIX,
    timeout: float = DEFAULT_SOCKET_TIMEOUT,
) -> SendResult:
    """Send text followed by a newline to a Claude Code session's commander socket.

    Sends a JSON message {"action": "send", "text": "<text>"} over the Unix domain
    socket, simulating typing the text and pressing Enter.

    Args:
        session_id: The claude_session_id from the Agent model
        text: The text to send
        prefix: Socket path prefix
        timeout: Socket connection/read timeout in seconds

    Returns:
        SendResult with success status and optional error information
    """
    if not session_id:
        return SendResult(
            success=False,
            error_type=CommanderErrorType.NO_SESSION_ID,
            error_message="No session ID provided.",
        )

    socket_path = get_socket_path(session_id, prefix)
    start_time = time.time()

    if not os.path.exists(socket_path):
        return SendResult(
            success=False,
            error_type=CommanderErrorType.SOCKET_NOT_FOUND,
            error_message=f"Commander socket not found at {socket_path}",
            latency_ms=int((time.time() - start_time) * 1000),
        )

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(socket_path)

        # Send the JSON message with newline delimiter
        message = json.dumps({"action": "send", "text": text}) + "\n"
        sock.sendall(message.encode("utf-8"))

        # Read response
        response_data = sock.recv(4096)
        latency_ms = int((time.time() - start_time) * 1000)

        sock.close()

        if response_data:
            response = json.loads(response_data.decode("utf-8").strip())
            if response.get("status") == "sent":
                logger.info(
                    f"Sent text to commander socket {socket_path} ({latency_ms}ms)"
                )
                return SendResult(success=True, latency_ms=latency_ms)
            else:
                error_msg = response.get("error", "Unknown error from commander")
                logger.warning(f"Commander send error: {error_msg}")
                return SendResult(
                    success=False,
                    error_type=CommanderErrorType.SEND_FAILED,
                    error_message=error_msg,
                    latency_ms=latency_ms,
                )
        else:
            # Empty response — treat as success (socket accepted the data)
            logger.info(
                f"Sent text to commander socket {socket_path}, no response ({latency_ms}ms)"
            )
            return SendResult(success=True, latency_ms=latency_ms)

    except ConnectionRefusedError:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Commander socket connection refused at {socket_path}")
        return SendResult(
            success=False,
            error_type=CommanderErrorType.CONNECTION_REFUSED,
            error_message="Commander socket connection refused. The session may have ended.",
            latency_ms=latency_ms,
        )

    except socket.timeout:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Commander socket timeout at {socket_path}")
        return SendResult(
            success=False,
            error_type=CommanderErrorType.TIMEOUT,
            error_message=f"Commander socket timed out after {timeout}s.",
            latency_ms=latency_ms,
        )

    except (BrokenPipeError, OSError) as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Commander socket error at {socket_path}: {e}")
        return SendResult(
            success=False,
            error_type=CommanderErrorType.PROCESS_DEAD,
            error_message="Commander process is unreachable. The session may have ended.",
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.exception(f"Unexpected error sending to commander at {socket_path}")
        return SendResult(
            success=False,
            error_type=CommanderErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
            latency_ms=latency_ms,
        )


def check_health(
    session_id: str,
    prefix: str = DEFAULT_SOCKET_PATH_PREFIX,
    timeout: float = DEFAULT_SOCKET_TIMEOUT,
) -> HealthResult:
    """Check whether a commander socket is available and healthy.

    Sends {"action": "status"} to the socket and parses the response.

    Args:
        session_id: The claude_session_id from the Agent model
        prefix: Socket path prefix
        timeout: Socket connection/read timeout in seconds

    Returns:
        HealthResult with availability status
    """
    if not session_id:
        return HealthResult(
            available=False,
            error_type=CommanderErrorType.NO_SESSION_ID,
            error_message="No session ID provided.",
        )

    socket_path = get_socket_path(session_id, prefix)

    if not os.path.exists(socket_path):
        return HealthResult(
            available=False,
            error_type=CommanderErrorType.SOCKET_NOT_FOUND,
            error_message=f"Socket not found at {socket_path}",
        )

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(socket_path)

        message = json.dumps({"action": "status"}) + "\n"
        sock.sendall(message.encode("utf-8"))

        response_data = sock.recv(4096)
        sock.close()

        if response_data:
            response = json.loads(response_data.decode("utf-8").strip())
            running = response.get("running", False)
            pid = response.get("pid")
            return HealthResult(
                available=True,
                running=running,
                pid=pid,
            )

        # Socket exists and accepts connections but gave empty response
        return HealthResult(available=True, running=True)

    except ConnectionRefusedError:
        return HealthResult(
            available=False,
            error_type=CommanderErrorType.CONNECTION_REFUSED,
            error_message="Connection refused — commander process may have exited.",
        )

    except socket.timeout:
        return HealthResult(
            available=False,
            error_type=CommanderErrorType.TIMEOUT,
            error_message="Health check timed out.",
        )

    except (BrokenPipeError, OSError) as e:
        return HealthResult(
            available=False,
            error_type=CommanderErrorType.PROCESS_DEAD,
            error_message=f"Socket error: {e}",
        )

    except Exception as e:
        logger.warning(f"Unexpected health check error for {socket_path}: {e}")
        return HealthResult(
            available=False,
            error_type=CommanderErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
        )
