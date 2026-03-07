"""Unit tests for RedisManager service using fakeredis."""

import fakeredis
import pytest

from claude_headspace.services.redis_manager import RedisManager


@pytest.fixture
def redis_config():
    """Minimal Redis config for testing."""
    return {
        "redis": {
            "enabled": True,
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0,
            "pool_size": 5,
            "socket_timeout": 2,
            "socket_connect_timeout": 2,
            "namespace": "test:",
            "retry_interval": 1,
            "max_retry_interval": 10,
        }
    }


@pytest.fixture
def redis_manager(redis_config):
    """RedisManager backed by fakeredis."""
    manager = RedisManager.__new__(RedisManager)
    manager._enabled = True
    manager._namespace = "test:"
    manager._retry_interval = 1
    manager._max_retry_interval = 10
    manager._is_available = True
    manager._last_error = None
    manager._consecutive_failures = 0
    manager._last_reconnect_attempt = 0.0
    manager._lock = __import__("threading").Lock()

    # Use fakeredis instead of real Redis
    server = fakeredis.FakeServer()
    manager._client = fakeredis.FakeRedis(server=server, decode_responses=True)
    return manager


@pytest.fixture
def disabled_manager():
    """RedisManager with Redis disabled."""
    config = {"redis": {"enabled": False}}
    manager = RedisManager.__new__(RedisManager)
    manager._enabled = False
    manager._namespace = "test:"
    manager._retry_interval = 1
    manager._max_retry_interval = 10
    manager._is_available = False
    manager._last_error = None
    manager._consecutive_failures = 0
    manager._last_reconnect_attempt = 0.0
    manager._lock = __import__("threading").Lock()
    manager._client = None
    return manager


class TestRedisManagerBasics:
    """Test basic RedisManager properties and key namespacing."""

    def test_is_available_when_connected(self, redis_manager):
        assert redis_manager.is_available is True

    def test_is_not_available_when_disabled(self, disabled_manager):
        assert disabled_manager.is_available is False

    def test_enabled_property(self, redis_manager, disabled_manager):
        assert redis_manager.enabled is True
        assert disabled_manager.enabled is False

    def test_key_namespacing(self, redis_manager):
        assert redis_manager.key("cache", "abc123") == "test:cache:abc123"
        assert redis_manager.key("sessions") == "test:sessions"

    def test_ping_success(self, redis_manager):
        assert redis_manager.ping() is True

    def test_ping_when_disabled(self, disabled_manager):
        assert disabled_manager.ping() is False


class TestStringOperations:
    """Test basic get/set/delete operations."""

    def test_set_and_get(self, redis_manager):
        assert redis_manager.set("key1", "value1") is True
        assert redis_manager.get("key1") == "value1"

    def test_get_nonexistent(self, redis_manager):
        assert redis_manager.get("nonexistent") is None

    def test_set_with_expiry(self, redis_manager):
        assert redis_manager.set("key1", "value1", ex=60) is True
        assert redis_manager.get("key1") == "value1"

    def test_set_nx(self, redis_manager):
        assert redis_manager.set_nx("unique", "first") is True
        assert redis_manager.set_nx("unique", "second") is False
        assert redis_manager.get("unique") == "first"

    def test_delete(self, redis_manager):
        redis_manager.set("key1", "val")
        assert redis_manager.delete("key1") == 1
        assert redis_manager.get("key1") is None

    def test_exists(self, redis_manager):
        assert redis_manager.exists("key1") is False
        redis_manager.set("key1", "val")
        assert redis_manager.exists("key1") is True

    def test_incr(self, redis_manager):
        assert redis_manager.incr("counter") == 1
        assert redis_manager.incr("counter") == 2
        assert redis_manager.incr("counter") == 3

    def test_expire(self, redis_manager):
        redis_manager.set("key1", "val")
        assert redis_manager.expire("key1", 60) is True

    def test_ttl(self, redis_manager):
        redis_manager.set("key1", "val", ex=60)
        ttl = redis_manager.ttl("key1")
        assert ttl is not None
        assert ttl > 0


class TestHashOperations:
    """Test hash get/set/delete operations."""

    def test_hset_and_hget(self, redis_manager):
        assert redis_manager.hset("hash1", "field1", "value1") is True
        assert redis_manager.hget("hash1", "field1") == "value1"

    def test_hget_nonexistent(self, redis_manager):
        assert redis_manager.hget("hash1", "field1") is None

    def test_hgetall(self, redis_manager):
        redis_manager.hset("hash1", "f1", "v1")
        redis_manager.hset("hash1", "f2", "v2")
        result = redis_manager.hgetall("hash1")
        assert result == {"f1": "v1", "f2": "v2"}

    def test_hgetall_empty(self, redis_manager):
        assert redis_manager.hgetall("nonexistent") == {}

    def test_hdel(self, redis_manager):
        redis_manager.hset("hash1", "f1", "v1")
        assert redis_manager.hdel("hash1", "f1") == 1
        assert redis_manager.hget("hash1", "f1") is None

    def test_hincrby(self, redis_manager):
        assert redis_manager.hincrby("hash1", "counter", 1) == 1
        assert redis_manager.hincrby("hash1", "counter", 5) == 6


class TestSetOperations:
    """Test set operations."""

    def test_sadd_and_smembers(self, redis_manager):
        assert redis_manager.sadd("set1", "a", "b") == 2
        assert redis_manager.smembers("set1") == {"a", "b"}

    def test_srem(self, redis_manager):
        redis_manager.sadd("set1", "a", "b")
        assert redis_manager.srem("set1", "a") == 1
        assert redis_manager.smembers("set1") == {"b"}

    def test_sismember(self, redis_manager):
        redis_manager.sadd("set1", "a")
        assert redis_manager.sismember("set1", "a") is True
        assert redis_manager.sismember("set1", "b") is False


class TestListOperations:
    """Test list operations."""

    def test_lpush_and_rpop(self, redis_manager):
        redis_manager.lpush("list1", "a")
        redis_manager.lpush("list1", "b")
        assert redis_manager.rpop("list1") == "a"
        assert redis_manager.rpop("list1") == "b"

    def test_llen(self, redis_manager):
        redis_manager.lpush("list1", "a", "b", "c")
        assert redis_manager.llen("list1") == 3

    def test_rpop_empty(self, redis_manager):
        assert redis_manager.rpop("list1") is None


class TestStreamOperations:
    """Test Redis Stream operations."""

    def test_xadd_and_xrange(self, redis_manager):
        entry_id = redis_manager.xadd("stream1", {"data": "hello"})
        assert entry_id is not None
        entries = redis_manager.xrange("stream1")
        assert len(entries) == 1
        assert entries[0][1]["data"] == "hello"

    def test_xadd_with_maxlen(self, redis_manager):
        for i in range(10):
            redis_manager.xadd("stream1", {"i": str(i)}, maxlen=5)
        assert redis_manager.xlen("stream1") <= 6  # approximate

    def test_xlen(self, redis_manager):
        redis_manager.xadd("stream1", {"a": "1"})
        redis_manager.xadd("stream1", {"b": "2"})
        assert redis_manager.xlen("stream1") == 2

    def test_xtrim(self, redis_manager):
        for i in range(10):
            redis_manager.xadd("stream1", {"i": str(i)})
        redis_manager.xtrim("stream1", maxlen=3)
        assert redis_manager.xlen("stream1") <= 4  # approximate


class TestJSONHelpers:
    """Test JSON get/set helpers."""

    def test_set_json_and_get_json(self, redis_manager):
        data = {"name": "test", "count": 42, "nested": {"a": 1}}
        assert redis_manager.set_json("json1", data) is True
        result = redis_manager.get_json("json1")
        assert result == data

    def test_get_json_nonexistent(self, redis_manager):
        assert redis_manager.get_json("nonexistent") is None

    def test_get_json_invalid(self, redis_manager):
        redis_manager.set("bad_json", "not json{")
        assert redis_manager.get_json("bad_json") is None

    def test_hset_json_and_hget_json(self, redis_manager):
        data = {"x": 1, "y": [2, 3]}
        assert redis_manager.hset_json("hash1", "field1", data) is True
        result = redis_manager.hget_json("hash1", "field1")
        assert result == data

    def test_set_json_with_datetime(self, redis_manager):
        from datetime import datetime, timezone

        dt = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        data = {"timestamp": dt}
        assert redis_manager.set_json("dt_test", data) is True
        result = redis_manager.get_json("dt_test")
        assert result["timestamp"] == "2026-03-07 12:00:00+00:00"


class TestGracefulDegradation:
    """Test that operations return safe defaults when Redis is unavailable."""

    def test_get_returns_none(self, disabled_manager):
        assert disabled_manager.get("key") is None

    def test_set_returns_false(self, disabled_manager):
        assert disabled_manager.set("key", "val") is False

    def test_delete_returns_zero(self, disabled_manager):
        assert disabled_manager.delete("key") == 0

    def test_exists_returns_false(self, disabled_manager):
        assert disabled_manager.exists("key") is False

    def test_incr_returns_none(self, disabled_manager):
        assert disabled_manager.incr("key") is None

    def test_hset_returns_false(self, disabled_manager):
        assert disabled_manager.hset("key", "field", "val") is False

    def test_hget_returns_none(self, disabled_manager):
        assert disabled_manager.hget("key", "field") is None

    def test_hgetall_returns_empty(self, disabled_manager):
        assert disabled_manager.hgetall("key") == {}

    def test_sadd_returns_zero(self, disabled_manager):
        assert disabled_manager.sadd("key", "val") == 0

    def test_smembers_returns_empty(self, disabled_manager):
        assert disabled_manager.smembers("key") == set()

    def test_lpush_returns_zero(self, disabled_manager):
        assert disabled_manager.lpush("key", "val") == 0

    def test_rpop_returns_none(self, disabled_manager):
        assert disabled_manager.rpop("key") is None

    def test_xadd_returns_none(self, disabled_manager):
        assert disabled_manager.xadd("key", {"a": "b"}) is None

    def test_xrange_returns_empty(self, disabled_manager):
        assert disabled_manager.xrange("key") == []

    def test_get_json_returns_none(self, disabled_manager):
        assert disabled_manager.get_json("key") is None

    def test_set_json_returns_false(self, disabled_manager):
        assert disabled_manager.set_json("key", {"a": 1}) is False


class TestHealthStatus:
    """Test health status reporting."""

    def test_health_when_available(self, redis_manager):
        status = redis_manager.get_health_status()
        assert status["enabled"] is True
        assert status["available"] is True
        assert status["status"] == "connected"

    def test_health_when_disabled(self, disabled_manager):
        status = disabled_manager.get_health_status()
        assert status["enabled"] is False
        assert status["status"] == "disabled"

    def test_health_when_unavailable(self, redis_manager):
        redis_manager._is_available = False
        redis_manager._last_error = "Connection refused"
        redis_manager._consecutive_failures = 3
        status = redis_manager.get_health_status()
        assert status["status"] == "unavailable"
        assert status["last_error"] == "Connection refused"
        assert status["consecutive_failures"] == 3


class TestFlushNamespace:
    """Test namespace flush operation."""

    def test_flush_namespace(self, redis_manager):
        redis_manager.set(redis_manager.key("a"), "1")
        redis_manager.set(redis_manager.key("b"), "2")
        redis_manager.set("other:key", "3")  # different namespace
        deleted = redis_manager.flush_namespace()
        assert deleted == 2
        assert redis_manager.get("other:key") == "3"
