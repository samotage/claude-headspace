"""Tests for session registry."""

import threading
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from claude_headspace.services.session_registry import (
    RegisteredSession,
    SessionRegistry,
)


class TestRegisteredSession:
    """Test RegisteredSession dataclass."""

    def test_create_session(self):
        """Test creating a session with required fields."""
        session_uuid = uuid4()
        session = RegisteredSession(
            session_uuid=session_uuid,
            project_path="/test/project",
            working_directory="/test/project",
        )
        assert session.session_uuid == session_uuid
        assert session.project_path == "/test/project"
        assert session.working_directory == "/test/project"
        assert session.iterm_pane_id is None
        assert session.jsonl_file_path is None
        assert session.registered_at is not None
        assert session.last_activity_at is not None

    def test_create_session_with_optional_fields(self):
        """Test creating session with optional fields."""
        session_uuid = uuid4()
        session = RegisteredSession(
            session_uuid=session_uuid,
            project_path="/test/project",
            working_directory="/test/project",
            iterm_pane_id="pane-123",
        )
        assert session.iterm_pane_id == "pane-123"


class TestSessionRegistry:
    """Test SessionRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return SessionRegistry()

    def test_register_session(self, registry):
        """Test registering a session."""
        session_uuid = uuid4()
        session = registry.register_session(
            session_uuid=session_uuid,
            project_path="/test/project",
            working_directory="/test/project",
        )
        assert session.session_uuid == session_uuid
        assert registry.is_session_registered(session_uuid)

    def test_register_session_with_iterm_pane(self, registry):
        """Test registering session with iTerm pane ID."""
        session_uuid = uuid4()
        session = registry.register_session(
            session_uuid=session_uuid,
            project_path="/test/project",
            working_directory="/test/project",
            iterm_pane_id="pane-123",
        )
        assert session.iterm_pane_id == "pane-123"

    def test_unregister_session(self, registry):
        """Test unregistering a session."""
        session_uuid = uuid4()
        registry.register_session(
            session_uuid=session_uuid,
            project_path="/test/project",
            working_directory="/test/project",
        )
        assert registry.unregister_session(session_uuid) is True
        assert registry.is_session_registered(session_uuid) is False

    def test_unregister_nonexistent_session(self, registry):
        """Test unregistering a session that doesn't exist."""
        assert registry.unregister_session(uuid4()) is False

    def test_get_registered_sessions(self, registry):
        """Test getting all registered sessions."""
        uuid1 = uuid4()
        uuid2 = uuid4()
        registry.register_session(uuid1, "/project1", "/project1")
        registry.register_session(uuid2, "/project2", "/project2")

        sessions = registry.get_registered_sessions()
        assert len(sessions) == 2
        uuids = {s.session_uuid for s in sessions}
        assert uuid1 in uuids
        assert uuid2 in uuids

    def test_get_session(self, registry):
        """Test getting a specific session."""
        session_uuid = uuid4()
        registry.register_session(session_uuid, "/test", "/test")

        session = registry.get_session(session_uuid)
        assert session is not None
        assert session.session_uuid == session_uuid

    def test_get_nonexistent_session(self, registry):
        """Test getting a session that doesn't exist."""
        assert registry.get_session(uuid4()) is None

    def test_update_last_activity(self, registry):
        """Test updating last activity timestamp."""
        session_uuid = uuid4()
        registry.register_session(session_uuid, "/test", "/test")

        session_before = registry.get_session(session_uuid)
        original_time = session_before.last_activity_at

        # Small delay to ensure different timestamp
        time.sleep(0.01)

        registry.update_last_activity(session_uuid)
        session_after = registry.get_session(session_uuid)

        assert session_after.last_activity_at > original_time

    def test_update_last_activity_nonexistent(self, registry):
        """Test updating activity for nonexistent session."""
        assert registry.update_last_activity(uuid4()) is False

    def test_update_jsonl_path(self, registry):
        """Test updating jsonl file path."""
        session_uuid = uuid4()
        registry.register_session(session_uuid, "/test", "/test")

        registry.update_jsonl_path(session_uuid, "/path/to/session.jsonl")
        session = registry.get_session(session_uuid)
        assert session.jsonl_file_path == "/path/to/session.jsonl"

    def test_get_inactive_sessions(self, registry):
        """Test getting inactive sessions."""
        uuid1 = uuid4()
        uuid2 = uuid4()

        # Register two sessions
        registry.register_session(uuid1, "/project1", "/project1")
        registry.register_session(uuid2, "/project2", "/project2")

        # Make one session "old" by modifying its last_activity_at
        session1 = registry.get_session(uuid1)
        session1.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=2)

        # Get sessions inactive for more than 1 hour
        inactive = registry.get_inactive_sessions(3600)
        assert len(inactive) == 1
        assert inactive[0].session_uuid == uuid1

    def test_clear(self, registry):
        """Test clearing all sessions."""
        registry.register_session(uuid4(), "/project1", "/project1")
        registry.register_session(uuid4(), "/project2", "/project2")

        registry.clear()
        assert len(registry.get_registered_sessions()) == 0


class TestSessionRegistryThreadSafety:
    """Test thread safety of SessionRegistry."""

    def test_concurrent_registration(self):
        """Test concurrent session registration."""
        registry = SessionRegistry()
        num_threads = 10
        sessions_per_thread = 100

        def register_sessions():
            for _ in range(sessions_per_thread):
                uuid = uuid4()
                registry.register_session(uuid, "/test", "/test")

        threads = [threading.Thread(target=register_sessions) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(registry.get_registered_sessions()) == num_threads * sessions_per_thread

    def test_concurrent_unregistration(self):
        """Test concurrent session unregistration."""
        registry = SessionRegistry()
        uuids = [uuid4() for _ in range(100)]
        for uuid in uuids:
            registry.register_session(uuid, "/test", "/test")

        def unregister_sessions(uuid_list):
            for uuid in uuid_list:
                registry.unregister_session(uuid)

        # Split UUIDs between threads
        mid = len(uuids) // 2
        t1 = threading.Thread(target=unregister_sessions, args=(uuids[:mid],))
        t2 = threading.Thread(target=unregister_sessions, args=(uuids[mid:],))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(registry.get_registered_sessions()) == 0
