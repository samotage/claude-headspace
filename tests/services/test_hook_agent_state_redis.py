"""Tests for Redis-backed AgentHookState."""

import json

import fakeredis
import pytest

from claude_headspace.services.hook_agent_state import AgentHookState


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

    def set_nx(self, key, value, ex=None):
        result = self._client.set(key, value, ex=ex, nx=True)
        return result is not None

    def delete(self, *keys):
        return self._client.delete(*keys)

    def exists(self, key):
        return bool(self._client.exists(key))

    def expire(self, key, seconds):
        return bool(self._client.expire(key, seconds))

    def lpush(self, key, *values):
        return self._client.lpush(key, *values)

    def rpop(self, key):
        return self._client.rpop(key)

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


@pytest.fixture
def state_with_redis(redis_mgr):
    return AgentHookState(redis_manager=redis_mgr)


@pytest.fixture
def state_no_redis():
    return AgentHookState()


class TestAwaitingTool:
    def test_set_and_get(self, state_with_redis):
        state_with_redis.set_awaiting_tool(1, "Write")
        assert state_with_redis.get_awaiting_tool(1) == "Write"

    def test_clear(self, state_with_redis):
        state_with_redis.set_awaiting_tool(1, "Read")
        state_with_redis.clear_awaiting_tool(1)
        assert state_with_redis.get_awaiting_tool(1) is None

    def test_fallback(self, state_no_redis):
        state_no_redis.set_awaiting_tool(1, "Bash")
        assert state_no_redis.get_awaiting_tool(1) == "Bash"


class TestRespondPending:
    def test_set_and_consume(self, state_with_redis):
        state_with_redis.set_respond_pending(1)
        assert state_with_redis.consume_respond_pending(1) is True
        assert state_with_redis.consume_respond_pending(1) is False

    def test_is_respond_pending(self, state_with_redis):
        state_with_redis.set_respond_pending(1)
        assert state_with_redis.is_respond_pending(1) is True

    def test_fallback(self, state_no_redis):
        state_no_redis.set_respond_pending(1)
        assert state_no_redis.is_respond_pending(1) is True


class TestRespondInflight:
    def test_set_and_check(self, state_with_redis):
        state_with_redis.set_respond_inflight(1)
        assert state_with_redis.is_respond_inflight(1) is True

    def test_clear(self, state_with_redis):
        state_with_redis.set_respond_inflight(1)
        state_with_redis.clear_respond_inflight(1)
        assert state_with_redis.is_respond_inflight(1) is False


class TestDeferredStop:
    def test_try_claim(self, state_with_redis):
        assert state_with_redis.try_claim_deferred_stop(1) is True
        assert state_with_redis.try_claim_deferred_stop(1) is False

    def test_release(self, state_with_redis):
        state_with_redis.try_claim_deferred_stop(1)
        state_with_redis.release_deferred_stop(1)
        assert state_with_redis.is_deferred_stop_pending(1) is False

    def test_fallback(self, state_no_redis):
        assert state_no_redis.try_claim_deferred_stop(1) is True
        assert state_no_redis.try_claim_deferred_stop(1) is False


class TestTranscriptPositions:
    def test_set_and_get(self, state_with_redis):
        state_with_redis.set_transcript_position(1, 42)
        assert state_with_redis.get_transcript_position(1) == 42

    def test_clear(self, state_with_redis):
        state_with_redis.set_transcript_position(1, 42)
        state_with_redis.clear_transcript_position(1)
        assert state_with_redis.get_transcript_position(1) is None


class TestProgressTexts:
    def test_append_and_consume(self, state_with_redis):
        state_with_redis.append_progress_text(1, "step 1")
        state_with_redis.append_progress_text(1, "step 2")
        result = state_with_redis.consume_progress_texts(1)
        assert result is not None
        assert len(result) == 2

    def test_consume_empty(self, state_with_redis):
        assert state_with_redis.consume_progress_texts(99) is None


class TestSkillInjection:
    def test_set_and_consume(self, state_with_redis):
        state_with_redis.set_skill_injection_pending(1)
        assert state_with_redis.consume_skill_injection_pending(1) is True
        assert state_with_redis.consume_skill_injection_pending(1) is False


class TestContentDedup:
    def test_first_is_not_duplicate(self, state_with_redis):
        assert state_with_redis.is_duplicate_prompt(1, "hello world") is False

    def test_second_is_duplicate(self, state_with_redis):
        state_with_redis.is_duplicate_prompt(1, "hello world")
        assert state_with_redis.is_duplicate_prompt(1, "hello world") is True

    def test_different_text_not_duplicate(self, state_with_redis):
        state_with_redis.is_duplicate_prompt(1, "hello")
        assert state_with_redis.is_duplicate_prompt(1, "world") is False

    def test_fallback(self, state_no_redis):
        assert state_no_redis.is_duplicate_prompt(1, "test") is False
        assert state_no_redis.is_duplicate_prompt(1, "test") is True


class TestCommandRateLimiting:
    def test_not_rate_limited_initially(self, state_with_redis):
        assert state_with_redis.is_command_rate_limited(1) is False

    def test_rate_limited_after_max(self, state_with_redis):
        for _ in range(5):
            state_with_redis.record_command_creation(1)
        assert state_with_redis.is_command_rate_limited(1) is True


class TestLifecycle:
    def test_on_session_end_clears_all(self, state_with_redis, redis_mgr):
        state_with_redis.set_awaiting_tool(1, "Write")
        state_with_redis.set_transcript_position(1, 100)
        state_with_redis.set_skill_injection_pending(1)
        state_with_redis.on_session_end(1)
        assert state_with_redis.get_awaiting_tool(1) is None
        assert state_with_redis.get_transcript_position(1) is None

    def test_on_session_start_clears_scoped(self, state_with_redis):
        state_with_redis.set_transcript_position(1, 50)
        state_with_redis.on_session_start(1)
        assert state_with_redis.get_transcript_position(1) is None


class TestRedisFallback:
    def test_operations_work_after_redis_failure(self, state_with_redis, redis_mgr):
        state_with_redis.set_awaiting_tool(1, "Write")
        redis_mgr._is_available = False
        # In-memory still works
        assert state_with_redis.get_awaiting_tool(1) == "Write"
        state_with_redis.set_awaiting_tool(2, "Read")
        assert state_with_redis.get_awaiting_tool(2) == "Read"
