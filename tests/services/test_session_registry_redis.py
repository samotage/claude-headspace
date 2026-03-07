"""Tests for Redis-backed SessionRegistry."""

import json
from uuid import uuid4

import fakeredis
import pytest

from claude_headspace.services.session_registry import (
    RegisteredSession,
    SessionRegistry,
)


class FakeRedisManager:
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

    def delete(self, *keys):
        return self._client.delete(*keys)

    def hset(self, key, field, value):
        self._client.hset(key, field, value)
        return True

    def hget(self, key, field):
        return self._client.hget(key, field)

    def hgetall(self, key):
        return self._client.hgetall(key) or {}

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
def registry_with_redis(redis_mgr):
    return SessionRegistry(redis_manager=redis_mgr)


@pytest.fixture
def registry_no_redis():
    return SessionRegistry()


class TestRegistration:
    def test_register_and_get(self, registry_with_redis):
        uid = uuid4()
        session = registry_with_redis.register_session(uid, "/project", "/work")
        assert session.session_uuid == uid
        assert registry_with_redis.get_session(uid) is not None

    def test_register_stores_in_redis(self, registry_with_redis, redis_mgr):
        uid = uuid4()
        registry_with_redis.register_session(uid, "/project", "/work")
        raw = redis_mgr.hget(redis_mgr.key("sessions"), str(uid))
        assert raw is not None
        data = json.loads(raw)
        assert data["project_path"] == "/project"

    def test_unregister(self, registry_with_redis, redis_mgr):
        uid = uuid4()
        registry_with_redis.register_session(uid, "/project", "/work")
        assert registry_with_redis.unregister_session(uid) is True
        assert registry_with_redis.get_session(uid) is None
        # Should also be gone from Redis
        raw = redis_mgr.hget(redis_mgr.key("sessions"), str(uid))
        assert raw is None


class TestRecovery:
    def test_recover_from_redis(self, redis_mgr):
        # Pre-populate Redis with a session
        uid = uuid4()
        from datetime import datetime, timezone

        session_data = {
            "session_uuid": str(uid),
            "project_path": "/recovered",
            "working_directory": "/work",
            "iterm_pane_id": None,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
            "jsonl_file_path": None,
        }
        redis_mgr.hset(redis_mgr.key("sessions"), str(uid), json.dumps(session_data))

        # Create new registry — should recover the session
        registry = SessionRegistry(redis_manager=redis_mgr)
        session = registry.get_session(uid)
        assert session is not None
        assert session.project_path == "/recovered"


class TestActivity:
    def test_update_last_activity(self, registry_with_redis):
        uid = uuid4()
        registry_with_redis.register_session(uid, "/project", "/work")
        initial = registry_with_redis.get_session(uid).last_activity_at
        import time

        time.sleep(0.01)
        registry_with_redis.update_last_activity(uid)
        updated = registry_with_redis.get_session(uid).last_activity_at
        assert updated > initial

    def test_update_jsonl_path(self, registry_with_redis):
        uid = uuid4()
        registry_with_redis.register_session(uid, "/project", "/work")
        registry_with_redis.update_jsonl_path(uid, "/path/to/file.jsonl")
        session = registry_with_redis.get_session(uid)
        assert session.jsonl_file_path == "/path/to/file.jsonl"


class TestFallback:
    def test_register_without_redis(self, registry_no_redis):
        uid = uuid4()
        session = registry_no_redis.register_session(uid, "/project", "/work")
        assert session is not None
        assert registry_no_redis.get_session(uid) is not None

    def test_operations_after_redis_failure(self, registry_with_redis, redis_mgr):
        uid = uuid4()
        registry_with_redis.register_session(uid, "/project", "/work")
        redis_mgr._is_available = False
        # In-memory still works
        assert registry_with_redis.get_session(uid) is not None
        assert registry_with_redis.is_session_registered(uid) is True


class TestSerialisation:
    def test_registered_session_round_trip(self):
        uid = uuid4()

        session = RegisteredSession(
            session_uuid=uid,
            project_path="/test",
            working_directory="/work",
            iterm_pane_id="pane-1",
            jsonl_file_path="/path/to/log.jsonl",
        )
        data = session.to_dict()
        restored = RegisteredSession.from_dict(data)
        assert restored.session_uuid == session.session_uuid
        assert restored.project_path == session.project_path
        assert restored.iterm_pane_id == session.iterm_pane_id
        assert restored.jsonl_file_path == session.jsonl_file_path
