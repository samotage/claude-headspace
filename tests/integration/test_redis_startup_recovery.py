"""Integration tests for Redis startup recovery flow."""

import json
from uuid import uuid4

import fakeredis
import pytest


class FakeRedisManager:
    """Shared fake Redis manager for integration tests."""

    def __init__(self):
        self.server = fakeredis.FakeServer()
        self._client = fakeredis.FakeRedis(server=self.server, decode_responses=True)
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

    def set_nx(self, key, value, ex=None):
        result = self._client.set(key, value, ex=ex, nx=True)
        return result is not None

    def delete(self, *keys):
        return self._client.delete(*keys)

    def exists(self, key):
        return bool(self._client.exists(key))

    def expire(self, key, seconds):
        return bool(self._client.expire(key, seconds))

    def incr(self, key):
        return self._client.incr(key)

    def hset(self, key, field, value):
        self._client.hset(key, field, value)
        return True

    def hget(self, key, field):
        return self._client.hget(key, field)

    def hgetall(self, key):
        return self._client.hgetall(key) or {}

    def hdel(self, key, *fields):
        return self._client.hdel(key, *fields)

    def hincrby(self, key, field, amount=1):
        return self._client.hincrby(key, field, amount)

    def lpush(self, key, *values):
        return self._client.lpush(key, *values)

    def rpop(self, key):
        return self._client.rpop(key)

    def xadd(self, key, fields, maxlen=None, approximate=True):
        kwargs = {}
        if maxlen is not None:
            kwargs["maxlen"] = maxlen
            kwargs["approximate"] = approximate
        return self._client.xadd(key, fields, **kwargs)

    def xrange(self, key, min="-", max="+", count=None):
        return self._client.xrange(key, min=min, max=max, count=count)

    def xlen(self, key):
        return self._client.xlen(key)

    def get_json(self, key):
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key, value):
        self._client.set(key, json.dumps(value, default=str))
        return True

    def sadd(self, key, *members):
        return self._client.sadd(key, *members)

    def srem(self, key, *members):
        return self._client.srem(key, *members)

    def smembers(self, key):
        return self._client.smembers(key) or set()

    def sismember(self, key, member):
        return bool(self._client.sismember(key, member))

    def ttl(self, key):
        result = self._client.ttl(key)
        return result if result >= 0 else None

    def ping(self):
        return True

    def get_health_status(self):
        return {
            "enabled": True,
            "available": True,
            "status": "connected",
            "key_count": 0,
        }

    def hset_json(self, key, field, value):
        encoded = json.dumps(value, default=str)
        return self.hset(key, field, encoded)

    def hget_json(self, key, field):
        raw = self.hget(key, field)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def flush_namespace(self):
        return 0


@pytest.fixture
def redis_mgr():
    return FakeRedisManager()


class TestSessionRegistryRecovery:
    """Test that SessionRegistry recovers state from Redis after restart."""

    def test_sessions_survive_restart(self, redis_mgr):
        from claude_headspace.services.session_registry import SessionRegistry

        uid = uuid4()
        # First instance registers a session
        r1 = SessionRegistry(redis_manager=redis_mgr)
        r1.register_session(uid, "/project/a", "/work/a")
        assert r1.get_session(uid) is not None

        # Second instance recovers from Redis
        r2 = SessionRegistry(redis_manager=redis_mgr)
        session = r2.get_session(uid)
        assert session is not None
        assert session.project_path == "/project/a"


class TestBroadcasterEventIdRecovery:
    """Test that Broadcaster recovers event ID counter from Redis."""

    def test_event_id_survives_restart(self, redis_mgr):
        from claude_headspace.services.broadcaster import Broadcaster

        b1 = Broadcaster(redis_manager=redis_mgr)
        b1.start()
        for _ in range(5):
            b1.broadcast("test", {"msg": "hello"})
        last_id = b1._event_id_counter
        b1.stop()

        b2 = Broadcaster(redis_manager=redis_mgr)
        b2.start()
        assert b2._event_id_counter == last_id
        b2.broadcast("test", {"msg": "new"})
        assert b2._event_id_counter == last_id + 1
        b2.stop()


class TestReplayBufferRecovery:
    """Test that SSE replay buffer recovers from Redis Stream."""

    def test_replay_events_survive_restart(self, redis_mgr):
        from claude_headspace.services.broadcaster import Broadcaster

        b1 = Broadcaster(redis_manager=redis_mgr)
        b1.start()
        b1.broadcast("card_refresh", {"agent_id": 1})
        b1.broadcast("state_change", {"agent_id": 2})
        b1.stop()

        b2 = Broadcaster(redis_manager=redis_mgr)
        b2.start()
        events = b2.get_replay_events(after_event_id=0)
        assert len(events) >= 2
        b2.stop()


class TestEventWriterMetricsRecovery:
    """Test that EventWriter metrics survive restart via Redis."""

    def test_metrics_survive_restart(self, redis_mgr):
        from claude_headspace.services.event_writer import EventWriterMetrics

        m1 = EventWriterMetrics(_redis=redis_mgr)
        m1.record_success()
        m1.record_success()
        m1.record_failure("test error")

        # New instance reads accumulated metrics
        m2 = EventWriterMetrics(_redis=redis_mgr)
        stats = m2.get_stats()
        assert stats["total_writes"] == 3
        assert stats["successful_writes"] == 2
        assert stats["failed_writes"] == 1


class TestNotificationRateLimitRecovery:
    """Test that notification rate limits survive restart via Redis."""

    def test_agent_rate_limit_survives_restart(self, redis_mgr):
        from claude_headspace.services.notification_service import (
            NotificationPreferences,
            NotificationService,
        )

        prefs = NotificationPreferences(rate_limit_seconds=5)
        s1 = NotificationService(preferences=prefs, redis_manager=redis_mgr)
        s1._update_rate_limit("agent-1")

        # New instance sees the rate limit
        s2 = NotificationService(preferences=prefs, redis_manager=redis_mgr)
        assert s2._is_rate_limited("agent-1") is True


class TestInferenceCacheRecovery:
    """Test that inference cache entries survive restart via Redis."""

    def test_cache_entries_survive_restart(self, redis_mgr):
        from claude_headspace.services.inference_cache import InferenceCache

        config = {"openrouter": {"cache": {"enabled": True, "ttl_seconds": 300}}}
        c1 = InferenceCache(config=config, redis_manager=redis_mgr)
        c1.put("hash1", "result text", 100, 50, "model-a")

        # New instance reads from Redis
        c2 = InferenceCache(config=config, redis_manager=redis_mgr)
        entry = c2.get("hash1")
        assert entry is not None
        assert entry.result_text == "result text"


class TestCorruptDataRecovery:
    """Test that corrupt data in Redis is handled gracefully."""

    def test_corrupt_session_skipped(self, redis_mgr):
        from claude_headspace.services.session_registry import SessionRegistry

        # Plant corrupt data
        redis_mgr.hset(redis_mgr.key("sessions"), "bad-uuid", "not json{{{")
        # Should not crash
        registry = SessionRegistry(redis_manager=redis_mgr)
        assert len(registry.get_registered_sessions()) == 0
