"""Event broadcaster service for SSE (Server-Sent Events)."""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SSEClient:
    """Represents a connected SSE client."""

    client_id: str
    connected_at: datetime
    last_event_at: Optional[datetime] = None
    event_queue: Queue = field(default_factory=Queue)
    filters: dict = field(default_factory=dict)
    failed_writes: int = 0
    is_active: bool = True

    def matches_filter(self, event_type: str, payload: dict) -> bool:
        """
        Check if an event matches this client's filters.

        Args:
            event_type: The type of event
            payload: The event payload

        Returns:
            True if the event should be sent to this client
        """
        # Check event type filter
        if "types" in self.filters and self.filters["types"]:
            if event_type not in self.filters["types"]:
                return False

        # Check project_id filter
        if "project_id" in self.filters and self.filters["project_id"]:
            event_project_id = payload.get("project_id")
            if event_project_id != self.filters["project_id"]:
                return False

        # Check agent_id filter
        if "agent_id" in self.filters and self.filters["agent_id"]:
            event_agent_id = payload.get("agent_id")
            if event_agent_id != self.filters["agent_id"]:
                return False

        return True


@dataclass
class SSEEvent:
    """Represents an SSE event to be broadcast."""

    event_type: str
    data: dict
    event_id: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def format(self) -> str:
        """
        Format the event as an SSE string.

        Returns:
            SSE-formatted event string
        """
        lines = [
            f"event: {self.event_type}",
            f"id: {self.event_id}",
            f"data: {json.dumps(self.data)}",
            "",
            "",  # Double newline to end event
        ]
        return "\n".join(lines)


class Broadcaster:
    """
    Event broadcaster for SSE connections.

    Manages a registry of connected clients and broadcasts events to all
    clients that match the event filters. Thread-safe for concurrent access.
    """

    def __init__(
        self,
        max_connections: int = 100,
        heartbeat_interval: float = 30.0,
        connection_timeout: float = 60.0,
        retry_after: int = 5,
    ) -> None:
        """
        Initialize the broadcaster.

        Args:
            max_connections: Maximum number of concurrent SSE connections
            heartbeat_interval: Seconds between heartbeat messages
            connection_timeout: Seconds before a stale connection is removed
            retry_after: Seconds to suggest in Retry-After header
        """
        self._max_connections = max_connections
        self._heartbeat_interval = heartbeat_interval
        self._connection_timeout = connection_timeout
        self._retry_after = retry_after

        self._clients: dict[str, SSEClient] = {}
        self._clients_lock = threading.Lock()
        self._event_id_counter = 0
        self._event_id_lock = threading.Lock()

        self._running = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        logger.info(
            f"Broadcaster initialized: max_connections={max_connections}, "
            f"heartbeat_interval={heartbeat_interval}s"
        )

    @property
    def active_connections(self) -> int:
        """Get the number of active connections."""
        with self._clients_lock:
            return len(self._clients)

    @property
    def max_connections(self) -> int:
        """Get the maximum allowed connections."""
        return self._max_connections

    @property
    def retry_after(self) -> int:
        """Get the retry-after value for 503 responses."""
        return self._retry_after

    def start(self) -> None:
        """Start the broadcaster and cleanup thread."""
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="sse-cleanup",
        )
        self._cleanup_thread.start()

        logger.info("Broadcaster started")

    def stop(self) -> None:
        """Stop the broadcaster and close all connections."""
        if not self._running:
            return

        logger.info("Broadcaster stopping...")
        self._running = False
        self._shutdown_event.set()

        # Send close notification to all clients
        with self._clients_lock:
            for client in self._clients.values():
                client.is_active = False
                # Put a special close event in the queue
                client.event_queue.put(None)

        # Wait for cleanup thread
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)

        # Clear all clients
        with self._clients_lock:
            self._clients.clear()

        logger.info("Broadcaster stopped")

    def can_accept_connection(self) -> bool:
        """
        Check if the broadcaster can accept a new connection.

        Returns:
            True if under the connection limit
        """
        return self.active_connections < self._max_connections

    def register_client(
        self,
        types: Optional[list[str]] = None,
        project_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Register a new SSE client.

        Args:
            types: Optional list of event types to filter
            project_id: Optional project ID to filter
            agent_id: Optional agent ID to filter

        Returns:
            Client ID if registered successfully, None if at limit
        """
        if not self.can_accept_connection():
            logger.warning(
                f"Connection limit reached ({self._max_connections}), rejecting client"
            )
            return None

        client_id = str(uuid.uuid4())
        filters = {}
        if types:
            filters["types"] = types
        if project_id:
            filters["project_id"] = project_id
        if agent_id:
            filters["agent_id"] = agent_id

        client = SSEClient(
            client_id=client_id,
            connected_at=datetime.now(timezone.utc),
            filters=filters,
        )

        with self._clients_lock:
            self._clients[client_id] = client

        logger.info(f"Client registered: {client_id}, filters={filters}")
        return client_id

    def unregister_client(self, client_id: str) -> bool:
        """
        Unregister an SSE client.

        Args:
            client_id: The client ID to unregister

        Returns:
            True if the client was found and removed
        """
        with self._clients_lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"Client unregistered: {client_id}")
                return True
        return False

    def get_client(self, client_id: str) -> Optional[SSEClient]:
        """
        Get a client by ID.

        Args:
            client_id: The client ID

        Returns:
            The SSEClient or None if not found
        """
        with self._clients_lock:
            return self._clients.get(client_id)

    def _next_event_id(self) -> int:
        """Get the next monotonic event ID."""
        with self._event_id_lock:
            self._event_id_counter += 1
            return self._event_id_counter

    def broadcast(self, event_type: str, data: dict) -> int:
        """
        Broadcast an event to all matching clients.

        Args:
            event_type: The type of event
            data: The event data payload

        Returns:
            Number of clients the event was sent to
        """
        event_id = self._next_event_id()
        event = SSEEvent(event_type=event_type, data=data, event_id=event_id)

        sent_count = 0
        with self._clients_lock:
            for client in self._clients.values():
                if client.is_active and client.matches_filter(event_type, data):
                    client.event_queue.put(event)
                    client.last_event_at = datetime.now(timezone.utc)
                    sent_count += 1

        logger.debug(
            f"Broadcast event: type={event_type}, id={event_id}, sent_to={sent_count}"
        )
        return sent_count

    def broadcast_error(self, error_type: str, message: str) -> int:
        """
        Broadcast an error event to all clients.

        Args:
            error_type: The type of error
            message: Error message

        Returns:
            Number of clients the error was sent to
        """
        return self.broadcast("error", {"error_type": error_type, "message": message})

    def get_next_event(
        self, client_id: str, timeout: float = 30.0
    ) -> Optional[SSEEvent]:
        """
        Get the next event for a client, blocking with timeout.

        Args:
            client_id: The client ID
            timeout: Timeout in seconds

        Returns:
            The next SSEEvent, or None if timeout/shutdown
        """
        client = self.get_client(client_id)
        if not client or not client.is_active:
            return None

        try:
            event = client.event_queue.get(timeout=timeout)
            return event  # May be None for shutdown signal
        except Empty:
            return None

    def mark_failed_write(self, client_id: str) -> None:
        """
        Mark a failed write attempt for a client.

        Args:
            client_id: The client ID
        """
        client = self.get_client(client_id)
        if client:
            client.failed_writes += 1
            logger.warning(
                f"Client {client_id} failed write count: {client.failed_writes}"
            )

    def _cleanup_loop(self) -> None:
        """Background thread that cleans up stale connections."""
        while not self._shutdown_event.is_set():
            try:
                self._cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

            # Sleep in small increments to allow quick shutdown
            for _ in range(int(self._connection_timeout / 5)):
                if self._shutdown_event.is_set():
                    break
                time.sleep(5)

    def _cleanup_stale_connections(self) -> None:
        """Remove stale connections from the registry."""
        now = datetime.now(timezone.utc)
        stale_clients = []

        with self._clients_lock:
            for client_id, client in self._clients.items():
                # Check for too many failed writes
                if client.failed_writes >= 3:
                    stale_clients.append(client_id)
                    continue

                # Check for connection timeout
                if client.last_event_at:
                    idle_time = (now - client.last_event_at).total_seconds()
                else:
                    idle_time = (now - client.connected_at).total_seconds()

                if idle_time > self._connection_timeout:
                    stale_clients.append(client_id)

        # Remove stale clients outside the lock
        for client_id in stale_clients:
            self.unregister_client(client_id)
            logger.info(f"Cleaned up stale connection: {client_id}")

    def get_health_status(self) -> dict[str, Any]:
        """
        Get health status for the broadcaster.

        Returns:
            Dictionary with health information
        """
        return {
            "status": "healthy" if self._running else "stopped",
            "active_connections": self.active_connections,
            "max_connections": self._max_connections,
            "running": self._running,
        }


# Global broadcaster instance
_broadcaster: Optional[Broadcaster] = None
_broadcaster_lock = threading.Lock()


def get_broadcaster() -> Broadcaster:
    """
    Get the global broadcaster instance.

    Returns:
        The global Broadcaster instance
    """
    global _broadcaster
    if _broadcaster is None:
        raise RuntimeError("Broadcaster not initialized. Call init_broadcaster first.")
    return _broadcaster


def init_broadcaster(config: Optional[dict] = None) -> Broadcaster:
    """
    Initialize the global broadcaster instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        The initialized Broadcaster instance
    """
    global _broadcaster

    with _broadcaster_lock:
        if _broadcaster is not None:
            return _broadcaster

        if config is None:
            config = {}

        sse_config = config.get("sse", {})

        _broadcaster = Broadcaster(
            max_connections=sse_config.get("max_connections", 100),
            heartbeat_interval=sse_config.get("heartbeat_interval_seconds", 30),
            connection_timeout=sse_config.get("connection_timeout_seconds", 60),
            retry_after=sse_config.get("retry_after_seconds", 5),
        )
        _broadcaster.start()

        return _broadcaster


def shutdown_broadcaster() -> None:
    """Shutdown the global broadcaster instance."""
    global _broadcaster

    with _broadcaster_lock:
        if _broadcaster is not None:
            _broadcaster.stop()
            _broadcaster = None
