"""Unit tests for OpenRouter API client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.claude_headspace.services.openrouter_client import (
    InferenceResult,
    OpenRouterClient,
    OpenRouterClientError,
)


@pytest.fixture
def config():
    return {
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "timeout": 10,
            "retry": {
                "max_attempts": 2,
                "base_delay_seconds": 0.01,
                "max_delay_seconds": 0.05,
            },
        },
    }


@pytest.fixture
def client_with_key(config):
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-123"}):
        return OpenRouterClient(config)


@pytest.fixture
def client_no_key(config):
    with patch.dict("os.environ", {}, clear=True):
        # Ensure no env var and no config key
        config["openrouter"].pop("api_key", None)
        return OpenRouterClient(config)


class TestOpenRouterClientInit:

    def test_is_configured_with_env_key(self, client_with_key):
        assert client_with_key.is_configured is True

    def test_is_not_configured_without_key(self):
        config = {"openrouter": {}}
        with patch.dict("os.environ", {}, clear=True):
            # Remove OPENROUTER_API_KEY if present
            import os
            os.environ.pop("OPENROUTER_API_KEY", None)
            client = OpenRouterClient(config)
            assert client.is_configured is False

    def test_env_key_takes_precedence(self):
        config = {"openrouter": {"api_key": "config-key"}}
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            client = OpenRouterClient(config)
            assert client.api_key == "env-key"

    def test_falls_back_to_config_key(self):
        config = {"openrouter": {"api_key": "config-key"}}
        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("OPENROUTER_API_KEY", None)
            client = OpenRouterClient(config)
            assert client.api_key == "config-key"


class TestChatCompletion:

    def test_successful_call(self, client_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "anthropic/claude-3-5-haiku-20241022",
        }

        with patch("requests.post", return_value=mock_response):
            result = client_with_key.chat_completion(
                model="anthropic/claude-3-5-haiku-20241022",
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert isinstance(result, InferenceResult)
        assert result.text == "Hello world"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.latency_ms >= 0

    def test_no_api_key_raises(self, client_no_key):
        with pytest.raises(OpenRouterClientError, match="not configured"):
            client_no_key.chat_completion(
                model="test-model",
                messages=[{"role": "user", "content": "Hi"}],
            )

    def test_non_retryable_error_raises_immediately(self, client_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(OpenRouterClientError) as exc_info:
                client_with_key.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )
            assert exc_info.value.retryable is False
            assert exc_info.value.status_code == 401

    def test_400_error_not_retried(self, client_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with patch("requests.post", return_value=mock_response) as mock_post:
            with pytest.raises(OpenRouterClientError) as exc_info:
                client_with_key.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )
            assert exc_info.value.retryable is False
            # Should only be called once (no retries)
            assert mock_post.call_count == 1

    def test_retryable_error_retries(self, client_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch("requests.post", return_value=mock_response) as mock_post:
            with pytest.raises(OpenRouterClientError) as exc_info:
                client_with_key.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )
            assert exc_info.value.retryable is True
            assert mock_post.call_count == 2  # max_attempts=2

    def test_429_is_retryable(self, client_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"

        with patch("requests.post", return_value=mock_response) as mock_post:
            with pytest.raises(OpenRouterClientError) as exc_info:
                client_with_key.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )
            assert exc_info.value.retryable is True
            assert mock_post.call_count == 2

    def test_timeout_is_retryable(self, client_with_key):
        with patch("requests.post", side_effect=requests.exceptions.Timeout) as mock_post:
            with pytest.raises(OpenRouterClientError) as exc_info:
                client_with_key.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )
            assert exc_info.value.retryable is True
            assert mock_post.call_count == 2

    def test_connection_error_is_retryable(self, client_with_key):
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError) as mock_post:
            with pytest.raises(OpenRouterClientError) as exc_info:
                client_with_key.chat_completion(
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )
            assert exc_info.value.retryable is True
            assert mock_post.call_count == 2

    def test_retry_then_success(self, client_with_key):
        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "Server error"

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "Success"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        }

        with patch("requests.post", side_effect=[fail_response, success_response]):
            result = client_with_key.chat_completion(
                model="test-model",
                messages=[{"role": "user", "content": "Hi"}],
            )
            assert result.text == "Success"

    def test_headers_include_auth(self, client_with_key):
        headers = client_with_key._get_headers()
        assert headers["Authorization"] == "Bearer test-key-123"
        assert headers["Content-Type"] == "application/json"


class TestConnectivity:

    def test_check_connectivity_success(self, client_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("requests.get", return_value=mock_response):
            assert client_with_key.check_connectivity() is True

    def test_check_connectivity_failure(self, client_with_key):
        with patch("requests.get", side_effect=Exception("Connection failed")):
            assert client_with_key.check_connectivity() is False

    def test_check_connectivity_no_key(self, client_no_key):
        assert client_no_key.check_connectivity() is False


class TestInputHash:

    def test_compute_input_hash(self):
        hash1 = OpenRouterClient.compute_input_hash("Hello world")
        hash2 = OpenRouterClient.compute_input_hash("Hello world")
        hash3 = OpenRouterClient.compute_input_hash("Different text")

        assert hash1 == hash2  # Deterministic
        assert hash1 != hash3  # Different input
        assert len(hash1) == 64  # SHA-256 hex digest
