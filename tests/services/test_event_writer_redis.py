"""Tests for Redis-backed EventWriter metrics."""

import fakeredis
import pytest

from claude_headspace.services.event_writer import EventWriterMetrics


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

    def hincrby(self, key, field, amount=1):
        return self._client.hincrby(key, field, amount)

    def hset(self, key, field, value):
        self._client.hset(key, field, value)
        return True

    def hgetall(self, key):
        return self._client.hgetall(key) or {}


@pytest.fixture
def redis_mgr():
    return FakeRedisManager()


@pytest.fixture
def metrics_with_redis(redis_mgr):
    return EventWriterMetrics(_redis=redis_mgr)


@pytest.fixture
def metrics_no_redis():
    return EventWriterMetrics()


class TestRedisBackedMetrics:
    def test_record_success_increments_redis(self, metrics_with_redis, redis_mgr):
        metrics_with_redis.record_success()
        data = redis_mgr.hgetall(redis_mgr.key("event_writer", "metrics"))
        assert int(data["total_writes"]) == 1
        assert int(data["successful_writes"]) == 1

    def test_record_failure_increments_redis(self, metrics_with_redis, redis_mgr):
        metrics_with_redis.record_failure("test error")
        data = redis_mgr.hgetall(redis_mgr.key("event_writer", "metrics"))
        assert int(data["total_writes"]) == 1
        assert int(data["failed_writes"]) == 1
        assert data["last_error"] == "test error"

    def test_get_stats_from_redis(self, metrics_with_redis):
        metrics_with_redis.record_success()
        metrics_with_redis.record_success()
        metrics_with_redis.record_failure("err")
        stats = metrics_with_redis.get_stats()
        assert stats["total_writes"] == 3
        assert stats["successful_writes"] == 2
        assert stats["failed_writes"] == 1
        assert stats["redis_backed"] is True

    def test_stats_survive_new_instance(self, redis_mgr):
        m1 = EventWriterMetrics(_redis=redis_mgr)
        m1.record_success()
        m1.record_success()
        # New instance reads from same Redis
        m2 = EventWriterMetrics(_redis=redis_mgr)
        stats = m2.get_stats()
        assert stats["total_writes"] == 2
        assert stats["redis_backed"] is True


class TestFallbackMetrics:
    def test_record_success_in_memory(self, metrics_no_redis):
        metrics_no_redis.record_success()
        stats = metrics_no_redis.get_stats()
        assert stats["total_writes"] == 1
        assert stats["redis_backed"] is False

    def test_fallback_on_redis_failure(self, metrics_with_redis, redis_mgr):
        metrics_with_redis.record_success()
        redis_mgr._is_available = False
        metrics_with_redis.record_success()
        # In-memory should still track
        stats = metrics_with_redis.get_stats()
        assert stats["total_writes"] == 2
        assert stats["redis_backed"] is False
