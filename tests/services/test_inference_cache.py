"""Unit tests for inference cache service."""

import time

import pytest

from src.claude_headspace.services.inference_cache import InferenceCache


@pytest.fixture
def cache_config():
    return {
        "openrouter": {
            "cache": {
                "enabled": True,
                "ttl_seconds": 1,  # Short TTL for testing
            },
        },
    }


@pytest.fixture
def cache(cache_config):
    return InferenceCache(cache_config)


@pytest.fixture
def disabled_cache():
    return InferenceCache({
        "openrouter": {
            "cache": {
                "enabled": False,
                "ttl_seconds": 300,
            },
        },
    })


class TestCacheHitMiss:

    def test_cache_miss_on_empty(self, cache):
        result = cache.get("nonexistent_hash")
        assert result is None

    def test_cache_hit_after_put(self, cache):
        cache.put("hash1", "result text", 100, 50, "model-a")
        entry = cache.get("hash1")
        assert entry is not None
        assert entry.result_text == "result text"
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.model == "model-a"

    def test_cache_miss_different_hash(self, cache):
        cache.put("hash1", "result", 100, 50, "model-a")
        result = cache.get("hash2")
        assert result is None

    def test_cache_overwrite(self, cache):
        cache.put("hash1", "first", 10, 5, "model-a")
        cache.put("hash1", "second", 20, 10, "model-b")
        entry = cache.get("hash1")
        assert entry.result_text == "second"
        assert entry.model == "model-b"


class TestCacheExpiry:

    def test_expired_entry_returns_none(self, cache):
        cache.put("hash1", "result", 100, 50, "model-a")
        time.sleep(1.1)  # TTL is 1 second
        result = cache.get("hash1")
        assert result is None

    def test_non_expired_entry_returns(self, cache):
        cache.put("hash1", "result", 100, 50, "model-a")
        # Immediately check - should not be expired
        result = cache.get("hash1")
        assert result is not None

    def test_evict_expired(self, cache):
        cache.put("hash1", "result1", 100, 50, "model-a")
        cache.put("hash2", "result2", 100, 50, "model-a")
        time.sleep(1.1)
        evicted = cache.evict_expired()
        assert evicted == 2
        assert cache.stats["size"] == 0


class TestCacheDisabled:

    def test_disabled_cache_always_misses(self, disabled_cache):
        disabled_cache.put("hash1", "result", 100, 50, "model-a")
        result = disabled_cache.get("hash1")
        assert result is None

    def test_disabled_cache_stats(self, disabled_cache):
        assert disabled_cache.stats["enabled"] is False


class TestCacheStats:

    def test_initial_stats(self, cache):
        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0
        assert stats["hit_rate"] == 0

    def test_stats_after_hits_and_misses(self, cache):
        cache.put("hash1", "result", 100, 50, "model-a")
        cache.get("hash1")  # hit
        cache.get("hash2")  # miss
        cache.get("hash1")  # hit

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert abs(stats["hit_rate"] - 2 / 3) < 0.01


class TestCacheClear:

    def test_clear_removes_all(self, cache):
        cache.put("hash1", "a", 10, 5, "m")
        cache.put("hash2", "b", 10, 5, "m")
        cache.clear()
        assert cache.stats["size"] == 0
        assert cache.get("hash1") is None
