"""Tests for Redis-backed SessionTokenService."""

import json

import fakeredis
import pytest

from claude_headspace.services.session_token import SessionTokenService, TokenInfo


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

    def delete(self, *keys):
        return self._client.delete(*keys)

    def hset(self, key, field, value):
        self._client.hset(key, field, value)
        return True

    def hget(self, key, field):
        return self._client.hget(key, field)

    def hdel(self, key, *fields):
        return self._client.hdel(key, *fields)

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


@pytest.fixture
def redis_mgr():
    return FakeRedisManager()


@pytest.fixture
def service_with_redis(redis_mgr):
    return SessionTokenService(redis_manager=redis_mgr)


@pytest.fixture
def service_no_redis():
    return SessionTokenService()


class TestRedisBackedTokens:
    def test_generate_and_validate(self, service_with_redis):
        token = service_with_redis.generate(agent_id=1)
        info = service_with_redis.validate(token)
        assert info is not None
        assert info.agent_id == 1

    def test_token_stored_in_redis(self, service_with_redis, redis_mgr):
        token = service_with_redis.generate(agent_id=1)
        raw = redis_mgr.hget(redis_mgr.key("session_tokens"), token)
        assert raw is not None
        data = json.loads(raw)
        assert data["agent_id"] == 1

    def test_validate_from_redis_only(self, service_with_redis, redis_mgr):
        token = service_with_redis.generate(agent_id=1)
        # Clear in-memory
        service_with_redis._tokens.clear()
        service_with_redis._agent_tokens.clear()
        # Redis should still validate
        info = service_with_redis.validate(token)
        assert info is not None
        assert info.agent_id == 1

    def test_revoke(self, service_with_redis, redis_mgr):
        token = service_with_redis.generate(agent_id=1)
        assert service_with_redis.revoke(token) is True
        assert service_with_redis.validate(token) is None
        # Gone from Redis too
        raw = redis_mgr.hget(redis_mgr.key("session_tokens"), token)
        assert raw is None

    def test_revoke_for_agent(self, service_with_redis, redis_mgr):
        token = service_with_redis.generate(agent_id=1)
        assert service_with_redis.revoke_for_agent(1) is True
        assert service_with_redis.validate(token) is None

    def test_validate_for_agent(self, service_with_redis):
        token = service_with_redis.generate(agent_id=1)
        assert service_with_redis.validate_for_agent(token, 1) is not None
        assert service_with_redis.validate_for_agent(token, 2) is None

    def test_feature_flags(self, service_with_redis):
        token = service_with_redis.generate(
            agent_id=1, feature_flags={"file_upload": True}
        )
        flags = service_with_redis.get_feature_flags(token)
        assert flags == {"file_upload": True}

    def test_generate_replaces_old_token(self, service_with_redis):
        token1 = service_with_redis.generate(agent_id=1)
        token2 = service_with_redis.generate(agent_id=1)
        assert token1 != token2
        assert service_with_redis.validate(token1) is None
        assert service_with_redis.validate(token2) is not None


class TestFallback:
    def test_generate_and_validate_without_redis(self, service_no_redis):
        token = service_no_redis.generate(agent_id=1)
        info = service_no_redis.validate(token)
        assert info is not None
        assert info.agent_id == 1

    def test_validate_after_redis_failure(self, service_with_redis, redis_mgr):
        token = service_with_redis.generate(agent_id=1)
        redis_mgr._is_available = False
        # In-memory still works
        info = service_with_redis.validate(token)
        assert info is not None


class TestTokenInfoSerialisation:
    def test_round_trip(self):
        info = TokenInfo(agent_id=42, feature_flags={"a": True})
        data = info.to_dict()
        restored = TokenInfo.from_dict(data)
        assert restored.agent_id == info.agent_id
        assert restored.feature_flags == info.feature_flags
