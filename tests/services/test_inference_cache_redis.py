"""Tests for Redis-backed InferenceCache."""

import json

import fakeredis
import pytest

from claude_headspace.services.inference_cache import CacheEntry, InferenceCache


def _make_redis_manager():
    """Create a minimal RedisManager-like object backed by fakeredis."""

    class FakeRedisManager:
        def __init__(self):
            server = fakeredis.FakeServer()
            self._client = fakeredis.FakeRedis(server=server, decode_responses=True)
            self._is_available = True
            self._namespace = "test:"

        @property
        def is_available(self):
            return self._is_available

        def key(self, *parts):
            return self._namespace + ":".join(parts)

        def get(self, key):
            return self._client.get(key)

        def set(self, key, value, ex=None):
            self._client.set(key, value, ex=ex)
            return True

        def exists(self, key):
            return bool(self._client.exists(key))

    return FakeRedisManager()


@pytest.fixture
def config():
    return {"openrouter": {"cache": {"enabled": True, "ttl_seconds": 300}}}


@pytest.fixture
def redis_mgr():
    return _make_redis_manager()


@pytest.fixture
def cache_with_redis(config, redis_mgr):
    return InferenceCache(config=config, redis_manager=redis_mgr)


@pytest.fixture
def cache_no_redis(config):
    return InferenceCache(config=config)


class TestRedisBackedCache:
    """Test InferenceCache with Redis backing."""

    def test_put_stores_in_redis(self, cache_with_redis, redis_mgr):
        cache_with_redis.put("hash1", "result text", 100, 50, "test-model")
        # Verify it's in Redis
        raw = redis_mgr.get(redis_mgr.key("cache", "hash1"))
        assert raw is not None
        data = json.loads(raw)
        assert data["result_text"] == "result text"
        assert data["input_tokens"] == 100
        assert data["model"] == "test-model"

    def test_get_reads_from_redis(self, cache_with_redis, redis_mgr):
        cache_with_redis.put("hash1", "result", 10, 5, "model-a")
        # Clear in-memory cache to force Redis read
        cache_with_redis._cache.clear()
        entry = cache_with_redis.get("hash1")
        assert entry is not None
        assert entry.result_text == "result"
        assert entry.model == "model-a"

    def test_get_returns_none_for_missing(self, cache_with_redis):
        assert cache_with_redis.get("nonexistent") is None

    def test_using_redis_property(self, cache_with_redis, cache_no_redis):
        assert cache_with_redis.using_redis is True
        assert cache_no_redis.using_redis is False

    def test_stats_includes_redis_backed(self, cache_with_redis, cache_no_redis):
        assert cache_with_redis.stats["redis_backed"] is True
        assert cache_no_redis.stats["redis_backed"] is False


class TestFallbackBehavior:
    """Test that cache falls back to in-memory when Redis is unavailable."""

    def test_put_and_get_without_redis(self, cache_no_redis):
        cache_no_redis.put("hash1", "result", 10, 5, "model-a")
        entry = cache_no_redis.get("hash1")
        assert entry is not None
        assert entry.result_text == "result"

    def test_fallback_on_redis_failure(self, cache_with_redis, redis_mgr):
        cache_with_redis.put("hash1", "result", 10, 5, "model-a")
        # Simulate Redis going down
        redis_mgr._is_available = False
        # In-memory cache still works
        entry = cache_with_redis.get("hash1")
        assert entry is not None
        assert entry.result_text == "result"

    def test_put_still_works_with_redis_down(self, cache_with_redis, redis_mgr):
        redis_mgr._is_available = False
        cache_with_redis.put("hash2", "fallback", 10, 5, "model-b")
        entry = cache_with_redis.get("hash2")
        assert entry is not None
        assert entry.result_text == "fallback"


class TestCacheEntrySerialisation:
    """Test CacheEntry to_dict/from_dict round-trip."""

    def test_round_trip(self):
        entry = CacheEntry(
            result_text="hello",
            input_tokens=100,
            output_tokens=50,
            model="test",
            cached_at=12345.67,
            ttl_seconds=300,
        )
        data = entry.to_dict()
        restored = CacheEntry.from_dict(data)
        assert restored.result_text == entry.result_text
        assert restored.input_tokens == entry.input_tokens
        assert restored.output_tokens == entry.output_tokens
        assert restored.model == entry.model
        assert restored.cached_at == entry.cached_at
        assert restored.ttl_seconds == entry.ttl_seconds
