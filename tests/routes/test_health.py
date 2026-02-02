"""Tests for the health check endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.health import get_sse_health, health_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    app.config["TESTING"] = True
    app.config["APP_VERSION"] = "1.0.0"
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestGetSSEHealth:
    """Tests for the get_sse_health function."""

    def test_broadcaster_not_initialized(self):
        """Test when broadcaster is not initialized."""
        with patch(
            "src.claude_headspace.services.broadcaster.get_broadcaster",
            side_effect=RuntimeError("not initialized"),
        ):
            result = get_sse_health()

            assert result["status"] == "not_initialized"
            assert result["active_connections"] == 0
            assert result["running"] is False

    def test_broadcaster_healthy(self):
        """Test when broadcaster is healthy."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.get_health_status.return_value = {
            "status": "healthy",
            "active_connections": 5,
            "max_connections": 100,
            "running": True,
        }

        with patch(
            "src.claude_headspace.services.broadcaster.get_broadcaster",
            return_value=mock_broadcaster,
        ):
            result = get_sse_health()

            assert result["status"] == "healthy"
            assert result["active_connections"] == 5
            assert result["max_connections"] == 100

    def test_broadcaster_error(self):
        """Test when broadcaster raises unexpected error."""
        with patch(
            "src.claude_headspace.services.broadcaster.get_broadcaster",
            side_effect=Exception("unexpected error"),
        ):
            result = get_sse_health()

            assert result["status"] == "error"
            assert "unexpected error" in result["error"]


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_healthy_with_db_and_sse(self, client):
        """Test healthy status with database and SSE."""
        mock_sse_health = {
            "status": "healthy",
            "active_connections": 5,
            "max_connections": 100,
            "running": True,
        }

        with patch(
            "src.claude_headspace.routes.health.check_database_health",
            return_value=(True, None),
        ):
            with patch(
                "src.claude_headspace.routes.health.get_sse_health",
                return_value=mock_sse_health,
            ):
                response = client.get("/health")

                assert response.status_code == 200
                data = response.get_json()

                assert data["status"] == "healthy"
                assert data["version"] == "1.0.0"
                assert data["database"] == "connected"
                assert data["sse"]["status"] == "healthy"
                assert data["sse"]["active_connections"] == 5

    def test_healthy_with_sse_not_initialized(self, client):
        """Test healthy status when SSE is not initialized."""
        mock_sse_health = {
            "status": "not_initialized",
            "active_connections": 0,
            "max_connections": 0,
            "running": False,
        }

        with patch(
            "src.claude_headspace.routes.health.check_database_health",
            return_value=(True, None),
        ):
            with patch(
                "src.claude_headspace.routes.health.get_sse_health",
                return_value=mock_sse_health,
            ):
                response = client.get("/health")

                data = response.get_json()

                # Should still be healthy if SSE is not initialized yet
                assert data["status"] == "healthy"
                assert data["sse"]["status"] == "not_initialized"

    def test_degraded_with_db_error(self, client):
        """Test degraded status when database is disconnected."""
        mock_sse_health = {
            "status": "healthy",
            "active_connections": 0,
            "max_connections": 100,
            "running": True,
        }

        with patch(
            "src.claude_headspace.routes.health.check_database_health",
            return_value=(False, "Connection refused"),
        ):
            with patch(
                "src.claude_headspace.routes.health.get_sse_health",
                return_value=mock_sse_health,
            ):
                response = client.get("/health")

                data = response.get_json()

                assert data["status"] == "degraded"
                assert data["database"] == "disconnected"
                assert data["database_error"] == "Connection refused"

    def test_degraded_with_sse_error(self, client):
        """Test degraded status when SSE has error."""
        mock_sse_health = {
            "status": "error",
            "error": "Thread died",
        }

        with patch(
            "src.claude_headspace.routes.health.check_database_health",
            return_value=(True, None),
        ):
            with patch(
                "src.claude_headspace.routes.health.get_sse_health",
                return_value=mock_sse_health,
            ):
                response = client.get("/health")

                data = response.get_json()

                assert data["status"] == "degraded"
                assert data["sse"]["status"] == "error"
