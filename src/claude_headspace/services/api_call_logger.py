"""API call logger middleware for capturing external API requests and responses."""

import logging
import time
from datetime import datetime, timezone

from flask import Flask, g, request

logger = logging.getLogger(__name__)

# Max payload size to store (1MB). Payloads larger than this are truncated.
MAX_PAYLOAD_BYTES = 1_000_000
TRUNCATION_INDICATOR = "\n\n... [TRUNCATED at 1MB] ..."

# Route prefixes to capture
CAPTURED_PREFIXES = (
    "/api/remote_agents/",
    "/api/voice_bridge/",
    "/embed/",
)

# Safe request headers to store (lowercase). Authorization values are never stored.
SAFE_HEADERS = frozenset({
    "content-type",
    "accept",
    "user-agent",
    "origin",
    "referer",
    "x-forwarded-for",
    "x-real-ip",
})


def _should_capture(path: str) -> bool:
    """Check if a request path matches captured prefixes."""
    for prefix in CAPTURED_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _extract_safe_headers(headers) -> dict:
    """Extract a safe subset of request headers (no auth token values)."""
    result = {}
    for key, value in headers:
        lower_key = key.lower()
        if lower_key in SAFE_HEADERS:
            result[key] = value
        elif lower_key == "authorization":
            # Record that Authorization was present, but not its value
            result[key] = "[REDACTED]"
    return result


def _truncate_body(body: str | None) -> str | None:
    """Truncate body if it exceeds MAX_PAYLOAD_BYTES."""
    if body is None:
        return None
    if len(body) > MAX_PAYLOAD_BYTES:
        return body[:MAX_PAYLOAD_BYTES] + TRUNCATION_INDICATOR
    return body


def _detect_auth_status(response_status: int) -> str:
    """Detect authentication status from request context and response.

    Uses a heuristic approach:
    - If response is 401/403, auth likely failed
    - If an Authorization header or session token is present, auth was attempted
    - Check for localhost bypass indicators
    """
    # Check for auth failure responses
    if response_status == 401:
        return "failed"
    if response_status == 403:
        # Could be failed auth or CSRF, use "failed" as best guess
        return "failed"

    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        return "authenticated"

    # Check for session token in query params (remote agents / embed pattern)
    if request.args.get("token"):
        return "authenticated"

    # Check for localhost bypass (voice bridge pattern)
    source_ip = request.remote_addr or ""
    if source_ip in ("127.0.0.1", "::1", "localhost"):
        # Voice bridge allows localhost bypass
        if request.path.startswith("/api/voice_bridge/"):
            return "bypassed"

    return "unauthenticated"


def _resolve_entity_ids() -> tuple[int | None, int | None]:
    """Resolve project_id and agent_id from the request context.

    Checks g for values set by route handlers, or extracts from URL path.
    """
    project_id = getattr(g, "api_log_project_id", None)
    agent_id = getattr(g, "api_log_agent_id", None)

    # Try to extract agent_id from URL path for remote agent routes
    # e.g., /api/remote_agents/<agent_id>/alive
    if agent_id is None and request.path.startswith("/api/remote_agents/"):
        parts = request.path.split("/")
        # /api/remote_agents/<id>/...
        if len(parts) >= 4:
            try:
                agent_id = int(parts[3])
            except (ValueError, IndexError):
                pass

    # Try to extract agent_id from embed routes
    # e.g., /embed/<agent_id>
    if agent_id is None and request.path.startswith("/embed/"):
        parts = request.path.split("/")
        if len(parts) >= 3:
            try:
                agent_id = int(parts[2])
            except (ValueError, IndexError):
                pass

    return project_id, agent_id


class ApiCallLogger:
    """Middleware service that captures external API requests and responses.

    Registers Flask before_request/after_request hooks to transparently
    capture HTTP traffic to designated route prefixes.

    Fault-tolerant: logging failures never break the API response.
    """

    def __init__(self, app: Flask | None = None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Register before/after request hooks on the Flask app."""
        self.app = app
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _before_request(self):
        """Record request start time for latency calculation."""
        if _should_capture(request.path):
            g._api_call_start_time = time.monotonic()

    def _after_request(self, response):
        """Capture and persist the API call log after the response is built."""
        if not _should_capture(request.path):
            return response

        try:
            self._persist_log(response)
        except Exception:
            # Fault-tolerant: never break the API response
            logger.exception("Failed to persist API call log for %s %s", request.method, request.path)

        return response

    def _persist_log(self, response) -> None:
        """Build and persist the ApiCallLog record, then broadcast SSE."""
        from ..database import db
        from ..models.api_call_log import ApiCallLog

        # Calculate latency
        start_time = getattr(g, "_api_call_start_time", None)
        latency_ms = None
        if start_time is not None:
            latency_ms = int((time.monotonic() - start_time) * 1000)

        # Extract request data
        request_body = _truncate_body(request.get_data(as_text=True))
        safe_headers = _extract_safe_headers(request.headers)

        # Extract response data
        response_body = None
        try:
            response_body = _truncate_body(response.get_data(as_text=True))
        except Exception:
            logger.debug("Could not read response body for API log")

        # Detect auth status
        auth_status = _detect_auth_status(response.status_code)

        # Resolve entity IDs
        project_id, agent_id = _resolve_entity_ids()

        # Build the log record
        log_record = ApiCallLog(
            timestamp=datetime.now(timezone.utc),
            http_method=request.method,
            endpoint_path=request.path,
            query_string=request.query_string.decode("utf-8", errors="replace") if request.query_string else None,
            request_content_type=request.content_type,
            request_headers=safe_headers if safe_headers else None,
            request_body=request_body if request_body else None,
            response_status_code=response.status_code,
            response_content_type=response.content_type,
            response_body=response_body if response_body else None,
            latency_ms=latency_ms,
            source_ip=request.remote_addr,
            auth_status=auth_status,
            project_id=project_id,
            agent_id=agent_id,
        )

        db.session.add(log_record)
        db.session.commit()

        # Broadcast SSE event (metadata only, no payloads)
        self._broadcast_event(log_record)

    def _broadcast_event(self, log_record) -> None:
        """Broadcast an api_call_logged SSE event with metadata only."""
        try:
            from flask import current_app
            broadcaster = current_app.extensions.get("broadcaster")
            if broadcaster is None:
                return

            event_data = {
                "id": log_record.id,
                "timestamp": log_record.timestamp.isoformat() if log_record.timestamp else None,
                "http_method": log_record.http_method,
                "endpoint_path": log_record.endpoint_path,
                "response_status_code": log_record.response_status_code,
                "latency_ms": log_record.latency_ms,
                "source_ip": log_record.source_ip,
                "auth_status": log_record.auth_status,
                "project_id": log_record.project_id,
                "agent_id": log_record.agent_id,
            }

            broadcaster.broadcast("api_call_logged", event_data)
        except Exception:
            logger.debug("Failed to broadcast api_call_logged event", exc_info=True)
