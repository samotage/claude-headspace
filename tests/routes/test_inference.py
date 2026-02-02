"""Unit tests for inference API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.inference import inference_bp


@pytest.fixture
def app():
    """Create a test Flask application with inference blueprint."""
    app = Flask(__name__)
    app.register_blueprint(inference_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.get_status.return_value = {
        "available": True,
        "openrouter_connected": True,
        "models": {
            "turn": "anthropic/claude-3-haiku",
            "project": "anthropic/claude-3.5-sonnet",
        },
        "rate_limits": {
            "calls_per_minute": {"current": 5, "limit": 30},
            "tokens_per_minute": {"current": 1000, "limit": 50000},
        },
        "cache": {
            "enabled": True,
            "ttl_seconds": 300,
            "size": 10,
            "hits": 25,
            "misses": 15,
            "hit_rate": 0.625,
        },
    }
    service.get_usage.return_value = {
        "total_calls": 100,
        "calls_by_level": {"turn": 70, "project": 30},
        "calls_by_model": {
            "anthropic/claude-3-haiku": 70,
            "anthropic/claude-3.5-sonnet": 30,
        },
        "total_input_tokens": 15000,
        "total_output_tokens": 5000,
        "total_cost": 0.095,
        "cost_by_model": {
            "anthropic/claude-3-haiku": 0.04,
            "anthropic/claude-3.5-sonnet": 0.055,
        },
    }
    return service


class TestStatusEndpoint:

    def test_status_returns_service_status(self, app, client, mock_service):
        app.extensions["inference_service"] = mock_service
        response = client.get("/api/inference/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["available"] is True
        assert data["openrouter_connected"] is True
        assert "models" in data
        assert "rate_limits" in data
        assert "cache" in data

    def test_status_no_service_returns_503(self, app, client):
        # No inference_service in extensions
        app.extensions.pop("inference_service", None)
        response = client.get("/api/inference/status")

        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data


class TestUsageEndpoint:

    def test_usage_returns_statistics(self, app, client, mock_service):
        app.extensions["inference_service"] = mock_service

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session = MagicMock()
            response = client.get("/api/inference/usage")

        assert response.status_code == 200
        data = response.get_json()
        assert data["total_calls"] == 100
        assert data["calls_by_level"]["turn"] == 70
        assert data["total_input_tokens"] == 15000
        assert data["total_cost"] == 0.095

    def test_usage_no_service_returns_503(self, app, client):
        app.extensions.pop("inference_service", None)
        response = client.get("/api/inference/usage")

        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data
