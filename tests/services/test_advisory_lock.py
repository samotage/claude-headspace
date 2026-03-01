"""Unit tests for the advisory lock service.

Tests lock acquisition, release, timeout, non-blocking skip,
connection cleanup, key hashing, and nested safety.
"""

import struct
import threading
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.advisory_lock import (
    AdvisoryLockError,
    LockNamespace,
    advisory_lock,
    advisory_lock_or_skip,
    lock_key_from_string,
    _get_held_locks,
)


class TestLockNamespace:
    """Test the LockNamespace enum."""

    def test_agent_namespace_value(self):
        assert LockNamespace.AGENT == 1

    def test_namespace_is_int(self):
        assert isinstance(LockNamespace.AGENT, int)


class TestLockKeyFromString:
    """Test the lock_key_from_string utility."""

    def test_returns_int(self):
        result = lock_key_from_string("test")
        assert isinstance(result, int)

    def test_deterministic(self):
        """Same input always produces the same output."""
        a = lock_key_from_string("agent-42")
        b = lock_key_from_string("agent-42")
        assert a == b

    def test_different_inputs_different_keys(self):
        """Different inputs produce different keys."""
        a = lock_key_from_string("agent-1")
        b = lock_key_from_string("agent-2")
        assert a != b

    def test_fits_int32(self):
        """Result fits within signed int32 range."""
        key = lock_key_from_string("any-string")
        assert -2**31 <= key < 2**31

    def test_empty_string(self):
        """Empty string produces a valid key."""
        key = lock_key_from_string("")
        assert isinstance(key, int)


class TestAdvisoryLockError:
    """Test the AdvisoryLockError exception."""

    def test_is_exception(self):
        assert issubclass(AdvisoryLockError, Exception)

    def test_message(self):
        err = AdvisoryLockError("test message")
        assert str(err) == "test message"


class TestAdvisoryLock:
    """Test the blocking advisory_lock context manager."""

    def test_reentrancy_detection(self, app):
        """Nested advisory_lock for the same key raises AdvisoryLockError."""
        with app.app_context():
            # Manually add a key to simulate holding a lock
            held = _get_held_locks()
            lock_key = (int(LockNamespace.AGENT), 42)
            held.add(lock_key)
            try:
                with pytest.raises(AdvisoryLockError, match="Reentrant"):
                    with advisory_lock(LockNamespace.AGENT, 42):
                        pass  # pragma: no cover
            finally:
                held.discard(lock_key)

    def test_different_keys_no_reentrancy(self, app):
        """Different lock keys do not trigger reentrancy detection."""
        with app.app_context():
            held = _get_held_locks()
            lock_key = (int(LockNamespace.AGENT), 42)
            held.add(lock_key)
            try:
                # Key (AGENT, 99) is different from (AGENT, 42) -- no reentrancy
                # This would try to actually acquire a PG lock, so we mock the db import
                with patch("claude_headspace.database.db") as mock_db:
                    mock_engine = MagicMock()
                    mock_conn = MagicMock()
                    mock_engine.connect.return_value = mock_conn
                    mock_db.engine = mock_engine

                    with advisory_lock(LockNamespace.AGENT, 99):
                        pass

                    # Verify lock was acquired and released
                    assert mock_conn.execute.call_count >= 2  # lock + unlock
            finally:
                held.discard(lock_key)

    def test_lock_acquired_and_released(self, app):
        """Advisory lock is acquired and properly released."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                with advisory_lock(LockNamespace.AGENT, 1):
                    # Inside the lock -- key should be tracked
                    held = _get_held_locks()
                    assert (1, 1) in held

                # After exit -- key should be removed
                held = _get_held_locks()
                assert (1, 1) not in held

                # Connection should be closed
                mock_conn.close.assert_called()

    def test_lock_released_on_exception(self, app):
        """Advisory lock is released even when body raises."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                with pytest.raises(ValueError, match="test error"):
                    with advisory_lock(LockNamespace.AGENT, 5):
                        raise ValueError("test error")

                # Lock should be released
                held = _get_held_locks()
                assert (1, 5) not in held

                # Connection should be closed
                mock_conn.close.assert_called()

    def test_timeout_raises_advisory_lock_error(self, app):
        """Lock timeout raises AdvisoryLockError."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                # Simulate timeout on pg_advisory_lock
                mock_conn.execute.side_effect = [
                    None,  # SET lock_timeout
                    Exception("lock timeout"),  # pg_advisory_lock fails
                ]

                with pytest.raises(AdvisoryLockError, match="Failed to acquire"):
                    with advisory_lock(LockNamespace.AGENT, 10, timeout=1.0):
                        pass  # pragma: no cover


class TestAdvisoryLockOrSkip:
    """Test the non-blocking advisory_lock_or_skip context manager."""

    def test_reentrancy_yields_false(self, app):
        """Reentrant call yields False instead of deadlocking."""
        with app.app_context():
            held = _get_held_locks()
            lock_key = (int(LockNamespace.AGENT), 42)
            held.add(lock_key)
            try:
                with advisory_lock_or_skip(LockNamespace.AGENT, 42) as acquired:
                    assert acquired is False
            finally:
                held.discard(lock_key)

    def test_acquired_yields_true(self, app):
        """When lock is available, yields True."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                # pg_try_advisory_lock returns True
                mock_result = MagicMock()
                mock_result.scalar.return_value = True
                mock_conn.execute.return_value = mock_result

                with advisory_lock_or_skip(LockNamespace.AGENT, 1) as acquired:
                    assert acquired is True
                    held = _get_held_locks()
                    assert (1, 1) in held

                # After exit -- cleaned up
                held = _get_held_locks()
                assert (1, 1) not in held

    def test_not_acquired_yields_false(self, app):
        """When lock is held by another connection, yields False."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                # pg_try_advisory_lock returns False
                mock_result = MagicMock()
                mock_result.scalar.return_value = False
                mock_conn.execute.return_value = mock_result

                with advisory_lock_or_skip(LockNamespace.AGENT, 1) as acquired:
                    assert acquired is False

                # Connection should be closed
                mock_conn.close.assert_called()

    def test_error_yields_false(self, app):
        """Connection error yields False gracefully."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                # pg_try_advisory_lock raises an error
                mock_conn.execute.side_effect = Exception("connection error")

                with advisory_lock_or_skip(LockNamespace.AGENT, 1) as acquired:
                    assert acquired is False

    def test_lock_released_on_body_exception(self, app):
        """Lock is released when the body raises an exception."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_engine.connect.return_value = mock_conn
                mock_db.engine = mock_engine

                mock_result = MagicMock()
                mock_result.scalar.return_value = True
                mock_conn.execute.return_value = mock_result

                with pytest.raises(RuntimeError, match="body error"):
                    with advisory_lock_or_skip(LockNamespace.AGENT, 7) as acquired:
                        assert acquired is True
                        raise RuntimeError("body error")

                # Lock should be cleaned up
                held = _get_held_locks()
                assert (1, 7) not in held


class TestGetHeldAdvisoryLocks:
    """Test the get_held_advisory_locks query function."""

    def test_returns_list(self, app):
        """Returns a list even with no locks held."""
        with app.app_context():
            from claude_headspace.services.advisory_lock import get_held_advisory_locks
            result = get_held_advisory_locks()
            assert isinstance(result, list)

    def test_handles_query_error(self, app):
        """Returns empty list on query errors."""
        with app.app_context():
            with patch("claude_headspace.database.db") as mock_db:
                mock_db.session.execute.side_effect = Exception("query failed")
                from claude_headspace.services.advisory_lock import get_held_advisory_locks
                result = get_held_advisory_locks()
                assert result == []
