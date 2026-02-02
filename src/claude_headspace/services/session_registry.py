"""Session registry for tracking registered Claude Code sessions."""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID


@dataclass
class RegisteredSession:
    """Data class representing a registered session."""

    session_uuid: UUID
    project_path: str
    working_directory: str
    iterm_pane_id: Optional[str] = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    jsonl_file_path: Optional[str] = None


class SessionRegistry:
    """
    Thread-safe registry for registered Claude Code sessions.

    Only sessions explicitly registered via this registry are monitored.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, RegisteredSession] = {}
        self._lock = threading.Lock()

    def register_session(
        self,
        session_uuid: UUID,
        project_path: str,
        working_directory: str,
        iterm_pane_id: Optional[str] = None,
    ) -> RegisteredSession:
        """
        Register a new session for monitoring.

        Args:
            session_uuid: Unique identifier for the session
            project_path: Decoded project path
            working_directory: Original working directory
            iterm_pane_id: Optional iTerm pane ID for focus functionality

        Returns:
            The registered session
        """
        with self._lock:
            session = RegisteredSession(
                session_uuid=session_uuid,
                project_path=project_path,
                working_directory=working_directory,
                iterm_pane_id=iterm_pane_id,
            )
            self._sessions[session_uuid] = session
            return session

    def unregister_session(self, session_uuid: UUID) -> bool:
        """
        Unregister a session and stop monitoring.

        Args:
            session_uuid: UUID of the session to unregister

        Returns:
            True if session was unregistered, False if not found
        """
        with self._lock:
            if session_uuid in self._sessions:
                del self._sessions[session_uuid]
                return True
            return False

    def get_registered_sessions(self) -> list[RegisteredSession]:
        """
        Get all registered sessions.

        Returns:
            List of all registered sessions
        """
        with self._lock:
            return list(self._sessions.values())

    def is_session_registered(self, session_uuid: UUID) -> bool:
        """
        Check if a session is registered.

        Args:
            session_uuid: UUID of the session to check

        Returns:
            True if session is registered, False otherwise
        """
        with self._lock:
            return session_uuid in self._sessions

    def get_session(self, session_uuid: UUID) -> Optional[RegisteredSession]:
        """
        Get a specific registered session.

        Args:
            session_uuid: UUID of the session to get

        Returns:
            The registered session, or None if not found
        """
        with self._lock:
            return self._sessions.get(session_uuid)

    def update_last_activity(self, session_uuid: UUID) -> bool:
        """
        Update the last activity timestamp for a session.

        Args:
            session_uuid: UUID of the session to update

        Returns:
            True if session was updated, False if not found
        """
        with self._lock:
            session = self._sessions.get(session_uuid)
            if session:
                session.last_activity_at = datetime.now(timezone.utc)
                return True
            return False

    def update_jsonl_path(self, session_uuid: UUID, jsonl_file_path: str) -> bool:
        """
        Update the jsonl file path for a session.

        Args:
            session_uuid: UUID of the session to update
            jsonl_file_path: Path to the session's jsonl file

        Returns:
            True if session was updated, False if not found
        """
        with self._lock:
            session = self._sessions.get(session_uuid)
            if session:
                session.jsonl_file_path = jsonl_file_path
                return True
            return False

    def get_inactive_sessions(self, timeout_seconds: int) -> list[RegisteredSession]:
        """
        Get sessions that have been inactive for longer than the timeout.

        Args:
            timeout_seconds: Inactivity timeout in seconds

        Returns:
            List of inactive sessions
        """
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
