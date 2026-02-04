"""Event broadcaster service for SSE (Server-Sent Events)."""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any, Optional

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
        """Check if an event matches this client's filters."""
        if "types" in self.filters and self.filters["types"]:
            if event_type not in self.filters["types"]:
                return False
        if "project_id" in self.filters and self.filters["project_id"]:
            if payload.get("project_id") != self.filters["project_id"]:
                return False
        if "agent_id" in self.filters and self.filters["agent_id"]:
            if payload.get("agent_id") != self.filters["agent_id"]:
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
        """Format the event as an SSE string."""
        lines = [
            f"event: {self.event_type}",
            f"id: {self.event_id}",
            f"data: {json.dumps(self.data)}",
            "",
            "",
        ]
        return "\n".join(lines)


class Broadcaster:
    """SSE event broadcaster. Thread-safe client registry with filtered delivery."""

    def __init__(
        self,
        max_connections: int = 100,
        heartbeat_interval: float = 30.0,
        connection_timeout: float = 60.0,
        retry_after: int = 5,
    ) -> None:
        self._max_connections = max_connections
        self._heartbeat_interval = heartbeat_interval
        self._connection_timeout = connection_timeout
        self._retry_after = retry_after

        self._clients: dict[str, SSEClient] = {}
        self._lock = threading.Lock()
        self._event_id_counter = 0

        self._running = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        logger.info(
            f"Broadcaster initialized: max_connections={max_connections}, "
            f"heartbeat_interval={heartbeat_interval}s"
        )

    @property
    def active_connections(self) -> int:
        with self._lock:
            return len(self._clients)

    @property
    def max_connections(self) -> int:
        return self._max_connections

    @property
    def retry_after(self) -> int:
        return self._retry_after

    def start(self) -> None:
        """Start the broadcaster and cleanup thread."""
        if self._running:
            return
        self._running = True
        self._shutdown_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="sse-cleanup",
        )
        self._cleanup_thread.start()
        logger.info("Broadcaster started")

    def stop(self) -> None:
        """Stop the broadcaster and close all connections."""
        if not self._running:
            return
        self._running = False
        self._shutdown_event.set()
        with self._lock:
            for client in self._clients.values():
                client.is_active = False
                client.event_queue.put(None)
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
        with self._lock:
            self._clients.clear()
        logger.info("Broadcaster stopped")

    def can_accept_connection(self) -> bool:
        return self.active_connections < self._max_connections

    def register_client(
        self,
        types: Optional[list[str]] = None,
        project_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> Optional[str]:
        """Register a new SSE client. Returns client_id or None if at limit."""
        if not self.can_accept_connection():
            logger.warning(f"Connection limit reached ({self._max_connections})")
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
        with self._lock:
            self._clients[client_id] = client
        logger.info(f"Client registered: {client_id}, filters={filters}")
        return client_id

    def unregister_client(self, client_id: str) -> bool:
        """Remove an SSE client. Returns True if found."""
        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"Client unregistered: {client_id}")
                return True
        return False

    def get_client(self, client_id: str) -> Optional[SSEClient]:
        with self._lock:
            return self._clients.get(client_id)

    def broadcast(self, event_type: str, data: dict) -> int:
        """Broadcast an event to all matching clients. Returns send count."""
        with self._lock:
            self._event_id_counter += 1
            event_id = self._event_id_counter
        event = SSEEvent(event_type=event_type, data=data, event_id=event_id)

        sent_count = 0
        with self._lock:
            for client in self._clients.values():
                if client.is_active and client.matches_filter(event_type, data):
                    client.event_queue.put(event)
                    client.last_event_at = datetime.now(timezone.utc)
                    sent_count += 1

        logger.debug(f"Broadcast: type={event_type}, id={event_id}, sent_to={sent_count}")
        return sent_count

    def get_next_event(self, client_id: str, timeout: float = 30.0) -> Optional[SSEEvent]:
        """Get the next event for a client, blocking with timeout."""
        client = self.get_client(client_id)
        if not client or not client.is_active:
            return None
        try:
            return client.event_queue.get(timeout=timeout)
        except Empty:
            client.last_event_at = datetime.now(timezone.utc)
            return None

    def mark_failed_write(self, client_id: str) -> None:
        client = self.get_client(client_id)
        if client:
            client.failed_writes += 1
            logger.warning(f"Client {client_id} failed write count: {client.failed_writes}")

    def _cleanup_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                self._cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
            for _ in range(int(self._connection_timeout / 5)):
                if self._shutdown_event.is_set():
                    break
                time.sleep(5)

    def _cleanup_stale_connections(self) -> None:
        now = datetime.now(timezone.utc)
        stale_clients = []
        with self._lock:
            for client_id, client in self._clients.items():
                if client.failed_writes >= 3:
                    stale_clients.append(client_id)
                    continue
                last = client.last_event_at or client.connected_at
                if (now - last).total_seconds() > self._connection_timeout:
                    stale_clients.append(client_id)
        for client_id in stale_clients:
            self.unregister_client(client_id)
            logger.info(f"Cleaned up stale connection: {client_id}")

    def get_health_status(self) -> dict[str, Any]:
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
    """Get the global broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        raise RuntimeError("Broadcaster not initialized. Call init_broadcaster first.")
    return _broadcaster


def init_broadcaster(config: Optional[dict] = None) -> Broadcaster:
    """Initialize the global broadcaster instance."""
    global _broadcaster
    with _broadcaster_lock:
        if _broadcaster is not None:
            return _broadcaster
        sse_config = (config or {}).get("sse", {})
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
