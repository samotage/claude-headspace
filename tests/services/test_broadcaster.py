"""Tests for the SSE broadcaster service."""

import threading
import time
from datetime import datetime, timezone
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.services.broadcaster import (
    Broadcaster,
    SSEClient,
    SSEEvent,
    get_broadcaster,
    init_broadcaster,
    shutdown_broadcaster,
)


class TestSSEClient:
    """Tests for the SSEClient dataclass."""

    def test_client_creation(self):
        """Test creating an SSE client."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
        )

        assert client.client_id == "test-123"
        assert client.last_event_at is None
        assert isinstance(client.event_queue, Queue)
        assert client.filters == {}
        assert client.failed_writes == 0
        assert client.is_active is True

    def test_client_with_filters(self):
        """Test creating a client with filters."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
            filters={
                "types": ["state_transition", "turn_detected"],
                "project_id": 42,
            },
        )

        assert client.filters["types"] == ["state_transition", "turn_detected"]
        assert client.filters["project_id"] == 42

    def test_matches_filter_no_filters(self):
        """Test filter matching with no filters set."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
        )

        assert client.matches_filter("state_transition", {}) is True
        assert client.matches_filter("turn_detected", {"project_id": 1}) is True

    def test_matches_filter_type_filter(self):
        """Test filter matching with type filter."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
            filters={"types": ["state_transition"]},
        )

        assert client.matches_filter("state_transition", {}) is True
        assert client.matches_filter("turn_detected", {}) is False

    def test_matches_filter_project_id(self):
        """Test filter matching with project_id filter."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
            filters={"project_id": 42},
        )

        assert client.matches_filter("state_transition", {"project_id": 42}) is True
        assert client.matches_filter("state_transition", {"project_id": 99}) is False
        assert client.matches_filter("state_transition", {}) is False

    def test_matches_filter_agent_id(self):
        """Test filter matching with agent_id filter."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
            filters={"agent_id": 7},
        )

        assert client.matches_filter("state_transition", {"agent_id": 7}) is True
        assert client.matches_filter("state_transition", {"agent_id": 8}) is False

    def test_matches_filter_combined(self):
        """Test filter matching with multiple filters."""
        client = SSEClient(
            client_id="test-123",
            connected_at=datetime.now(timezone.utc),
            filters={
                "types": ["state_transition"],
                "project_id": 42,
            },
        )

        # Both conditions must match
        assert (
            client.matches_filter("state_transition", {"project_id": 42}) is True
        )
        assert (
            client.matches_filter("turn_detected", {"project_id": 42}) is False
        )
        assert (
            client.matches_filter("state_transition", {"project_id": 99}) is False
        )


class TestSSEEvent:
    """Tests for the SSEEvent dataclass."""

    def test_event_creation(self):
        """Test creating an SSE event."""
        event = SSEEvent(
            event_type="state_transition",
            data={"agent_id": 1, "new_state": "processing"},
            event_id=42,
        )

        assert event.event_type == "state_transition"
        assert event.data == {"agent_id": 1, "new_state": "processing"}
        assert event.event_id == 42
        assert event.timestamp is not None

    def test_event_format(self):
        """Test formatting an event as SSE string."""
        event = SSEEvent(
            event_type="state_transition",
            data={"agent_id": 1},
            event_id=42,
        )

        formatted = event.format()

        assert "event: state_transition\n" in formatted
        assert "id: 42\n" in formatted
        assert 'data: {"agent_id": 1}\n' in formatted
        assert formatted.endswith("\n\n")

    def test_event_format_complex_data(self):
        """Test formatting an event with complex data."""
        event = SSEEvent(
            event_type="turn_detected",
            data={
                "agent_id": 1,
                "content": "Hello, world!",
                "nested": {"key": "value"},
            },
            event_id=100,
        )

        formatted = event.format()

        assert "event: turn_detected\n" in formatted
        assert "id: 100\n" in formatted
        assert '"agent_id": 1' in formatted
        assert '"content": "Hello, world!"' in formatted


class TestBroadcaster:
    """Tests for the Broadcaster class."""

    def test_broadcaster_creation(self):
        """Test creating a broadcaster."""
        broadcaster = Broadcaster(
            max_connections=50,
            heartbeat_interval=15.0,
            connection_timeout=30.0,
            retry_after=10,
        )

        assert broadcaster.max_connections == 50
        assert broadcaster.retry_after == 10
        assert broadcaster.active_connections == 0
        assert broadcaster._running is False

    def test_broadcaster_start_stop(self):
        """Test starting and stopping the broadcaster."""
        broadcaster = Broadcaster()
        broadcaster.start()

        assert broadcaster._running is True

        broadcaster.stop()

        assert broadcaster._running is False

    def test_broadcaster_double_start(self):
        """Test that starting twice is safe."""
        broadcaster = Broadcaster()
        broadcaster.start()
        broadcaster.start()  # Should not raise

        assert broadcaster._running is True
        broadcaster.stop()

    def test_broadcaster_double_stop(self):
        """Test that stopping twice is safe."""
        broadcaster = Broadcaster()
        broadcaster.start()
        broadcaster.stop()
        broadcaster.stop()  # Should not raise

        assert broadcaster._running is False

    def test_register_client(self):
        """Test registering a client."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()

            assert client_id is not None
            assert broadcaster.active_connections == 1

            client = broadcaster.get_client(client_id)
            assert client is not None
            assert client.is_active is True
        finally:
            broadcaster.stop()

    def test_register_client_with_filters(self):
        """Test registering a client with filters."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client(
                types=["state_transition"],
                project_id=42,
                agent_id=7,
            )

            client = broadcaster.get_client(client_id)
            assert client.filters["types"] == ["state_transition"]
            assert client.filters["project_id"] == 42
            assert client.filters["agent_id"] == 7
        finally:
            broadcaster.stop()

    def test_register_client_at_limit(self):
        """Test registering a client when at connection limit."""
        broadcaster = Broadcaster(max_connections=2)
        broadcaster.start()

        try:
            client1 = broadcaster.register_client()
            client2 = broadcaster.register_client()
            client3 = broadcaster.register_client()  # Should fail

            assert client1 is not None
            assert client2 is not None
            assert client3 is None
            assert broadcaster.active_connections == 2
        finally:
            broadcaster.stop()

    def test_unregister_client(self):
        """Test unregistering a client."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            assert broadcaster.active_connections == 1

            result = broadcaster.unregister_client(client_id)

            assert result is True
            assert broadcaster.active_connections == 0
            assert broadcaster.get_client(client_id) is None
        finally:
            broadcaster.stop()

    def test_unregister_nonexistent_client(self):
        """Test unregistering a client that doesn't exist."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            result = broadcaster.unregister_client("nonexistent")
            assert result is False
        finally:
            broadcaster.stop()

    def test_broadcast_event(self):
        """Test broadcasting an event."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            client = broadcaster.get_client(client_id)

            sent_count = broadcaster.broadcast(
                "state_transition",
                {"agent_id": 1, "new_state": "processing"},
            )

            assert sent_count == 1
            assert not client.event_queue.empty()

            event = client.event_queue.get_nowait()
            assert event.event_type == "state_transition"
            assert event.data["agent_id"] == 1
        finally:
            broadcaster.stop()

    def test_broadcast_to_multiple_clients(self):
        """Test broadcasting to multiple clients."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client1_id = broadcaster.register_client()
            client2_id = broadcaster.register_client()
            client3_id = broadcaster.register_client()

            sent_count = broadcaster.broadcast("test_event", {"data": "value"})

            assert sent_count == 3

            for client_id in [client1_id, client2_id, client3_id]:
                client = broadcaster.get_client(client_id)
                assert not client.event_queue.empty()
        finally:
            broadcaster.stop()

    def test_broadcast_with_filtering(self):
        """Test that broadcast respects client filters."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            # Client 1: only state_transition events
            client1_id = broadcaster.register_client(types=["state_transition"])
            # Client 2: no filter
            client2_id = broadcaster.register_client()

            # Broadcast turn_detected
            sent_count = broadcaster.broadcast("turn_detected", {})

            assert sent_count == 1  # Only client2

            client1 = broadcaster.get_client(client1_id)
            client2 = broadcaster.get_client(client2_id)

            assert client1.event_queue.empty()
            assert not client2.event_queue.empty()
        finally:
            broadcaster.stop()

    def test_broadcast_with_project_filter(self):
        """Test that broadcast respects project_id filter."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client1_id = broadcaster.register_client(project_id=42)
            client2_id = broadcaster.register_client(project_id=99)

            sent_count = broadcaster.broadcast(
                "state_transition",
                {"project_id": 42},
            )

            assert sent_count == 1

            client1 = broadcaster.get_client(client1_id)
            client2 = broadcaster.get_client(client2_id)

            assert not client1.event_queue.empty()
            assert client2.event_queue.empty()
        finally:
            broadcaster.stop()

    def test_broadcast_error(self):
        """Test broadcasting an error event."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            client = broadcaster.get_client(client_id)

            sent_count = broadcaster.broadcast_error("connection_lost", "Test error")

            assert sent_count == 1

            event = client.event_queue.get_nowait()
            assert event.event_type == "error"
            assert event.data["error_type"] == "connection_lost"
            assert event.data["message"] == "Test error"
        finally:
            broadcaster.stop()

    def test_get_next_event_timeout(self):
        """Test get_next_event with timeout."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()

            # Should timeout since no events
            event = broadcaster.get_next_event(client_id, timeout=0.1)

            assert event is None
        finally:
            broadcaster.stop()

    def test_get_next_event_with_event(self):
        """Test get_next_event when event is available."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            broadcaster.broadcast("test_event", {"data": "value"})

            event = broadcaster.get_next_event(client_id, timeout=1.0)

            assert event is not None
            assert event.event_type == "test_event"
        finally:
            broadcaster.stop()

    def test_get_next_event_nonexistent_client(self):
        """Test get_next_event for nonexistent client."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            event = broadcaster.get_next_event("nonexistent", timeout=0.1)
            assert event is None
        finally:
            broadcaster.stop()

    def test_mark_failed_write(self):
        """Test marking a failed write."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            client = broadcaster.get_client(client_id)

            assert client.failed_writes == 0

            broadcaster.mark_failed_write(client_id)

            assert client.failed_writes == 1
        finally:
            broadcaster.stop()

    def test_can_accept_connection(self):
        """Test can_accept_connection check."""
        broadcaster = Broadcaster(max_connections=2)
        broadcaster.start()

        try:
            assert broadcaster.can_accept_connection() is True

            broadcaster.register_client()
            assert broadcaster.can_accept_connection() is True

            broadcaster.register_client()
            assert broadcaster.can_accept_connection() is False
        finally:
            broadcaster.stop()

    def test_event_id_monotonic(self):
        """Test that event IDs are monotonically increasing."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            client = broadcaster.get_client(client_id)

            broadcaster.broadcast("event1", {})
            broadcaster.broadcast("event2", {})
            broadcaster.broadcast("event3", {})

            event1 = client.event_queue.get_nowait()
            event2 = client.event_queue.get_nowait()
            event3 = client.event_queue.get_nowait()

            assert event1.event_id < event2.event_id < event3.event_id
        finally:
            broadcaster.stop()

    def test_get_health_status(self):
        """Test getting health status."""
        broadcaster = Broadcaster(max_connections=50)
        broadcaster.start()

        try:
            broadcaster.register_client()
            broadcaster.register_client()

            status = broadcaster.get_health_status()

            assert status["status"] == "healthy"
            assert status["active_connections"] == 2
            assert status["max_connections"] == 50
            assert status["running"] is True
        finally:
            broadcaster.stop()

    def test_get_health_status_stopped(self):
        """Test health status when stopped."""
        broadcaster = Broadcaster()

        status = broadcaster.get_health_status()

        assert status["status"] == "stopped"
        assert status["running"] is False

    def test_thread_safety_registration(self):
        """Test thread-safe client registration."""
        broadcaster = Broadcaster(max_connections=100)
        broadcaster.start()

        try:
            results = []
            threads = []

            def register_client():
                client_id = broadcaster.register_client()
                if client_id:
                    results.append(client_id)

            # Register from multiple threads
            for _ in range(20):
                t = threading.Thread(target=register_client)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # All registrations should succeed
            assert len(results) == 20
            assert broadcaster.active_connections == 20
        finally:
            broadcaster.stop()

    def test_thread_safety_broadcast(self):
        """Test thread-safe broadcasting."""
        broadcaster = Broadcaster()
        broadcaster.start()

        try:
            client_id = broadcaster.register_client()
            client = broadcaster.get_client(client_id)

            threads = []
            for i in range(10):
                t = threading.Thread(
                    target=lambda x: broadcaster.broadcast("event", {"n": x}),
                    args=(i,),
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # All events should be in queue
            events = []
            while not client.event_queue.empty():
                events.append(client.event_queue.get_nowait())

            assert len(events) == 10
        finally:
            broadcaster.stop()


class TestGlobalBroadcaster:
    """Tests for global broadcaster instance management."""

    def teardown_method(self):
        """Clean up after each test."""
        shutdown_broadcaster()

    def test_init_broadcaster(self):
        """Test initializing the global broadcaster."""
        broadcaster = init_broadcaster()

        assert broadcaster is not None
        assert broadcaster._running is True

    def test_init_broadcaster_with_config(self):
        """Test initializing with configuration."""
        config = {
            "sse": {
                "max_connections": 50,
                "heartbeat_interval_seconds": 15,
            }
        }

        broadcaster = init_broadcaster(config)

        assert broadcaster.max_connections == 50
        assert broadcaster._heartbeat_interval == 15

    def test_init_broadcaster_idempotent(self):
        """Test that init_broadcaster is idempotent."""
        broadcaster1 = init_broadcaster()
        broadcaster2 = init_broadcaster()

        assert broadcaster1 is broadcaster2

    def test_get_broadcaster_not_initialized(self):
        """Test get_broadcaster when not initialized."""
        with pytest.raises(RuntimeError) as exc_info:
            get_broadcaster()

        assert "not initialized" in str(exc_info.value)

    def test_get_broadcaster_after_init(self):
        """Test get_broadcaster after initialization."""
        init_broadcaster()
        broadcaster = get_broadcaster()

        assert broadcaster is not None
        assert broadcaster._running is True

    def test_shutdown_broadcaster(self):
        """Test shutting down the global broadcaster."""
        init_broadcaster()
        shutdown_broadcaster()

        with pytest.raises(RuntimeError):
            get_broadcaster()

    def test_shutdown_broadcaster_not_initialized(self):
        """Test shutdown when not initialized (should not raise)."""
        shutdown_broadcaster()  # Should not raise
