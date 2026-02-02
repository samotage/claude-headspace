"""Commander availability tracking with periodic health checks.

Tracks which agents have reachable commander sockets and broadcasts
availability changes via SSE so the dashboard can show/hide the input widget.
"""

import logging
import threading
import time
from datetime import datetime, timezone

from . import commander_service

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_HEALTH_CHECK_INTERVAL = 30  # seconds


class CommanderAvailability:
    """Tracks commander socket availability for active agents.

    Thread-safe in-memory cache with periodic health check loop.
    Broadcasts SSE events when availability changes.
    """

    def __init__(
        self,
        app=None,
        config: dict | None = None,
        health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
    ):
        self._app = app
        self._config = config or {}
        self._lock = threading.Lock()
        # Maps agent_id -> bool (available)
        self._availability: dict[int, bool] = {}
        # Maps agent_id -> session_id (for health checks)
        self._session_ids: dict[int, str] = {}
        self._health_check_interval = health_check_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._socket_prefix = commander_service.DEFAULT_SOCKET_PATH_PREFIX
        self._socket_timeout = commander_service.DEFAULT_SOCKET_TIMEOUT

        # Read config overrides
        commander_config = self._config.get("commander", {})
        if commander_config:
            self._health_check_interval = commander_config.get(
                "health_check_interval", health_check_interval
            )
            self._socket_prefix = commander_config.get(
                "socket_path_prefix", self._socket_prefix
            )
            self._socket_timeout = commander_config.get(
                "socket_timeout", self._socket_timeout
            )

    def start(self) -> None:
        """Start the periodic health check thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._health_check_loop,
            name="commander-availability",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Commander availability checker started "
            f"(interval={self._health_check_interval}s)"
        )

    def stop(self) -> None:
        """Stop the periodic health check thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Commander availability checker stopped")

    def is_available(self, agent_id: int) -> bool:
        """Check if a commander socket is available for an agent.

        Uses the cached value. Call check_agent() to refresh.

        Args:
            agent_id: The agent ID

        Returns:
            True if commander socket is available
        """
        with self._lock:
            return self._availability.get(agent_id, False)

    def register_agent(self, agent_id: int, session_id: str | None) -> None:
        """Register an agent for availability tracking.

        Args:
            agent_id: The agent ID
            session_id: The claude_session_id (may be None)
        """
        with self._lock:
            if session_id:
                self._session_ids[agent_id] = session_id
            elif agent_id in self._session_ids:
                del self._session_ids[agent_id]
                self._availability[agent_id] = False

    def unregister_agent(self, agent_id: int) -> None:
        """Remove an agent from availability tracking.

        Args:
            agent_id: The agent ID
        """
        with self._lock:
            self._session_ids.pop(agent_id, None)
            self._availability.pop(agent_id, None)

    def check_agent(self, agent_id: int, session_id: str | None = None) -> bool:
        """Check and update commander availability for a specific agent.

        Args:
            agent_id: The agent ID
            session_id: Optional session_id override (uses registered value if None)

        Returns:
            True if commander is available
        """
        with self._lock:
            sid = session_id or self._session_ids.get(agent_id)

        if not sid:
            self._update_availability(agent_id, False)
            return False

        # Register if not already tracked
        if session_id:
            self.register_agent(agent_id, session_id)

        health = commander_service.check_health(
            sid, prefix=self._socket_prefix, timeout=self._socket_timeout
        )
        self._update_availability(agent_id, health.available)
        return health.available

    def _update_availability(self, agent_id: int, available: bool) -> None:
        """Update availability and broadcast if changed."""
        with self._lock:
            previous = self._availability.get(agent_id)
            self._availability[agent_id] = available

        if previous is not None and previous != available:
            self._broadcast_change(agent_id, available)

    def _broadcast_change(self, agent_id: int, available: bool) -> None:
        """Broadcast commander availability change via SSE."""
        try:
            from .broadcaster import get_broadcaster

            get_broadcaster().broadcast(
                "commander_availability",
                {
                    "agent_id": agent_id,
                    "available": available,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(
                f"Commander availability changed for agent {agent_id}: {available}"
            )
        except Exception as e:
            logger.debug(f"Commander availability broadcast failed (non-fatal): {e}")

    def _health_check_loop(self) -> None:
        """Periodic health check loop running in background thread."""
        while not self._stop_event.is_set():
            try:
                self._check_all_agents()
            except Exception as e:
                logger.warning(f"Health check loop error (non-fatal): {e}")

            self._stop_event.wait(self._health_check_interval)

    def _check_all_agents(self) -> None:
        """Check health for all registered agents."""
        with self._lock:
            agents_to_check = dict(self._session_ids)

        for agent_id, session_id in agents_to_check.items():
            if self._stop_event.is_set():
                break
            try:
                health = commander_service.check_health(
                    session_id,
                    prefix=self._socket_prefix,
                    timeout=self._socket_timeout,
                )
                self._update_availability(agent_id, health.available)
            except Exception as e:
                logger.debug(
                    f"Health check failed for agent {agent_id} (non-fatal): {e}"
                )
                self._update_availability(agent_id, False)
