"""Tests for the voice_auth service (tasks 3.2, 3.8)."""

import time
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.services.voice_auth import VoiceAuth


@pytest.fixture
def config():
    """Config with voice bridge auth enabled."""
    return {
        "voice_bridge": {
            "enabled": True,
            "auth": {
                "token": "test-secret-token",
                "localhost_bypass": True,
            },
            "rate_limit": {
                "requests_per_minute": 5,
            },
            "default_verbosity": "concise",
        },
    }


@pytest.fixture
def config_no_token():
    """Config with no auth token configured."""
    return {
        "voice_bridge": {
            "enabled": True,
            "auth": {
                "token": "",
                "localhost_bypass": False,
            },
            "rate_limit": {
                "requests_per_minute": 60,
            },
        },
    }


@pytest.fixture
def config_no_bypass():
    """Config with localhost bypass disabled."""
    return {
        "voice_bridge": {
            "enabled": True,
            "auth": {
                "token": "test-secret-token",
                "localhost_bypass": False,
            },
            "rate_limit": {
                "requests_per_minute": 60,
            },
        },
    }


@pytest.fixture
def app():
    """Minimal Flask app for request context."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestVoiceAuthInit:
    """Test VoiceAuth initialization."""

    def test_init_with_config(self, config):
        auth = VoiceAuth(config=config)
        assert auth.token == "test-secret-token"
        assert auth.localhost_bypass is True
        assert auth.requests_per_minute == 5

    def test_init_defaults(self):
        auth = VoiceAuth(config={})
        assert auth.token == ""
        assert auth.localhost_bypass is True
        assert auth.requests_per_minute == 60

    def test_reload_config(self, config):
        auth = VoiceAuth(config={})
        assert auth.token == ""
        auth.reload_config(config)
        assert auth.token == "test-secret-token"
        assert auth.localhost_bypass is True
        assert auth.requests_per_minute == 5


class TestTokenValidation:
    """Test token validation (task 3.2, 3.8)."""

    def test_valid_token(self, app, config):
        auth = VoiceAuth(config=config)
        with app.test_request_context(
            "/api/voice/sessions",
            headers={"Authorization": "Bearer test-secret-token"},
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            result = auth.authenticate()
            assert result is None  # None means allow

    def test_missing_authorization_header(self, app, config_no_bypass):
        auth = VoiceAuth(config=config_no_bypass)
        with app.test_request_context(
            "/api/voice/sessions",
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            result = auth.authenticate()
            assert result is not None
            response, status_code = result
            assert status_code == 401
            data = response.get_json()
            assert data["error"] == "missing_token"
            assert "voice" in data

    def test_invalid_token(self, app, config_no_bypass):
        auth = VoiceAuth(config=config_no_bypass)
        with app.test_request_context(
            "/api/voice/sessions",
            headers={"Authorization": "Bearer wrong-token"},
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            result = auth.authenticate()
            assert result is not None
            response, status_code = result
            assert status_code == 401
            data = response.get_json()
            assert data["error"] == "invalid_token"

    def test_non_bearer_auth(self, app, config_no_bypass):
        auth = VoiceAuth(config=config_no_bypass)
        with app.test_request_context(
            "/api/voice/sessions",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            result = auth.authenticate()
            assert result is not None
            _, status_code = result
            assert status_code == 401


class TestLocalhostBypass:
    """Test localhost bypass (task 3.2)."""

    def test_localhost_127_bypass(self, app, config):
        auth = VoiceAuth(config=config)
        with app.test_request_context(
            "/api/voice/sessions",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        ):
            result = auth.authenticate()
            assert result is None

    def test_localhost_ipv6_bypass(self, app, config):
        auth = VoiceAuth(config=config)
        with app.test_request_context(
            "/api/voice/sessions",
            environ_base={"REMOTE_ADDR": "::1"},
        ):
            result = auth.authenticate()
            assert result is None

    def test_localhost_bypass_disabled(self, app, config_no_bypass):
        auth = VoiceAuth(config=config_no_bypass)
        with app.test_request_context(
            "/api/voice/sessions",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        ):
            result = auth.authenticate()
            assert result is not None
            _, status_code = result
            assert status_code == 401

    def test_no_token_configured_allows_all(self, app, config_no_token):
        """When no token is configured, all requests are allowed."""
        auth = VoiceAuth(config=config_no_token)
        with app.test_request_context(
            "/api/voice/sessions",
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            result = auth.authenticate()
            assert result is None


class TestRateLimiting:
    """Test rate limiting (task 3.2)."""

    def test_rate_limit_allows_within_limit(self, app, config):
        auth = VoiceAuth(config=config)
        # Config allows 5 requests per minute
        with app.test_request_context(
            "/api/voice/sessions",
            headers={"Authorization": "Bearer test-secret-token"},
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            for _ in range(5):
                result = auth.authenticate()
                assert result is None

    def test_rate_limit_blocks_over_limit(self, app, config):
        auth = VoiceAuth(config=config)
        # Config allows 5 requests per minute
        with app.test_request_context(
            "/api/voice/sessions",
            headers={"Authorization": "Bearer test-secret-token"},
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            # Use up the limit
            for _ in range(5):
                auth.authenticate()

            # 6th request should be rate limited
            result = auth.authenticate()
            assert result is not None
            response, status_code = result
            assert status_code == 429
            data = response.get_json()
            assert data["error"] == "rate_limited"

    def test_rate_limit_window_expires(self, app, config):
        auth = VoiceAuth(config=config)
        with app.test_request_context(
            "/api/voice/sessions",
            headers={"Authorization": "Bearer test-secret-token"},
            environ_base={"REMOTE_ADDR": "192.168.1.1"},
        ):
            # Fill up the rate limit with old timestamps
            token = "test-secret-token"
            old_time = time.time() - 61  # 61 seconds ago
            auth._request_times[token] = [old_time] * 5

            # Should pass because old entries are cleaned
            result = auth.authenticate()
            assert result is None
