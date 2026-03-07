"""Session registry for tracking registered Claude Code sessions.

Supports Redis-backed storage with in-memory fallback.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class RegisteredSession:
    """Data class representing a registered session."""

    session_uuid: UUID
    project_path: str
    working_directory: str
    iterm_pane_id: str | None = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    jsonl_file_path: str | None = None

    def to_dict(self) -> dict:
        """Serialise to dict for Redis storage."""
        return {
            "session_uuid": str(self.session_uuid),
            "project_path": self.project_path,
            "working_directory": self.working_directory,
            "iterm_pane_id": self.iterm_pane_id,
            "registered_at": self.registered_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "jsonl_file_path": self.jsonl_file_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RegisteredSession":
        """Deserialise from dict (Redis storage)."""
        return cls(
            session_uuid=UUID(data["session_uuid"]),
            project_path=data["project_path"],
            working_directory=data["working_directory"],
            iterm_pane_id=data.get("iterm_pane_id"),
            registered_at=datetime.fromisoformat(data["registered_at"]),
            last_activity_at=datetime.fromisoformat(data["last_activity_at"]),
            jsonl_file_path=data.get("jsonl_file_path"),
        )


class SessionRegistry:
    """
    Thread-safe registry for registered Claude Code sessions.

    When Redis is available, sessions are persisted for restart resilience.
    Falls back to in-memory-only when Redis is unavailable.
    """

    def __init__(self, redis_manager=None) -> None:
        self._sessions: dict[UUID, RegisteredSession] = {}
        self._lock = threading.Lock()
        self._redis = redis_manager

        # Recover sessions from Redis on startup
        if self._redis_available():
            self._recover_from_redis()

    def _redis_key(self) -> str:
        """Redis hash key for all sessions."""
        return self._redis.key("sessions")

    def _session_ttl_key(self, session_uuid: UUID) -> str:
        """Redis key for per-session TTL."""
        return self._redis.key("session", str(session_uuid))

    def _redis_available(self) -> bool:
        return self._redis is not None and self._redis.is_available

    def _recover_from_redis(self) -> None:
        """Load sessions from Redis on startup."""
        try:
            data = self._redis.hgetall(self._redis_key())
            recovered = 0
            for uuid_str, raw in data.items():
                try:
                    session = RegisteredSession.from_dict(json.loads(raw))
                    self._sessions[session.session_uuid] = session
                    recovered += 1
                except Exception as e:
                    logger.warning("Failed to recover session %s: %s", uuid_str, e)
            if recovered:
                logger.info("Recovered %d sessions from Redis", recovered)
        except Exception as e:
            logger.warning("Failed to recover sessions from Redis: %s", e)

    def _sync_to_redis(self, session: RegisteredSession) -> None:
        """Sync a session to Redis."""
        if not self._redis_available():
            return
        try:
            self._redis.hset_json(
                self._redis_key(),
                str(session.session_uuid),
                session.to_dict(),
            )
            # Set TTL key for this session (5 min, refreshed on activity)
            self._redis.set(self._session_ttl_key(session.session_uuid), "1", ex=300)
        except Exception:
            pass

    def _remove_from_redis(self, session_uuid: UUID) -> None:
        """Remove a session from Redis."""
        if not self._redis_available():
            return
        try:
            self._redis.hdel(self._redis_key(), str(session_uuid))
            self._redis.delete(self._session_ttl_key(session_uuid))
        except Exception:
            pass

    def register_session(
        self,
        session_uuid: UUID,
        project_path: str,
        working_directory: str,
        iterm_pane_id: str | None = None,
    ) -> RegisteredSession:
        """Register a new session for monitoring."""
        with self._lock:
            session = RegisteredSession(
                session_uuid=session_uuid,
                project_path=project_path,
                working_directory=working_directory,
                iterm_pane_id=iterm_pane_id,
            )
            self._sessions[session_uuid] = session
        self._sync_to_redis(session)
        return session

    def unregister_session(self, session_uuid: UUID) -> bool:
        """Unregister a session and stop monitoring."""
        with self._lock:
            if session_uuid in self._sessions:
                del self._sessions[session_uuid]
                self._remove_from_redis(session_uuid)
                return True
        return False

    def get_registered_sessions(self) -> list[RegisteredSession]:
        """Get all registered sessions."""
        with self._lock:
            return list(self._sessions.values())

    def is_session_registered(self, session_uuid: UUID) -> bool:
        """Check if a session is registered."""
        with self._lock:
            return session_uuid in self._sessions

    def get_session(self, session_uuid: UUID) -> RegisteredSession | None:
        """Get a specific registered session."""
        with self._lock:
            return self._sessions.get(session_uuid)

    def update_last_activity(self, session_uuid: UUID) -> bool:
        """Update the last activity timestamp for a session."""
        with self._lock:
            session = self._sessions.get(session_uuid)
            if session:
                session.last_activity_at = datetime.now(timezone.utc)
                self._sync_to_redis(session)
                return True
            return False

    def update_jsonl_path(self, session_uuid: UUID, jsonl_file_path: str) -> bool:
        """Update the jsonl file path for a session."""
        with self._lock:
            session = self._sessions.get(session_uuid)
            if session:
                session.jsonl_file_path = jsonl_file_path
                self._sync_to_redis(session)
                return True
            return False

    def get_inactive_sessions(self, timeout_seconds: int) -> list[RegisteredSession]:
        """Get sessions that have been inactive for longer than the timeout."""
        now = datetime.now(timezone.utc)
        with self._lock:
            inactive = []
            for session in self._sessions.values():
                elapsed = (now - session.last_activity_at).total_seconds()
                if elapsed > timeout_seconds:
                    inactive.append(session)
            return inactive

    def clear(self) -> None:
        """Clear all registered sessions."""
        with self._lock:
            self._sessions.clear()
        if self._redis_available():
            try:
                self._redis.delete(self._redis_key())
            except Exception:
                pass
