"""Commander availability tracking with periodic health checks.

Tracks which agents have reachable tmux panes and broadcasts
availability changes via SSE so the dashboard can show/hide the input widget.
"""

import logging
import threading
from datetime import datetime, timezone

from . import tmux_bridge

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_HEALTH_CHECK_INTERVAL = 30  # seconds


class CommanderAvailability:
    """Tracks tmux pane availability for active agents.

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
        # Maps agent_id -> tmux_pane_id (for health checks)
        self._pane_ids: dict[int, str] = {}
        self._health_check_interval = health_check_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._subprocess_timeout = tmux_bridge.DEFAULT_SUBPROCESS_TIMEOUT

        # Read config overrides
        bridge_config = self._config.get("tmux_bridge", {})
        if bridge_config:
            self._health_check_interval = bridge_config.get(
                "health_check_interval", health_check_interval
            )
            self._subprocess_timeout = bridge_config.get(
                "subprocess_timeout", self._subprocess_timeout
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
        """Check if a tmux pane is available for an agent.

        Uses the cached value. Call check_agent() to refresh.

        Args:
            agent_id: The agent ID

        Returns:
            True if tmux pane is available
        """
        with self._lock:
            return self._availability.get(agent_id, False)

    def register_agent(self, agent_id: int, tmux_pane_id: str | None) -> None:
        """Register an agent for availability tracking.

        Args:
            agent_id: The agent ID
            tmux_pane_id: The tmux pane ID (may be None)
        """
        with self._lock:
            if tmux_pane_id:
                self._pane_ids[agent_id] = tmux_pane_id
            elif agent_id in self._pane_ids:
                del self._pane_ids[agent_id]
                self._availability[agent_id] = False

    def unregister_agent(self, agent_id: int) -> None:
        """Remove an agent from availability tracking.

        Args:
            agent_id: The agent ID
        """
        with self._lock:
            self._pane_ids.pop(agent_id, None)
            self._availability.pop(agent_id, None)

    def check_agent(self, agent_id: int, tmux_pane_id: str | None = None) -> bool:
        """Check and update tmux pane availability for a specific agent.

        Args:
            agent_id: The agent ID
            tmux_pane_id: Optional pane_id override (uses registered value if None)

        Returns:
            True if tmux pane is available
        """
        with self._lock:
            pid = tmux_pane_id or self._pane_ids.get(agent_id)

        if not pid:
            self._update_availability(agent_id, False)
            return False

        # Register if not already tracked
        if tmux_pane_id:
            self.register_agent(agent_id, tmux_pane_id)

        health = tmux_bridge.check_health(
            pid, timeout=self._subprocess_timeout
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
            agents_to_check = dict(self._pane_ids)

        for agent_id, pane_id in agents_to_check.items():
            if self._stop_event.is_set():
                break
            try:
                health = tmux_bridge.check_health(
                    pane_id,
                    timeout=self._subprocess_timeout,
                )
                self._update_availability(agent_id, health.available)
            except Exception as e:
                logger.debug(
                    f"Health check failed for agent {agent_id} (non-fatal): {e}"
                )
                self._update_availability(agent_id, False)
