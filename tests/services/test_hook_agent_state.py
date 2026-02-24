"""Tests for AgentHookState thread-safe state management."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest

from claude_headspace.services.hook_agent_state import (
    AgentHookState,
    get_agent_hook_state,
    reset_agent_hook_state,
)


@pytest.fixture
def state():
    """Create a fresh AgentHookState for each test."""
    return AgentHookState()


class TestAwaitingTool:
    def test_set_and_get(self, state):
        state.set_awaiting_tool(1, "Bash")
        assert state.get_awaiting_tool(1) == "Bash"

    def test_get_nonexistent(self, state):
        assert state.get_awaiting_tool(999) is None

    def test_clear(self, state):
        state.set_awaiting_tool(1, "Bash")
        cleared = state.clear_awaiting_tool(1)
        assert cleared == "Bash"
        assert state.get_awaiting_tool(1) is None

    def test_clear_nonexistent(self, state):
        assert state.clear_awaiting_tool(999) is None

    def test_overwrite(self, state):
        state.set_awaiting_tool(1, "Bash")
        state.set_awaiting_tool(1, "Read")
        assert state.get_awaiting_tool(1) == "Read"


class TestRespondPending:
    def test_set_and_consume(self, state):
        state.set_respond_pending(1)
        assert state.consume_respond_pending(1) is True

    def test_consume_clears_flag(self, state):
        state.set_respond_pending(1)
        state.consume_respond_pending(1)
        assert state.consume_respond_pending(1) is False

    def test_consume_nonexistent(self, state):
        assert state.consume_respond_pending(999) is False

    def test_consume_expired(self, state):
        state.set_respond_pending(1)
        # Monkey-patch the timestamp to simulate expiry
        with state._lock:
            state._respond_pending[1] = time.time() - 20.0
        assert state.consume_respond_pending(1) is False


class TestDeferredStop:
    def test_try_claim_success(self, state):
        assert state.try_claim_deferred_stop(1) is True

    def test_try_claim_already_pending(self, state):
        state.try_claim_deferred_stop(1)
        assert state.try_claim_deferred_stop(1) is False

    def test_release(self, state):
        state.try_claim_deferred_stop(1)
        state.release_deferred_stop(1)
        assert state.try_claim_deferred_stop(1) is True

    def test_release_nonexistent(self, state):
        # Should not raise
        state.release_deferred_stop(999)

    def test_is_pending(self, state):
        assert state.is_deferred_stop_pending(1) is False
        state.try_claim_deferred_stop(1)
        assert state.is_deferred_stop_pending(1) is True

    def test_concurrent_claim_only_one_wins(self, state):
        """Only one of N concurrent threads should successfully claim."""
        results = []

        def try_claim():
            return state.try_claim_deferred_stop(42)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(try_claim) for _ in range(20)]
            for f in as_completed(futures):
                results.append(f.result())

        # Exactly one thread should have claimed
        assert results.count(True) == 1
        assert results.count(False) == 19


class TestTranscriptPositions:
    def test_set_and_get(self, state):
        state.set_transcript_position(1, 1024)
        assert state.get_transcript_position(1) == 1024

    def test_get_nonexistent(self, state):
        assert state.get_transcript_position(999) is None

    def test_clear(self, state):
        state.set_transcript_position(1, 1024)
        cleared = state.clear_transcript_position(1)
        assert cleared == 1024
        assert state.get_transcript_position(1) is None

    def test_overwrite(self, state):
        state.set_transcript_position(1, 100)
        state.set_transcript_position(1, 200)
        assert state.get_transcript_position(1) == 200


class TestProgressTexts:
    def test_append_and_get(self, state):
        state.append_progress_text(1, "Step 1")
        state.append_progress_text(1, "Step 2")
        assert state.get_progress_texts(1) == ["Step 1", "Step 2"]

    def test_get_returns_copy(self, state):
        state.append_progress_text(1, "Step 1")
        copy = state.get_progress_texts(1)
        copy.append("mutated")
        assert state.get_progress_texts(1) == ["Step 1"]

    def test_get_nonexistent(self, state):
        assert state.get_progress_texts(999) == []

    def test_consume(self, state):
        state.append_progress_text(1, "Step 1")
        state.append_progress_text(1, "Step 2")
        consumed = state.consume_progress_texts(1)
        assert consumed == ["Step 1", "Step 2"]
        assert state.get_progress_texts(1) == []

    def test_consume_nonexistent(self, state):
        assert state.consume_progress_texts(999) is None

    def test_clear(self, state):
        state.append_progress_text(1, "Step 1")
        state.clear_progress_texts(1)
        assert state.get_progress_texts(1) == []

    def test_concurrent_append_no_data_loss(self, state):
        """Multiple threads appending should not lose data."""
        agent_id = 42
        num_threads = 10
        items_per_thread = 50

        def append_items(thread_id):
            for i in range(items_per_thread):
                state.append_progress_text(agent_id, f"t{thread_id}-{i}")

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(append_items, tid) for tid in range(num_threads)]
            for f in as_completed(futures):
                f.result()  # Raise any exceptions

        texts = state.get_progress_texts(agent_id)
        assert len(texts) == num_threads * items_per_thread


class TestFileMetadataPending:
    def test_set_and_consume(self, state):
        meta = {"filename": "test.py", "size": 1024}
        state.set_file_metadata_pending(1, meta)
        consumed = state.consume_file_metadata_pending(1)
        assert consumed == meta

    def test_consume_clears(self, state):
        state.set_file_metadata_pending(1, {"x": 1})
        state.consume_file_metadata_pending(1)
        assert state.consume_file_metadata_pending(1) is None

    def test_consume_nonexistent(self, state):
        assert state.consume_file_metadata_pending(999) is None


class TestLifecycleMethods:
    def test_on_session_start(self, state):
        state.set_transcript_position(1, 100)
        state.append_progress_text(1, "step")
        state.set_awaiting_tool(1, "Bash")  # NOT cleared by session_start

        state.on_session_start(1)

        assert state.get_transcript_position(1) is None
        assert state.get_progress_texts(1) == []
        assert state.get_awaiting_tool(1) == "Bash"  # preserved

    def test_on_session_end(self, state):
        state.set_awaiting_tool(1, "Bash")
        state.set_transcript_position(1, 100)
        state.append_progress_text(1, "step")

        state.on_session_end(1)

        assert state.get_awaiting_tool(1) is None
        assert state.get_transcript_position(1) is None
        assert state.get_progress_texts(1) == []

    def test_on_new_response_cycle(self, state):
        state.set_awaiting_tool(1, "Bash")
        state.append_progress_text(1, "step")
        state.set_transcript_position(1, 100)  # NOT cleared

        state.on_new_response_cycle(1)

        assert state.get_awaiting_tool(1) is None
        assert state.get_progress_texts(1) == []
        assert state.get_transcript_position(1) == 100  # preserved


class TestReset:
    def test_reset_clears_everything(self, state):
        state.set_awaiting_tool(1, "Bash")
        state.set_respond_pending(1)
        state.try_claim_deferred_stop(1)
        state.set_transcript_position(1, 100)
        state.append_progress_text(1, "step")
        state.set_file_metadata_pending(1, {"x": 1})

        state.reset()

        assert state.get_awaiting_tool(1) is None
        assert state.consume_respond_pending(1) is False
        assert state.try_claim_deferred_stop(1) is True  # slot now free
        assert state.get_transcript_position(1) is None
        assert state.get_progress_texts(1) == []
        assert state.consume_file_metadata_pending(1) is None


class TestSingleton:
    def test_get_returns_same_instance(self):
        reset_agent_hook_state()
        a = get_agent_hook_state()
        b = get_agent_hook_state()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_agent_hook_state()
        a.set_awaiting_tool(1, "Bash")
        reset_agent_hook_state()
        b = get_agent_hook_state()
        assert b.get_awaiting_tool(1) is None


class TestContentDedup:
    """Tests for is_duplicate_prompt() — content deduplication."""

    def test_first_prompt_not_duplicate(self, state):
        assert state.is_duplicate_prompt(1, "Fix the bug") is False

    def test_second_identical_prompt_is_duplicate(self, state):
        state.is_duplicate_prompt(1, "Fix the bug")
        assert state.is_duplicate_prompt(1, "Fix the bug") is True

    def test_different_prompt_not_duplicate(self, state):
        state.is_duplicate_prompt(1, "Fix the bug")
        assert state.is_duplicate_prompt(1, "Add a feature") is False

    def test_different_agent_not_duplicate(self, state):
        state.is_duplicate_prompt(1, "Fix the bug")
        assert state.is_duplicate_prompt(2, "Fix the bug") is False

    def test_none_text_not_duplicate(self, state):
        assert state.is_duplicate_prompt(1, None) is False

    def test_empty_text_not_duplicate(self, state):
        assert state.is_duplicate_prompt(1, "") is False

    def test_expired_entry_not_duplicate(self, state):
        state.is_duplicate_prompt(1, "Fix the bug")
        # Expire the entry
        with state._lock:
            state._recent_prompt_hashes[1] = [
                (state._recent_prompt_hashes[1][0][0], time.time() - 60)
            ]
        assert state.is_duplicate_prompt(1, "Fix the bug") is False

    def test_session_end_clears_dedup(self, state):
        state.is_duplicate_prompt(1, "Fix the bug")
        state.on_session_end(1)
        assert state.is_duplicate_prompt(1, "Fix the bug") is False

    def test_reset_clears_dedup(self, state):
        state.is_duplicate_prompt(1, "Fix the bug")
        state.reset()
        assert state.is_duplicate_prompt(1, "Fix the bug") is False

    def test_max_history_respected(self, state):
        """History should be capped at _DEDUP_MAX_HISTORY entries."""
        for i in range(10):
            state.is_duplicate_prompt(1, f"prompt-{i}")
        with state._lock:
            assert len(state._recent_prompt_hashes.get(1, [])) <= state._DEDUP_MAX_HISTORY


class TestCommandRateLimiting:
    """Tests for is_command_rate_limited() and record_command_creation()."""

    def test_not_rate_limited_initially(self, state):
        assert state.is_command_rate_limited(1) is False

    def test_rate_limited_after_max_commands(self, state):
        for _ in range(5):
            state.record_command_creation(1)
        assert state.is_command_rate_limited(1) is True

    def test_not_rate_limited_under_max(self, state):
        for _ in range(4):
            state.record_command_creation(1)
        assert state.is_command_rate_limited(1) is False

    def test_different_agents_independent(self, state):
        for _ in range(5):
            state.record_command_creation(1)
        assert state.is_command_rate_limited(2) is False

    def test_expired_entries_not_counted(self, state):
        for _ in range(5):
            state.record_command_creation(1)
        # Expire all entries
        with state._lock:
            state._command_creation_times[1] = [time.time() - 20 for _ in range(5)]
        assert state.is_command_rate_limited(1) is False

    def test_session_end_clears_rate_limit(self, state):
        for _ in range(5):
            state.record_command_creation(1)
        state.on_session_end(1)
        assert state.is_command_rate_limited(1) is False

    def test_reset_clears_rate_limit(self, state):
        for _ in range(5):
            state.record_command_creation(1)
        state.reset()
        assert state.is_command_rate_limited(1) is False


class TestThreadSafety:
    """Thread-safety stress tests following Broadcaster test patterns."""

    def test_concurrent_mixed_operations(self, state):
        """Multiple threads doing different operations should not corrupt state."""
        errors = []

        def writer(agent_id):
            try:
                for i in range(50):
                    state.set_awaiting_tool(agent_id, f"tool-{i}")
                    state.set_transcript_position(agent_id, i)
                    state.append_progress_text(agent_id, f"text-{i}")
            except Exception as e:
                errors.append(e)

        def reader(agent_id):
            try:
                for _ in range(50):
                    state.get_awaiting_tool(agent_id)
                    state.get_transcript_position(agent_id)
                    state.get_progress_texts(agent_id)
            except Exception as e:
                errors.append(e)

        def lifecycle(agent_id):
            try:
                for _ in range(20):
                    state.on_session_start(agent_id)
                    state.on_new_response_cycle(agent_id)
                    state.on_session_end(agent_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for aid in range(5):
                futures.append(executor.submit(writer, aid))
                futures.append(executor.submit(reader, aid))
                futures.append(executor.submit(lifecycle, aid))
            for f in as_completed(futures):
                f.result()

        assert errors == []
