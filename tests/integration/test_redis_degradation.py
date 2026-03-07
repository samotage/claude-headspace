"""Integration tests for Redis graceful degradation.

Tests that all services continue operating when Redis becomes unavailable
mid-operation, using in-memory fallback.
"""

import json
from uuid import uuid4

import fakeredis
import pytest


class FakeRedisManager:
    """Redis manager that can be toggled on/off to test degradation."""

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


@pytest.fixture
def redis_mgr():
    return FakeRedisManager()


class TestBroadcasterDegradation:
    """Test Broadcaster continues working after Redis fails."""

    def test_broadcasts_continue(self, redis_mgr):
        from claude_headspace.services.broadcaster import Broadcaster

        b = Broadcaster(redis_manager=redis_mgr)
        b.start()
        # Works with Redis
        b.broadcast("test", {"msg": "with_redis"})
        assert b._event_id_counter >= 1

        # Redis goes down
        redis_mgr._is_available = False
        # Still works
        b.broadcast("test", {"msg": "no_redis"})
        assert b._event_id_counter >= 2
        b.stop()


class TestInferenceCacheDegradation:
    """Test InferenceCache continues working after Redis fails."""

    def test_cache_continues(self, redis_mgr):
        from claude_headspace.services.inference_cache import InferenceCache

        config = {"openrouter": {"cache": {"enabled": True, "ttl_seconds": 300}}}
        cache = InferenceCache(config=config, redis_manager=redis_mgr)

        # Works with Redis
        cache.put("h1", "result1", 10, 5, "model")
        assert cache.get("h1") is not None

        # Redis goes down
        redis_mgr._is_available = False
        # Put and get still work via in-memory
        cache.put("h2", "result2", 10, 5, "model")
        assert cache.get("h2") is not None
        # Previously cached entry still available in memory
        assert cache.get("h1") is not None


class TestNotificationDegradation:
    """Test NotificationService rate limits continue after Redis fails."""

    def test_rate_limits_continue(self, redis_mgr):
        from claude_headspace.services.notification_service import (
            NotificationPreferences,
            NotificationService,
        )

        prefs = NotificationPreferences(rate_limit_seconds=5)
        svc = NotificationService(preferences=prefs, redis_manager=redis_mgr)

        # Works with Redis
        svc._update_rate_limit("agent-1")
        assert svc._is_rate_limited("agent-1") is True

        # Redis goes down
        redis_mgr._is_available = False
        # In-memory still has the rate limit
        assert svc._is_rate_limited("agent-1") is True
        # Can still update
        svc._update_rate_limit("agent-2")
        assert svc._is_rate_limited("agent-2") is True


class TestSessionRegistryDegradation:
    """Test SessionRegistry continues after Redis fails."""

    def test_registry_continues(self, redis_mgr):
        from claude_headspace.services.session_registry import SessionRegistry

        reg = SessionRegistry(redis_manager=redis_mgr)
        uid1 = uuid4()
        reg.register_session(uid1, "/project/a", "/work/a")

        # Redis goes down
        redis_mgr._is_available = False
        # In-memory still works
        assert reg.get_session(uid1) is not None
        uid2 = uuid4()
        reg.register_session(uid2, "/project/b", "/work/b")
        assert reg.get_session(uid2) is not None


class TestAgentHookStateDegradation:
    """Test AgentHookState continues after Redis fails."""

    def test_hook_state_continues(self, redis_mgr):
        from claude_headspace.services.hook_agent_state import AgentHookState

        state = AgentHookState(redis_manager=redis_mgr)
        state.set_awaiting_tool(1, "Write")
        assert state.get_awaiting_tool(1) == "Write"

        # Redis goes down
        redis_mgr._is_available = False
        # In-memory still works
        assert state.get_awaiting_tool(1) == "Write"
        state.set_awaiting_tool(2, "Read")
        assert state.get_awaiting_tool(2) == "Read"


class TestSessionTokenDegradation:
    """Test SessionTokenService continues after Redis fails."""

    def test_tokens_continue(self, redis_mgr):
        from claude_headspace.services.session_token import SessionTokenService

        svc = SessionTokenService(redis_manager=redis_mgr)
        token = svc.generate(agent_id=1)
        assert svc.validate(token) is not None

        # Redis goes down
        redis_mgr._is_available = False
        # In-memory still validates
        assert svc.validate(token) is not None
        # Can still generate new tokens
        token2 = svc.generate(agent_id=2)
        assert svc.validate(token2) is not None


class TestEventWriterMetricsDegradation:
    """Test EventWriter metrics continue after Redis fails."""

    def test_metrics_continue(self, redis_mgr):
        from claude_headspace.services.event_writer import EventWriterMetrics

        m = EventWriterMetrics(_redis=redis_mgr)
        m.record_success()
        stats = m.get_stats()
        assert stats["total_writes"] == 1
        assert stats["redis_backed"] is True

        # Redis goes down
        redis_mgr._is_available = False
        m.record_success()
        stats = m.get_stats()
        assert stats["total_writes"] == 2
        assert stats["redis_backed"] is False
