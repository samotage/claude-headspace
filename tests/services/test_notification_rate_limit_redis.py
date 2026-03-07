"""Tests for Redis-backed notification rate limits."""

import fakeredis
import pytest

from claude_headspace.services.notification_service import (
    NotificationPreferences,
    NotificationService,
)


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


@pytest.fixture
def redis_mgr():
    return FakeRedisManager()


@pytest.fixture
def service_with_redis(redis_mgr):
    prefs = NotificationPreferences(rate_limit_seconds=5)
    return NotificationService(preferences=prefs, redis_manager=redis_mgr)


@pytest.fixture
def service_no_redis():
    prefs = NotificationPreferences(rate_limit_seconds=5)
    return NotificationService(preferences=prefs)


class TestAgentRateLimitRedis:
    """Test agent rate limiting with Redis backing."""

    def test_not_rate_limited_initially(self, service_with_redis):
        assert service_with_redis._is_rate_limited("agent-1") is False

    def test_rate_limited_after_update(self, service_with_redis, redis_mgr):
        service_with_redis._update_rate_limit("agent-1")
        assert service_with_redis._is_rate_limited("agent-1") is True

    def test_rate_limit_stored_in_redis(self, service_with_redis, redis_mgr):
        service_with_redis._update_rate_limit("agent-1")
        key = redis_mgr.key("ratelimit", "agent", "agent-1")
        assert redis_mgr.exists(key) is True

    def test_different_agents_independent(self, service_with_redis):
        service_with_redis._update_rate_limit("agent-1")
        assert service_with_redis._is_rate_limited("agent-1") is True
        assert service_with_redis._is_rate_limited("agent-2") is False


class TestChannelRateLimitRedis:
    """Test channel rate limiting with Redis backing."""

    def test_not_rate_limited_initially(self, service_with_redis):
        assert service_with_redis._is_channel_rate_limited("general") is False

    def test_rate_limited_after_update(self, service_with_redis):
        service_with_redis._update_channel_rate_limit("general")
        assert service_with_redis._is_channel_rate_limited("general") is True

    def test_channel_rate_limit_stored_in_redis(self, service_with_redis, redis_mgr):
        service_with_redis._update_channel_rate_limit("general")
        key = redis_mgr.key("ratelimit", "channel", "general")
        assert redis_mgr.exists(key) is True


class TestFallbackBehavior:
    """Test rate limit fallback when Redis is unavailable."""

    def test_agent_rate_limit_without_redis(self, service_no_redis):
        assert service_no_redis._is_rate_limited("agent-1") is False
        service_no_redis._update_rate_limit("agent-1")
        assert service_no_redis._is_rate_limited("agent-1") is True

    def test_agent_rate_limit_redis_failure(self, service_with_redis, redis_mgr):
        service_with_redis._update_rate_limit("agent-1")
        # Simulate Redis going down
        redis_mgr._is_available = False
        # In-memory fallback should still show rate limited
        assert service_with_redis._is_rate_limited("agent-1") is True

    def test_channel_rate_limit_redis_failure(self, service_with_redis, redis_mgr):
        service_with_redis._update_channel_rate_limit("general")
        redis_mgr._is_available = False
        assert service_with_redis._is_channel_rate_limited("general") is True
