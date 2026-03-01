"""PostgreSQL advisory lock service for cross-connection serialisation.

Provides session-scoped advisory locks on dedicated connections, independent
of the application's db.session transactions. This ensures locks survive
intermediate commits within critical sections (hook processing does 2-8
commits per request).

Two context managers:
- advisory_lock(namespace, entity_id) -- blocking, raises on timeout
- advisory_lock_or_skip(namespace, entity_id) -- non-blocking, yields False if busy

Design decisions:
1. Single AGENT namespace -- eliminates nested lock scenarios and deadlock risk
2. Session-scoped locks on dedicated connections -- survive db.session.commit()
3. Thread-local reentrancy detection -- raises immediately instead of deadlocking
4. Unconditional pg_advisory_unlock in finally -- handles PostgreSQL Bug #17686
"""

import hashlib
import logging
import struct
import threading
from contextlib import contextmanager
from enum import IntEnum

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Thread-local storage for reentrancy detection
_thread_local = threading.local()


class LockNamespace(IntEnum):
    """Advisory lock namespace identifiers.

    PostgreSQL advisory locks take two int4 keys. The first key is the
    namespace, the second is the entity ID.
    """
    AGENT = 1


class AdvisoryLockError(Exception):
    """Raised when an advisory lock cannot be acquired."""
    pass


def lock_key_from_string(value: str) -> int:
    """Convert a string to a deterministic int32 lock key via BLAKE2b.

    Uses BLAKE2b with 4-byte digest, unpacked as a signed int32 to match
    PostgreSQL's int4 parameter type.

    Args:
        value: Arbitrary string to hash

    Returns:
        Signed int32 suitable for pg_advisory_lock's second parameter
    """
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=4).digest()
    return struct.unpack(">i", digest)[0]


def _get_held_locks() -> set:
    """Get the set of currently held lock keys for this thread."""
    if not hasattr(_thread_local, "held_locks"):
        _thread_local.held_locks = set()
    return _thread_local.held_locks


@contextmanager
def advisory_lock(namespace: LockNamespace, entity_id: int, timeout: float = 15.0):
    """Acquire a blocking PostgreSQL advisory lock on a dedicated connection.

    The lock is session-scoped: it survives all intermediate db.session.commit()
    calls within the block and is released when the context manager exits.

    Args:
        namespace: Lock namespace (e.g., LockNamespace.AGENT)
        entity_id: Entity ID (e.g., agent.id)
        timeout: Maximum seconds to wait for the lock (default 15s)

    Raises:
        AdvisoryLockError: If the lock cannot be acquired within timeout,
            or if a reentrant acquisition is attempted.

    Yields:
        None
    """
    lock_key = (int(namespace), entity_id)

    # Reentrancy detection: same thread, same key -> immediate error
    held = _get_held_locks()
    if lock_key in held:
        raise AdvisoryLockError(
            f"Reentrant advisory lock detected: namespace={namespace.name}, "
            f"entity_id={entity_id}. This would deadlock."
        )

    from ..database import db
    engine = db.engine

    conn = engine.connect()
    try:
        # Set lock_timeout for this connection.
        # SET does not support bound parameters in PostgreSQL, so we use
        # f-string formatting. Safe because timeout_ms is always an int.
        timeout_ms = int(timeout * 1000)
        if not isinstance(timeout_ms, int) or timeout_ms < 0:
            raise ValueError(f"Invalid lock timeout: {timeout_ms}")
        conn.execute(text(f"SET lock_timeout = '{timeout_ms}ms'"))

        # Attempt to acquire session-scoped advisory lock
        try:
            conn.execute(
                text("SELECT pg_advisory_lock(:ns, :id)"),
                {"ns": lock_key[0], "id": lock_key[1]},
            )
        except Exception as e:
            # Lock timeout or other error
            # Unconditional unlock in case of PostgreSQL Bug #17686:
            # lock_timeout can fire AFTER the lock is granted but BEFORE
            # the result is returned.
            try:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :id)"),
                    {"ns": lock_key[0], "id": lock_key[1]},
                )
            except Exception:
                pass  # Best effort cleanup
            conn.close()
            raise AdvisoryLockError(
                f"Failed to acquire advisory lock: namespace={namespace.name}, "
                f"entity_id={entity_id}, timeout={timeout}s: {e}"
            ) from e

        # Track for reentrancy detection
        held.add(lock_key)

        try:
            yield
        finally:
            # Always release the lock and clean up
            held.discard(lock_key)
            try:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :id)"),
                    {"ns": lock_key[0], "id": lock_key[1]},
                )
            except Exception as e:
                logger.warning(
                    f"Advisory lock unlock failed (non-fatal): "
                    f"namespace={namespace.name}, entity_id={entity_id}: {e}"
                )
            conn.close()
    except AdvisoryLockError:
        raise
    except Exception:
        # Ensure connection is closed on unexpected errors
        try:
            conn.close()
        except Exception:
            pass
        raise


@contextmanager
def advisory_lock_or_skip(namespace: LockNamespace, entity_id: int):
    """Try to acquire a non-blocking PostgreSQL advisory lock.

    If the lock is held by another connection, yields False immediately
    without raising an exception. The caller should skip processing.

    If this thread already holds the same lock (reentrancy), yields False
    instead of deadlocking.

    Args:
        namespace: Lock namespace (e.g., LockNamespace.AGENT)
        entity_id: Entity ID (e.g., agent.id)

    Yields:
        True if the lock was acquired, False if it was busy or reentrant.
    """
    lock_key = (int(namespace), entity_id)

    # Reentrancy detection: yield False instead of deadlocking
    held = _get_held_locks()
    if lock_key in held:
        logger.debug(
            f"advisory_lock_or_skip: reentrant call for "
            f"namespace={namespace.name}, entity_id={entity_id} — yielding False"
        )
        yield False
        return

    from ..database import db
    engine = db.engine

    lock_acquired = False
    conn = engine.connect()
    try:
        # Try non-blocking lock acquisition
        result = conn.execute(
            text("SELECT pg_try_advisory_lock(:ns, :id)"),
            {"ns": lock_key[0], "id": lock_key[1]},
        )
        acquired = result.scalar()

        if not acquired:
            conn.close()
            yield False
            return

        # Lock acquired — track and yield
        lock_acquired = True
        held.add(lock_key)
        try:
            yield True
        finally:
            held.discard(lock_key)
            try:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :id)"),
                    {"ns": lock_key[0], "id": lock_key[1]},
                )
            except Exception as e:
                logger.warning(
                    f"Advisory lock unlock failed (non-fatal): "
                    f"namespace={namespace.name}, entity_id={entity_id}: {e}"
                )
            conn.close()

    except Exception as e:
        # Ensure connection is closed on unexpected errors.
        # If the lock was acquired, the inner finally already cleaned up
        # and this is a body exception — re-raise instead of swallowing.
        if lock_acquired:
            raise
        try:
            conn.close()
        except Exception:
            pass
        logger.warning(
            f"advisory_lock_or_skip: error acquiring lock "
            f"namespace={namespace.name}, entity_id={entity_id}: {e}"
        )
        yield False


def get_held_advisory_locks():
    """Query PostgreSQL for all currently held advisory locks.

    Returns a list of dicts suitable for the /api/advisory-locks endpoint.
    """
    from ..database import db

    query = text("""
        SELECT
            l.pid,
            a.application_name,
            a.state,
            a.query_start,
            l.classid AS namespace,
            l.objid AS entity_id,
            l.mode,
            l.granted,
            EXTRACT(EPOCH FROM (now() - a.query_start)) AS duration_seconds
        FROM pg_locks l
        JOIN pg_stat_activity a ON l.pid = a.pid
        WHERE l.locktype = 'advisory'
        ORDER BY a.query_start DESC
    """)

    try:
        result = db.session.execute(query)
        locks = []
        for row in result:
            locks.append({
                "pid": row.pid,
                "application_name": row.application_name,
                "state": row.state,
                "query_start": row.query_start.isoformat() if row.query_start else None,
                "namespace": row.namespace,
                "entity_id": row.entity_id,
                "mode": row.mode,
                "granted": row.granted,
                "duration_seconds": round(row.duration_seconds, 2) if row.duration_seconds else None,
            })
        return locks
    except Exception as e:
        logger.warning(f"Failed to query advisory locks: {e}")
        return []
