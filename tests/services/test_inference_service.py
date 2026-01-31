"""Unit tests for inference service."""

from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.services.inference_service import (
    InferenceService,
    InferenceServiceError,
)
from src.claude_headspace.services.openrouter_client import (
    InferenceResult,
    OpenRouterClientError,
)


@pytest.fixture
def config():
    return {
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "timeout": 10,
            "models": {
                "turn": "anthropic/claude-3-5-haiku-20241022",
                "task": "anthropic/claude-3-5-haiku-20241022",
                "project": "anthropic/claude-3-5-sonnet-20241022",
                "objective": "anthropic/claude-3-5-sonnet-20241022",
            },
            "rate_limits": {
                "calls_per_minute": 30,
                "tokens_per_minute": 50000,
            },
            "cache": {
                "enabled": True,
                "ttl_seconds": 300,
            },
            "retry": {
                "max_attempts": 1,
                "base_delay_seconds": 0.01,
                "max_delay_seconds": 0.01,
            },
            "pricing": {
                "anthropic/claude-3-5-haiku-20241022": {
                    "input_per_million": 1.0,
                    "output_per_million": 5.0,
                },
                "anthropic/claude-3-5-sonnet-20241022": {
                    "input_per_million": 3.0,
                    "output_per_million": 15.0,
                },
            },
        },
    }


@pytest.fixture
def service(config):
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
        return InferenceService(config=config)


@pytest.fixture
def service_no_key(config):
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("OPENROUTER_API_KEY", None)
        config["openrouter"].pop("api_key", None)
        return InferenceService(config=config)


class TestModelSelection:

    def test_turn_uses_haiku(self, service):
        assert service.get_model_for_level("turn") == "anthropic/claude-3-5-haiku-20241022"

    def test_task_uses_haiku(self, service):
        assert service.get_model_for_level("task") == "anthropic/claude-3-5-haiku-20241022"

    def test_project_uses_sonnet(self, service):
        assert service.get_model_for_level("project") == "anthropic/claude-3-5-sonnet-20241022"

    def test_objective_uses_sonnet(self, service):
        assert service.get_model_for_level("objective") == "anthropic/claude-3-5-sonnet-20241022"

    def test_unknown_level_raises(self, service):
        with pytest.raises(InferenceServiceError, match="No model configured"):
            service.get_model_for_level("unknown")


class TestServiceAvailability:

    def test_available_with_key(self, service):
        assert service.is_available is True

    def test_not_available_without_key(self, service_no_key):
        assert service_no_key.is_available is False

    def test_infer_without_key_raises(self, service_no_key):
        with pytest.raises(InferenceServiceError, match="not available"):
            service_no_key.infer(level="turn", purpose="test", input_text="hello")


class TestInference:

    def test_successful_inference(self, service):
        mock_result = InferenceResult(
            text="Summary text",
            input_tokens=100,
            output_tokens=50,
            model="anthropic/claude-3-5-haiku-20241022",
            latency_ms=250,
        )

        with patch.object(service.client, "chat_completion", return_value=mock_result):
            result = service.infer(level="turn", purpose="summarise", input_text="test input")

        assert result.text == "Summary text"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cached is False

    def test_cache_hit_returns_cached(self, service):
        mock_result = InferenceResult(
            text="Fresh result",
            input_tokens=100,
            output_tokens=50,
            model="anthropic/claude-3-5-haiku-20241022",
            latency_ms=250,
        )

        with patch.object(service.client, "chat_completion", return_value=mock_result):
            # First call - populates cache
            service.infer(level="turn", purpose="summarise", input_text="same input")

        with patch.object(service.client, "chat_completion") as mock_call:
            # Second call - should hit cache
            result = service.infer(level="turn", purpose="summarise", input_text="same input")
            mock_call.assert_not_called()

        assert result.cached is True
        assert result.text == "Fresh result"
        assert result.latency_ms == 0

    def test_rate_limit_raises(self, service):
        # Exhaust rate limits
        for _ in range(30):
            service.rate_limiter.record(100)

        with pytest.raises(InferenceServiceError) as exc_info:
            service.infer(level="turn", purpose="test", input_text="blocked")
        assert exc_info.value.rate_limited is True
        assert exc_info.value.retry_after > 0

    def test_api_error_propagated(self, service):
        error = OpenRouterClientError("API failed", status_code=500, retryable=True)
        with patch.object(service.client, "chat_completion", side_effect=error):
            with pytest.raises(OpenRouterClientError, match="API failed"):
                service.infer(level="turn", purpose="test", input_text="error input")


class TestCostCalculation:

    def test_haiku_cost(self, service):
        cost = service._calculate_cost(
            "anthropic/claude-3-5-haiku-20241022",
            input_tokens=1000,
            output_tokens=500,
        )
        # input: 1000 * 1.0 / 1M = 0.001, output: 500 * 5.0 / 1M = 0.0025
        expected = 0.001 + 0.0025
        assert abs(cost - expected) < 1e-10

    def test_sonnet_cost(self, service):
        cost = service._calculate_cost(
            "anthropic/claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500,
        )
        # input: 1000 * 3.0 / 1M = 0.003, output: 500 * 15.0 / 1M = 0.0075
        expected = 0.003 + 0.0075
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_zero_cost(self, service):
        cost = service._calculate_cost("unknown-model", 1000, 500)
        assert cost == 0.0


class TestServiceStatus:

    def test_status_available(self, service):
        with patch.object(service.client, "check_connectivity", return_value=True):
            status = service.get_status()

        assert status["available"] is True
        assert status["openrouter_connected"] is True
        assert "models" in status
        assert "rate_limits" in status
        assert "cache" in status

    def test_status_disconnected(self, service):
        with patch.object(service.client, "check_connectivity", return_value=False):
            status = service.get_status()

        assert status["available"] is True
        assert status["openrouter_connected"] is False

    def test_status_unavailable(self, service_no_key):
        status = service_no_key.get_status()
        assert status["available"] is False
        assert status["openrouter_connected"] is False


class TestLogging:

    def test_log_call_with_session_factory(self, config):
        mock_session = MagicMock()
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            service = InferenceService(
                config=config,
                db_session_factory=lambda: mock_session,
            )

        mock_result = InferenceResult(
            text="result",
            input_tokens=100,
            output_tokens=50,
            model="anthropic/claude-3-5-haiku-20241022",
            latency_ms=200,
        )

        with patch.object(service.client, "chat_completion", return_value=mock_result):
            service.infer(level="turn", purpose="test", input_text="hello")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_no_session_factory_skips_logging(self, service):
        mock_result = InferenceResult(
            text="result",
            input_tokens=100,
            output_tokens=50,
            model="anthropic/claude-3-5-haiku-20241022",
            latency_ms=200,
        )

        with patch.object(service.client, "chat_completion", return_value=mock_result):
            # Should not raise even without db_session_factory
            result = service.infer(level="turn", purpose="test", input_text="hello")
            assert result.text == "result"
