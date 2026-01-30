"""Tests for the SSE endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.sse import (
    parse_filter_types,
    parse_int_param,
    sse_bp,
)


class TestParseFilterTypes:
    """Tests for parse_filter_types function."""

    def test_none_input(self):
        """Test with None input."""
        assert parse_filter_types(None) is None

    def test_empty_string(self):
        """Test with empty string."""
        assert parse_filter_types("") is None

    def test_single_type(self):
        """Test with single type."""
        result = parse_filter_types("state_transition")
        assert result == ["state_transition"]

    def test_multiple_types(self):
        """Test with multiple types."""
        result = parse_filter_types("state_transition,turn_detected,agent_created")
        assert result == ["state_transition", "turn_detected", "agent_created"]

    def test_types_with_spaces(self):
        """Test with types containing spaces."""
        result = parse_filter_types("state_transition, turn_detected , agent_created")
        assert result == ["state_transition", "turn_detected", "agent_created"]

    def test_empty_items_filtered(self):
        """Test that empty items are filtered out."""
        result = parse_filter_types("state_transition,,turn_detected")
        assert result == ["state_transition", "turn_detected"]


class TestParseIntParam:
    """Tests for parse_int_param function."""

    def test_none_input(self):
        """Test with None input."""
        assert parse_int_param(None) is None

    def test_empty_string(self):
        """Test with empty string."""
        assert parse_int_param("") is None

    def test_valid_int(self):
        """Test with valid integer string."""
        assert parse_int_param("42") == 42

    def test_negative_int(self):
        """Test with negative integer."""
        assert parse_int_param("-5") == -5

    def test_invalid_int(self):
        """Test with invalid integer string."""
        assert parse_int_param("not_a_number") is None

    def test_float_string(self):
        """Test with float string."""
        assert parse_int_param("3.14") is None


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(sse_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestSSEEndpoint:
    """Tests for the SSE endpoint."""

    def test_connection_limit_rejected(self, client):
        """Test that connection is rejected when limit reached."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = False
        mock_broadcaster.retry_after = 5

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            response = client.get("/api/events/stream")

            assert response.status_code == 503
            assert response.headers.get("Retry-After") == "5"
            assert b"connection limit" in response.data

    def test_registration_failure(self, client):
        """Test handling registration failure."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = None
        mock_broadcaster.retry_after = 5

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            response = client.get("/api/events/stream")

            assert response.status_code == 503

    def test_content_type(self, client):
        """Test that response has correct content type."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None  # Causes immediate exit

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            response = client.get("/api/events/stream")

            assert response.content_type.startswith("text/event-stream")

    def test_cache_control_header(self, client):
        """Test that cache control header is set."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            response = client.get("/api/events/stream")

            assert response.headers.get("Cache-Control") == "no-cache"

    def test_nginx_buffering_disabled(self, client):
        """Test that nginx buffering is disabled."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            response = client.get("/api/events/stream")

            assert response.headers.get("X-Accel-Buffering") == "no"

    def test_types_filter_passed(self, client):
        """Test that types filter is passed to register_client."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            client.get("/api/events/stream?types=state_transition,turn_detected")

            mock_broadcaster.register_client.assert_called_once_with(
                types=["state_transition", "turn_detected"],
                project_id=None,
                agent_id=None,
            )

    def test_project_id_filter_passed(self, client):
        """Test that project_id filter is passed to register_client."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            client.get("/api/events/stream?project_id=42")

            mock_broadcaster.register_client.assert_called_once_with(
                types=None,
                project_id=42,
                agent_id=None,
            )

    def test_agent_id_filter_passed(self, client):
        """Test that agent_id filter is passed to register_client."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            client.get("/api/events/stream?agent_id=7")

            mock_broadcaster.register_client.assert_called_once_with(
                types=None,
                project_id=None,
                agent_id=7,
            )

    def test_all_filters_combined(self, client):
        """Test with all filters combined."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            client.get("/api/events/stream?types=state_transition&project_id=42&agent_id=7")

            mock_broadcaster.register_client.assert_called_once_with(
                types=["state_transition"],
                project_id=42,
                agent_id=7,
            )

    def test_last_event_id_header_logged(self, client):
        """Test that Last-Event-ID header is logged for reconnection."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            with patch("src.claude_headspace.routes.sse.logger") as mock_logger:
                client.get(
                    "/api/events/stream",
                    headers={"Last-Event-ID": "42"},
                )

                # Verify reconnection was logged
                mock_logger.info.assert_any_call(
                    "SSE client reconnecting from event ID: 42"
                )

    def test_client_unregistered_on_disconnect(self, client):
        """Test that client is unregistered when generator exits."""
        mock_client = MagicMock()
        mock_client.is_active = False

        mock_broadcaster = MagicMock()
        mock_broadcaster.can_accept_connection.return_value = True
        mock_broadcaster.register_client.return_value = "test-client-123"
        mock_broadcaster.get_client.return_value = mock_client
        mock_broadcaster.get_next_event.return_value = None

        with patch(
            "src.claude_headspace.routes.sse.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            # Consume the response to trigger generator
            response = client.get("/api/events/stream")
            list(response.response)  # Consume generator

            mock_broadcaster.unregister_client.assert_called_with("test-client-123")
