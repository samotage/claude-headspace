"""Tests for file watcher service."""

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from claude_headspace.services.file_watcher import FileWatcher
from claude_headspace.services.project_decoder import encode_project_path


class TestFileWatcher:
    """Test FileWatcher class."""

    @pytest.fixture
    def temp_projects_dir(self):
        """Create a temporary Claude projects directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def watcher(self, temp_projects_dir):
        """Create a FileWatcher instance."""
        watcher = FileWatcher(
            projects_path=temp_projects_dir,
            polling_interval=0.1,
            inactivity_timeout=60,
            debounce_interval=0.05,
        )
        yield watcher
        watcher.stop()

    def test_create_watcher(self, temp_projects_dir):
        """Test creating a file watcher."""
        watcher = FileWatcher(projects_path=temp_projects_dir)
        assert watcher.registry is not None
        assert watcher.git_metadata is not None

    def test_start_stop(self, watcher):
        """Test starting and stopping the watcher."""
        watcher.start()
        assert watcher._running is True

        watcher.stop()
        assert watcher._running is False

    def test_register_session(self, watcher, temp_projects_dir):
        """Test registering a session."""
        session_uuid = uuid4()
        project_path = "/test/project"

        session = watcher.register_session(
            session_uuid=session_uuid,
            project_path=project_path,
            working_directory=project_path,
        )

        assert session.session_uuid == session_uuid
        assert watcher.is_session_registered(session_uuid)

    def test_register_session_with_existing_jsonl(self, watcher, temp_projects_dir):
        """Test registering session when jsonl file exists."""
        project_path = "/test/project"
        folder_name = encode_project_path(project_path)
        project_folder = os.path.join(temp_projects_dir, folder_name)
        os.makedirs(project_folder)

        # Create jsonl file
        jsonl_path = os.path.join(project_folder, "session.jsonl")
        with open(jsonl_path, "w") as f:
            f.write('{"type": "progress"}\n')

        session_uuid = uuid4()
        session = watcher.register_session(
            session_uuid=session_uuid,
            project_path=project_path,
            working_directory=project_path,
        )

        # Should have found and set the jsonl path
        updated_session = watcher.registry.get_session(session_uuid)
        assert updated_session.jsonl_file_path == jsonl_path

    def test_unregister_session(self, watcher):
        """Test unregistering a session."""
        session_uuid = uuid4()
        watcher.register_session(session_uuid, "/test", "/test")

        result = watcher.unregister_session(session_uuid)
        assert result is True
        assert not watcher.is_session_registered(session_uuid)

    def test_get_registered_sessions(self, watcher):
        """Test getting all registered sessions."""
        uuid1 = uuid4()
        uuid2 = uuid4()
        watcher.register_session(uuid1, "/project1", "/project1")
        watcher.register_session(uuid2, "/project2", "/project2")

        sessions = watcher.get_registered_sessions()
        assert len(sessions) == 2

    def test_set_polling_interval(self, watcher):
        """Test setting polling interval."""
        watcher.set_polling_interval(60)
        assert watcher._polling_interval == 60

    def test_turn_detected_callback(self, watcher, temp_projects_dir):
        """Test turn_detected callback is called."""
        events = []

        def on_turn(event):
            events.append(event)

        watcher.set_on_turn_detected(on_turn)
        watcher.start()

        # Create project folder and jsonl file
        project_path = "/test/project"
        folder_name = encode_project_path(project_path)
        project_folder = os.path.join(temp_projects_dir, folder_name)
        os.makedirs(project_folder)

        jsonl_path = os.path.join(project_folder, "session.jsonl")
        with open(jsonl_path, "w") as f:
            f.write("")  # Empty file initially

        # Register session
        session_uuid = uuid4()
        watcher.register_session(session_uuid, project_path, project_path)

        # Write a turn to the file
        with open(jsonl_path, "a") as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Hello!"},
                "timestamp": "2026-01-29T10:00:00Z",
            }) + "\n")

        # Wait for polling to detect it
        time.sleep(0.3)

        assert len(events) > 0
        assert events[0]["event_type"] == "turn_detected"
        assert events[0]["actor"] == "user"
        assert events[0]["text"] == "Hello!"
        assert events[0]["source"] == "polling"

    def test_session_ended_callback(self, watcher):
        """Test session_ended callback is called on timeout."""
        events = []

        def on_session_ended(event):
            events.append(event)

        watcher.set_on_session_ended(on_session_ended)

        # Create a watcher with very short timeout
        short_timeout_watcher = FileWatcher(
            projects_path=watcher._projects_path,
            polling_interval=0.05,
            inactivity_timeout=0.1,  # Very short timeout for testing
            debounce_interval=0.01,
        )
        short_timeout_watcher.set_on_session_ended(on_session_ended)
        short_timeout_watcher.start()

        # Register a session
        session_uuid = uuid4()
        session = short_timeout_watcher.register_session(
            session_uuid, "/test", "/test"
        )

        # Make session appear old
        session.last_activity_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        # Wait for timeout detection
        time.sleep(0.3)

        short_timeout_watcher.stop()

        assert len(events) > 0
        assert events[0]["event_type"] == "session_ended"
        assert events[0]["reason"] == "timeout"


class TestFileWatcherDebouncing:
    """Test debouncing behavior."""

    @pytest.fixture
    def temp_projects_dir(self):
        """Create a temporary Claude projects directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_debounce_rapid_changes(self, temp_projects_dir):
        """Test that rapid file changes are debounced."""
        events = []

        def on_turn(event):
            events.append(event)

        watcher = FileWatcher(
            projects_path=temp_projects_dir,
            polling_interval=0.5,
            debounce_interval=0.1,
        )
        watcher.set_on_turn_detected(on_turn)
        watcher.start()

        # Create project folder and jsonl file
        project_path = "/test/project"
        folder_name = encode_project_path(project_path)
        project_folder = os.path.join(temp_projects_dir, folder_name)
        os.makedirs(project_folder)

        jsonl_path = os.path.join(project_folder, "session.jsonl")
        with open(jsonl_path, "w") as f:
            f.write("")

        # Register session
        session_uuid = uuid4()
        watcher.register_session(session_uuid, project_path, project_path)

        # Write multiple rapid changes
        for i in range(5):
            with open(jsonl_path, "a") as f:
                f.write(json.dumps({
                    "type": "user",
                    "message": {"content": f"Message {i}"},
                    "timestamp": "2026-01-29T10:00:00Z",
                }) + "\n")
            time.sleep(0.01)  # Very fast writes

        # Wait for debounce + polling
        time.sleep(0.8)

        watcher.stop()

        # Should have all 5 messages, but processed in fewer batches
        assert len(events) == 5
