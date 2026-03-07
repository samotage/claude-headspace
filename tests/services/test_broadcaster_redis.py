"""Tests for Redis-backed Broadcaster (event ID counter + replay buffer)."""

import fakeredis
import pytest

from claude_headspace.services.broadcaster import Broadcaster


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

    def incr(self, key):
        return self._client.incr(key)

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


@pytest.fixture
def redis_mgr():
    return FakeRedisManager()


@pytest.fixture
def broadcaster_with_redis(redis_mgr):
    b = Broadcaster(redis_manager=redis_mgr)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def broadcaster_no_redis():
    b = Broadcaster()
    b.start()
    yield b
    b.stop()


class TestRedisEventIdCounter:
    """Test event ID counter backed by Redis INCR."""

    def test_event_ids_increment_via_redis(self, broadcaster_with_redis, redis_mgr):
        broadcaster_with_redis.broadcast("test", {"msg": "a"})
        broadcaster_with_redis.broadcast("test", {"msg": "b"})
        # Check Redis has the counter
        stored = redis_mgr.get(redis_mgr.key("sse", "event_id"))
        assert stored is not None
        assert int(stored) >= 2

    def test_event_ids_persist_across_instances(self, redis_mgr):
        # First broadcaster increments counter
        b1 = Broadcaster(redis_manager=redis_mgr)
        b1.start()
        b1.broadcast("test", {"msg": "a"})
        b1.broadcast("test", {"msg": "b"})
        last_id = b1._event_id_counter
        b1.stop()

        # Second broadcaster should recover the counter
        b2 = Broadcaster(redis_manager=redis_mgr)
        b2.start()
        assert b2._event_id_counter == last_id
        b2.broadcast("test", {"msg": "c"})
        assert b2._event_id_counter == last_id + 1
        b2.stop()


class TestRedisReplayBuffer:
    """Test replay buffer backed by Redis Stream."""

    def test_replay_events_stored_in_redis(self, broadcaster_with_redis, redis_mgr):
        broadcaster_with_redis.broadcast("card_refresh", {"agent_id": 1})
        broadcaster_with_redis.broadcast("state_change", {"agent_id": 2})
        # Check Redis stream
        stream_len = redis_mgr.xlen(redis_mgr.key("sse", "replay"))
        assert stream_len == 2

    def test_get_replay_events_from_redis(self, broadcaster_with_redis, redis_mgr):
        broadcaster_with_redis.broadcast("ev1", {"data": "a"})
        broadcaster_with_redis.broadcast("ev2", {"data": "b"})
        broadcaster_with_redis.broadcast("ev3", {"data": "c"})
        # Get events after first one
        events = broadcaster_with_redis.get_replay_events(after_event_id=1)
        assert len(events) == 2
        assert events[0].event_type == "ev2"
        assert events[1].event_type == "ev3"

    def test_replay_with_filters(self, broadcaster_with_redis):
        broadcaster_with_redis.broadcast("type_a", {"agent_id": 1})
        broadcaster_with_redis.broadcast("type_b", {"agent_id": 2})
        broadcaster_with_redis.broadcast("type_a", {"agent_id": 3})
        events = broadcaster_with_redis.get_replay_events(
            after_event_id=0, filters={"types": ["type_a"]}
        )
        assert len(events) == 2
        assert all(e.event_type == "type_a" for e in events)


class TestFallbackBehavior:
    """Test broadcaster falls back to in-memory when Redis is unavailable."""

    def test_event_ids_work_without_redis(self, broadcaster_no_redis):
        broadcaster_no_redis.broadcast("test", {"msg": "a"})
        assert broadcaster_no_redis._event_id_counter >= 1

    def test_replay_works_without_redis(self, broadcaster_no_redis):
        broadcaster_no_redis.broadcast("ev1", {"data": "a"})
        broadcaster_no_redis.broadcast("ev2", {"data": "b"})
        events = broadcaster_no_redis.get_replay_events(after_event_id=0)
        assert len(events) == 2

    def test_fallback_on_redis_failure(self, broadcaster_with_redis, redis_mgr):
        broadcaster_with_redis.broadcast("ev1", {"data": "a"})
        redis_mgr._is_available = False
        # Should still broadcast using in-memory
        broadcaster_with_redis.broadcast("ev2", {"data": "b"})
        assert broadcaster_with_redis._event_id_counter >= 2


class TestHealthStatus:
    """Test health status includes redis_backed flag."""

    def test_health_with_redis(self, broadcaster_with_redis):
        status = broadcaster_with_redis.get_health_status()
        assert status["redis_backed"] is True

    def test_health_without_redis(self, broadcaster_no_redis):
        status = broadcaster_no_redis.get_health_status()
        assert status["redis_backed"] is False
