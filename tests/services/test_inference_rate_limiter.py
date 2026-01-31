"""Unit tests for inference rate limiter."""

import threading

import pytest

from src.claude_headspace.services.inference_rate_limiter import (
    InferenceRateLimiter,
    RateLimitResult,
)


@pytest.fixture
def limiter():
    return InferenceRateLimiter({
        "openrouter": {
            "rate_limits": {
                "calls_per_minute": 5,
                "tokens_per_minute": 1000,
            },
        },
    })


class TestRateLimitCheck:

    def test_first_request_allowed(self, limiter):
        result = limiter.check()
        assert result.allowed is True

    def test_within_limit_allowed(self, limiter):
        for _ in range(4):
            limiter.record(100)
        result = limiter.check()
        assert result.allowed is True

    def test_calls_per_minute_exceeded(self, limiter):
        for _ in range(5):
            limiter.record(10)
        result = limiter.check()
        assert result.allowed is False
        assert "Calls per minute" in result.reason
        assert result.retry_after_seconds > 0

    def test_tokens_per_minute_exceeded(self, limiter):
        limiter.record(900)
        result = limiter.check(estimated_tokens=200)
        assert result.allowed is False
        assert "Tokens per minute" in result.reason

    def test_tokens_check_includes_estimate(self, limiter):
        limiter.record(500)
        # 500 existing + 600 estimated = 1100 > 1000 limit
        result = limiter.check(estimated_tokens=600)
        assert result.allowed is False

    def test_tokens_check_passes_within_limit(self, limiter):
        limiter.record(500)
        # 500 existing + 400 estimated = 900 <= 1000 limit
        result = limiter.check(estimated_tokens=400)
        assert result.allowed is True


class TestRateLimitRecord:

    def test_record_increments_call_count(self, limiter):
        limiter.record(100)
        usage = limiter.current_usage
        assert usage["calls_per_minute"]["current"] == 1

    def test_record_increments_token_count(self, limiter):
        limiter.record(250)
        usage = limiter.current_usage
        assert usage["tokens_per_minute"]["current"] == 250


class TestCurrentUsage:

    def test_initial_usage(self, limiter):
        usage = limiter.current_usage
        assert usage["calls_per_minute"]["current"] == 0
        assert usage["calls_per_minute"]["limit"] == 5
        assert usage["tokens_per_minute"]["current"] == 0
        assert usage["tokens_per_minute"]["limit"] == 1000

    def test_usage_after_records(self, limiter):
        limiter.record(100)
        limiter.record(200)
        usage = limiter.current_usage
        assert usage["calls_per_minute"]["current"] == 2
        assert usage["tokens_per_minute"]["current"] == 300


class TestThreadSafety:

    def test_concurrent_records(self, limiter):
        """Test that concurrent record calls don't lose data."""
        errors = []

        def record_calls():
            try:
                for _ in range(10):
                    limiter.record(10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_calls) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        usage = limiter.current_usage
        assert usage["calls_per_minute"]["current"] == 50
        assert usage["tokens_per_minute"]["current"] == 500

    def test_concurrent_check_and_record(self, limiter):
        """Test concurrent check and record don't deadlock or error."""
        errors = []

        def check_loop():
            try:
                for _ in range(20):
                    limiter.check()
            except Exception as e:
                errors.append(e)

        def record_loop():
            try:
                for _ in range(20):
                    limiter.record(10)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=check_loop)
        t2 = threading.Thread(target=record_loop)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
