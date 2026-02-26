"""Tests for the API call logger middleware service."""

import json
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.api_call_logger import (
    CAPTURED_PREFIXES,
    MAX_PAYLOAD_BYTES,
    TRUNCATION_INDICATOR,
    ApiCallLogger,
    _detect_auth_status,
    _extract_safe_headers,
    _should_capture,
    _truncate_body,
)


class TestShouldCapture:
    """Tests for _should_capture route prefix matching."""

    def test_captures_remote_agents(self):
        """Test that remote agents API paths are captured."""
        assert _should_capture("/api/remote_agents/create") is True
        assert _should_capture("/api/remote_agents/123/alive") is True
        assert _should_capture("/api/remote_agents/123/shutdown") is True

    def test_captures_voice_bridge(self):
        """Test that voice bridge API paths are captured."""
        assert _should_capture("/api/voice_bridge/query") is True
        assert _should_capture("/api/voice_bridge/status") is True

    def test_captures_embed(self):
        """Test that embed paths are captured."""
        assert _should_capture("/embed/123") is True
        assert _should_capture("/embed/456/chat") is True

    def test_ignores_hooks(self):
        """Test that hook endpoints are NOT captured."""
        assert _should_capture("/hook/session-start") is False
        assert _should_capture("/hook/stop") is False

    def test_ignores_dashboard(self):
        """Test that dashboard routes are NOT captured."""
        assert _should_capture("/") is False
        assert _should_capture("/dashboard") is False
        assert _should_capture("/logging") is False

    def test_ignores_internal_apis(self):
        """Test that internal API routes are NOT captured."""
        assert _should_capture("/api/events") is False
        assert _should_capture("/api/inference/calls") is False
        assert _should_capture("/api/sessions") is False
        assert _should_capture("/api/focus/123") is False

    def test_ignores_sse_stream(self):
        """Test that SSE stream is NOT captured."""
        assert _should_capture("/api/events/stream") is False

    def test_ignores_health(self):
        """Test that health endpoint is NOT captured."""
        assert _should_capture("/health") is False


class TestExtractSafeHeaders:
    """Tests for _extract_safe_headers."""

    def test_extracts_safe_headers(self):
        """Test that safe headers are extracted."""
        headers = [
            ("Content-Type", "application/json"),
            ("Accept", "text/html"),
            ("User-Agent", "TestBot/1.0"),
        ]
        result = _extract_safe_headers(headers)
        assert result["Content-Type"] == "application/json"
        assert result["Accept"] == "text/html"
        assert result["User-Agent"] == "TestBot/1.0"

    def test_redacts_authorization(self):
        """Test that Authorization header value is redacted."""
        headers = [
            ("Authorization", "Bearer secret-token-123"),
            ("Content-Type", "application/json"),
        ]
        result = _extract_safe_headers(headers)
        assert result["Authorization"] == "[REDACTED]"
        assert result["Content-Type"] == "application/json"

    def test_skips_unknown_headers(self):
        """Test that non-safe, non-auth headers are skipped."""
        headers = [
            ("X-Custom-Header", "value"),
            ("X-Secret", "secret"),
        ]
        result = _extract_safe_headers(headers)
        assert "X-Custom-Header" not in result
        assert "X-Secret" not in result

    def test_empty_headers(self):
        """Test with no headers."""
        result = _extract_safe_headers([])
        assert result == {}


class TestTruncateBody:
    """Tests for _truncate_body."""

    def test_none_body(self):
        """Test that None body returns None."""
        assert _truncate_body(None) is None

    def test_small_body_unchanged(self):
        """Test that bodies under the limit are unchanged."""
        body = "small body"
        assert _truncate_body(body) == body

    def test_large_body_truncated(self):
        """Test that bodies over 1MB are truncated."""
        body = "x" * (MAX_PAYLOAD_BYTES + 100)
        result = _truncate_body(body)
        assert len(result) == MAX_PAYLOAD_BYTES + len(TRUNCATION_INDICATOR)
        assert result.endswith(TRUNCATION_INDICATOR)

    def test_exact_limit_not_truncated(self):
        """Test that bodies exactly at the limit are not truncated."""
        body = "x" * MAX_PAYLOAD_BYTES
        result = _truncate_body(body)
        assert result == body


class TestDetectAuthStatus:
    """Tests for _detect_auth_status."""

    def test_401_returns_failed(self, app):
        """Test that 401 response status returns 'failed'."""
        with app.test_request_context("/api/remote_agents/create"):
            result = _detect_auth_status(401)
            assert result == "failed"

    def test_403_returns_failed(self, app):
        """Test that 403 response status returns 'failed'."""
        with app.test_request_context("/api/remote_agents/create"):
            result = _detect_auth_status(403)
            assert result == "failed"

    def test_bearer_token_returns_authenticated(self, app):
        """Test that Authorization header presence returns 'authenticated'."""
        with app.test_request_context(
            "/api/voice_bridge/query",
            headers={"Authorization": "Bearer token123"},
        ):
            result = _detect_auth_status(200)
            assert result == "authenticated"

    def test_session_token_in_query_returns_authenticated(self, app):
        """Test that session token in query params returns 'authenticated'."""
        with app.test_request_context(
            "/api/remote_agents/create?token=abc123",
        ):
            result = _detect_auth_status(200)
            assert result == "authenticated"

    def test_no_auth_returns_unauthenticated(self, app):
        """Test that no auth indicators returns 'unauthenticated'."""
        with app.test_request_context("/api/remote_agents/create"):
            result = _detect_auth_status(200)
            assert result == "unauthenticated"

    def test_localhost_voice_bridge_returns_bypassed(self, app):
        """Test that localhost + voice bridge returns 'bypassed'."""
        with app.test_request_context(
            "/api/voice_bridge/query",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        ):
            result = _detect_auth_status(200)
            assert result == "bypassed"


class TestApiCallLoggerMiddleware:
    """Tests for the ApiCallLogger middleware integration."""

    def test_captures_remote_agent_request(self, app, client):
        """Test that requests to remote agent endpoints are captured."""
        with patch("claude_headspace.database.db") as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit = MagicMock()

            # Make a request to a captured prefix
            response = client.post(
                "/api/remote_agents/create",
                data=json.dumps({"name": "test-agent"}),
                content_type="application/json",
            )
            # The route may return 404 or another status, but the middleware fires.
            # Verify the middleware attempted to persist
            mock_db.session.add.assert_called_once()

    def test_ignores_internal_routes(self, app, client):
        """Test that internal routes are NOT captured."""
        with patch("claude_headspace.database.db") as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit = MagicMock()

            # Health endpoint should not be captured
            response = client.get("/health")
            # The middleware should NOT have called db.session.add for this route
            mock_db.session.add.assert_not_called()

    def test_fault_tolerance_db_failure(self, app, client):
        """Test that DB write failure does not break the API response."""
        with patch("claude_headspace.database.db") as mock_db:
            mock_db.session.add.side_effect = Exception("DB write failed")

            # The request should still succeed even if logging fails
            response = client.get("/health")
            assert response.status_code == 200

    def test_sse_broadcast_after_capture(self, app, client):
        """Test that an SSE event is broadcast after capture."""
        mock_broadcaster = MagicMock()
        app.extensions["broadcaster"] = mock_broadcaster

        with patch("claude_headspace.database.db") as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit = MagicMock()

            response = client.post(
                "/api/remote_agents/create",
                data=json.dumps({"name": "test"}),
                content_type="application/json",
            )

            # The middleware should have broadcast an api_call_logged event
            mock_broadcaster.broadcast.assert_called_once()
            call_args = mock_broadcaster.broadcast.call_args
            assert call_args[0][0] == "api_call_logged"


class TestApiCallLoggerInit:
    """Tests for ApiCallLogger initialization."""

    def test_init_with_app(self, app):
        """Test that ApiCallLogger initializes correctly with an app."""
        logger = ApiCallLogger(app=app)
        assert logger.app is app

    def test_init_without_app(self):
        """Test that ApiCallLogger can be created without an app."""
        logger = ApiCallLogger()
        assert logger.app is None

    def test_init_app_later(self, app):
        """Test that init_app can be called after creation."""
        logger = ApiCallLogger()
        logger.init_app(app)
        assert logger.app is app
