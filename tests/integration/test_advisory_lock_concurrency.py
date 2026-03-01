"""Multi-threaded concurrency tests for PostgreSQL advisory locks.

Tests serialisation, different agents, contention between hooks and
background threads, pool exhaustion, reentrancy detection, per-iteration
commit, exception during body, unconditional unlock, and lock_or_skip
reentrancy -- all against a real PostgreSQL database.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import text

from claude_headspace.services.advisory_lock import (
    AdvisoryLockError,
    LockNamespace,
    advisory_lock,
    advisory_lock_or_skip,
    _get_held_locks,
)


class TestSerialisation:
    """Verify that advisory locks serialise concurrent access."""

    def test_same_agent_serialised(self, app):
        """Two threads locking the same agent_id run sequentially, not concurrently."""
        results = []
        barrier = threading.Barrier(2, timeout=10)

        def worker(worker_id):
            with app.app_context():
                with advisory_lock(LockNamespace.AGENT, 1, timeout=10.0):
                    results.append(f"enter-{worker_id}")
                    time.sleep(0.2)
                    results.append(f"exit-{worker_id}")

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        # Both workers should complete
        assert len(results) == 4

        # Entries should be serialised: one worker fully completes before the
        # other starts. That means "enter-X, exit-X, enter-Y, exit-Y" pattern.
        # The first enterer should also be the first exiter.
        first_enter = results[0]  # "enter-X"
        worker_first = first_enter.split("-")[1]
        assert results[1] == f"exit-{worker_first}"
        # Second worker runs after
        second_idx = 2
        second_enter = results[second_idx]
        worker_second = second_enter.split("-")[1]
        assert results[second_idx + 1] == f"exit-{worker_second}"
        assert worker_first != worker_second

    def test_different_agents_concurrent(self, app):
        """Two threads locking different agent_ids can run concurrently."""
        order = []
        event = threading.Event()

        def worker(agent_id):
            with app.app_context():
                with advisory_lock(LockNamespace.AGENT, agent_id, timeout=10.0):
                    order.append(f"enter-{agent_id}")
                    event.wait(timeout=5)  # Wait for the other thread
                    order.append(f"exit-{agent_id}")

        t1 = threading.Thread(target=worker, args=(100,))
        t2 = threading.Thread(target=worker, args=(200,))
        t1.start()
        t2.start()

        # Give both threads time to enter their locks
        time.sleep(0.5)

        # Both should have entered by now since they hold different locks
        enter_count = sum(1 for item in order if item.startswith("enter-"))
        # Release both
        event.set()

        t1.join(timeout=10)
        t2.join(timeout=10)

        assert enter_count == 2, "Both threads should enter concurrently with different agent IDs"
        assert len(order) == 4


class TestHookReaperContention:
    """Simulate hook route + reaper contention on same agent."""

    def test_hook_blocks_reaper_skips(self, app):
        """When a hook holds the lock, reaper (lock_or_skip) gets False."""
        hook_entered = threading.Event()
        hook_release = threading.Event()
        reaper_result = {}

        def hook_worker():
            with app.app_context():
                with advisory_lock(LockNamespace.AGENT, 42, timeout=10.0):
                    hook_entered.set()
                    hook_release.wait(timeout=10)

        def reaper_worker():
            hook_entered.wait(timeout=5)
            with app.app_context():
                with advisory_lock_or_skip(LockNamespace.AGENT, 42) as acquired:
                    reaper_result["acquired"] = acquired

        t_hook = threading.Thread(target=hook_worker)
        t_reaper = threading.Thread(target=reaper_worker)

        t_hook.start()
        t_reaper.start()

        t_reaper.join(timeout=10)

        # Reaper should have gotten False since hook holds the lock
        assert reaper_result.get("acquired") is False

        # Release hook
        hook_release.set()
        t_hook.join(timeout=10)


class TestDeferredStopSessionEnd:
    """Simulate deferred_stop + session_end contention."""

    def test_serialised_access(self, app):
        """Two threads contending for the same agent lock serialise correctly."""
        execution_order = []

        def deferred_stop():
            with app.app_context():
                with advisory_lock(LockNamespace.AGENT, 55, timeout=10.0):
                    execution_order.append("deferred_stop_enter")
                    time.sleep(0.3)
                    execution_order.append("deferred_stop_exit")

        def session_end():
            time.sleep(0.1)  # Slight delay to ensure deferred_stop gets lock first
            with app.app_context():
                with advisory_lock(LockNamespace.AGENT, 55, timeout=10.0):
                    execution_order.append("session_end_enter")
                    execution_order.append("session_end_exit")

        t1 = threading.Thread(target=deferred_stop)
        t2 = threading.Thread(target=session_end)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert len(execution_order) == 4
        # Verify serialisation: one completes before the other starts
        if execution_order[0] == "deferred_stop_enter":
            assert execution_order[1] == "deferred_stop_exit"
            assert execution_order[2] == "session_end_enter"
        else:
            assert execution_order[0] == "session_end_enter"
            assert execution_order[1] == "session_end_exit"
            assert execution_order[2] == "deferred_stop_enter"


class TestReentrancyDetection:
    """Test reentrancy detection with real database."""

    def test_blocking_reentrancy_raises(self, app):
        """Reentrant advisory_lock raises AdvisoryLockError immediately."""
        with app.app_context():
            with advisory_lock(LockNamespace.AGENT, 77, timeout=10.0):
                with pytest.raises(AdvisoryLockError, match="Reentrant"):
                    with advisory_lock(LockNamespace.AGENT, 77, timeout=1.0):
                        pass  # pragma: no cover

    def test_skip_reentrancy_yields_false(self, app):
        """Reentrant advisory_lock_or_skip yields False instead of deadlocking."""
        with app.app_context():
            with advisory_lock(LockNamespace.AGENT, 88, timeout=10.0):
                with advisory_lock_or_skip(LockNamespace.AGENT, 88) as acquired:
                    assert acquired is False


class TestExceptionDuringBody:
    """Test lock cleanup when the protected body raises an exception."""

    def test_blocking_lock_released_on_body_exception(self, app):
        """advisory_lock releases the PG lock even when the body raises."""
        with app.app_context():
            with pytest.raises(RuntimeError, match="intentional"):
                with advisory_lock(LockNamespace.AGENT, 33, timeout=10.0):
                    raise RuntimeError("intentional error")

            # Lock should be released -- verify by acquiring it again
            with advisory_lock(LockNamespace.AGENT, 33, timeout=2.0):
                pass  # Should succeed without timeout

    def test_skip_lock_released_on_body_exception(self, app):
        """advisory_lock_or_skip releases the PG lock even when the body raises."""
        with app.app_context():
            with pytest.raises(RuntimeError, match="intentional"):
                with advisory_lock_or_skip(LockNamespace.AGENT, 34) as acquired:
                    assert acquired is True
                    raise RuntimeError("intentional error")

            # Lock should be released -- verify by acquiring it again
            with advisory_lock_or_skip(LockNamespace.AGENT, 34) as acquired:
                assert acquired is True


class TestUnconditionalUnlock:
    """Test that pg_advisory_unlock is always called."""

    def test_lock_released_after_normal_exit(self, app):
        """Lock is released after normal context manager exit."""
        with app.app_context():
            with advisory_lock(LockNamespace.AGENT, 44, timeout=10.0):
                pass

            # Verify we can re-acquire (lock is released)
            with advisory_lock(LockNamespace.AGENT, 44, timeout=2.0):
                pass

    def test_thread_local_cleaned_up(self, app):
        """Thread-local held_locks set is cleaned up after exit."""
        with app.app_context():
            with advisory_lock(LockNamespace.AGENT, 55, timeout=10.0):
                held = _get_held_locks()
                assert (1, 55) in held

            held = _get_held_locks()
            assert (1, 55) not in held


class TestPerIterationCommit:
    """Test that commits work correctly inside advisory lock scope."""

    def test_commit_inside_blocking_lock(self, app):
        """db.session.commit() works while holding an advisory lock."""
        from claude_headspace.database import db

        with app.app_context():
            with advisory_lock(LockNamespace.AGENT, 66, timeout=10.0):
                # Execute a simple query and commit -- should not release the lock
                db.session.execute(text("SELECT 1"))
                db.session.commit()

                # Lock should still be held
                held = _get_held_locks()
                assert (1, 66) in held

            # After exiting, lock should be released
            held = _get_held_locks()
            assert (1, 66) not in held

    def test_commit_inside_skip_lock(self, app):
        """db.session.commit() works while holding a non-blocking advisory lock."""
        from claude_headspace.database import db

        with app.app_context():
            with advisory_lock_or_skip(LockNamespace.AGENT, 67) as acquired:
                assert acquired is True

                db.session.execute(text("SELECT 1"))
                db.session.commit()

                # Lock should still be held
                held = _get_held_locks()
                assert (1, 67) in held


class TestLockOrSkipConcurrency:
    """Test advisory_lock_or_skip under concurrent access."""

    def test_only_one_thread_acquires(self, app):
        """Only one thread acquires the lock; others get False."""
        lock_holder = threading.Event()
        all_done = threading.Event()
        results = {"acquired": 0, "skipped": 0}
        results_lock = threading.Lock()

        def worker():
            with app.app_context():
                with advisory_lock_or_skip(LockNamespace.AGENT, 99) as acquired:
                    with results_lock:
                        if acquired:
                            results["acquired"] += 1
                        else:
                            results["skipped"] += 1

                    if acquired:
                        lock_holder.set()
                        # Hold the lock while others try
                        all_done.wait(timeout=10)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()

        # Wait for the lock holder to be established
        lock_holder.wait(timeout=10)

        # Give other threads time to attempt and fail
        time.sleep(0.5)

        # Release everyone
        all_done.set()

        for t in threads:
            t.join(timeout=10)

        assert results["acquired"] == 1
        assert results["skipped"] == 4


class TestLockTimeout:
    """Test lock timeout behavior with real PostgreSQL."""

    def test_blocking_lock_timeout(self, app):
        """advisory_lock raises AdvisoryLockError on timeout."""
        lock_held = threading.Event()
        holder_release = threading.Event()

        def holder():
            with app.app_context():
                with advisory_lock(LockNamespace.AGENT, 111, timeout=10.0):
                    lock_held.set()
                    holder_release.wait(timeout=30)

        t_holder = threading.Thread(target=holder)
        t_holder.start()
        lock_held.wait(timeout=5)

        # Try to acquire the same lock with a very short timeout
        with app.app_context():
            with pytest.raises(AdvisoryLockError, match="Failed to acquire"):
                with advisory_lock(LockNamespace.AGENT, 111, timeout=0.5):
                    pass  # pragma: no cover

        holder_release.set()
        t_holder.join(timeout=10)
