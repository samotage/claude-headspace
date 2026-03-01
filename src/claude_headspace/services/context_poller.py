"""Context poller service for periodic context window usage monitoring.

Polls all active agents' tmux panes to read the Claude Code statusline
(e.g. [ctx: 22% used, 155k remaining]) and persists usage data to the
Agent model for at-a-glance display on dashboard cards.

Two data sources (tried in order):
1. Pane capture — parse the visible statusline from the tmux pane
2. Sidecar file — read /tmp/claude_headspace_ctx/<pane_number> written
   by the statusline-command.sh script (fallback for narrow terminals
   where the statusline is truncated)
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone

from flask import Flask

from ..config import get_value
from ..database import db
from ..models.agent import Agent
from . import tmux_bridge
from .advisory_lock import LockNamespace, advisory_lock_or_skip
from .card_state import broadcast_card_refresh
from .context_parser import parse_context_usage

logger = logging.getLogger(__name__)

# Defaults (overridden by config.yaml -> context_monitor section)
DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_WARNING_THRESHOLD = 65
DEFAULT_HIGH_THRESHOLD = 75

# Debounce: skip agents whose context was updated less than this many seconds ago
DEBOUNCE_SECONDS = 15

# Sidecar files written by statusline-command.sh
_SIDECAR_DIR = "/tmp/claude_headspace_ctx"


def _read_sidecar(pane_id: str) -> dict | None:
    """Read context data from the sidecar file for a tmux pane.

    The statusline-command.sh writes JSON files to /tmp/claude_headspace_ctx/<N>
    where N is the tmux pane number (without the % prefix).

    Returns:
        Dict with keys: percent_used (int), remaining_tokens (str)
        None if the file doesn't exist, is stale (>5 min), or is malformed.
    """
    # Strip % prefix from pane_id (e.g., "%56" -> "56")
    pane_num = pane_id.lstrip("%")
    path = os.path.join(_SIDECAR_DIR, pane_num)
    try:
        stat = os.stat(path)
        # Ignore stale files (>5 minutes old)
        age = datetime.now(timezone.utc).timestamp() - stat.st_mtime
        if age > 300:
            return None
        with open(path) as f:
            data = json.load(f)
        pct = data.get("percent_used")
        rem = data.get("remaining_tokens", "")
        if pct is not None and isinstance(pct, (int, float)):
            return {"percent_used": int(pct), "remaining_tokens": str(rem)}
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def _compute_tier(percent_used: int, warning_threshold: int, high_threshold: int) -> str:
    """Compute the context usage tier from a percentage.

    Args:
        percent_used: Context usage percentage (0-100)
        warning_threshold: Threshold for 'warning' tier
        high_threshold: Threshold for 'high' tier

    Returns:
        One of 'normal', 'warning', or 'high'
    """
    if percent_used >= high_threshold:
        return "high"
    if percent_used >= warning_threshold:
        return "warning"
    return "normal"


class ContextPoller:
    """Background service that polls active agents for context window usage.

    Follows the AgentReaper pattern: __init__, start, stop, _poll_loop, poll_once.
    """

    def __init__(self, app: Flask, config: dict) -> None:
        self._app = app
        ctx_config = config.get("context_monitor", {})
        self._enabled = get_value(config, "context_monitor", "enabled", default=True)
        self._interval = ctx_config.get(
            "poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_tiers: dict[int, str] = {}

    def start(self) -> None:
        """Start the context poller background thread."""
        if not self._enabled:
            logger.info("Context poller disabled by config")
            return

        if self._thread and self._thread.is_alive():
            logger.warning("Context poller already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="ContextPoller"
        )
        self._thread.start()
        logger.info(f"Context poller started (interval={self._interval}s)")

    def stop(self) -> None:
        """Stop the poller gracefully."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            self._thread = None
            logger.info("Context poller stopped")

    def _poll_loop(self) -> None:
        """Background loop that calls poll_once at the configured interval."""
        consecutive_failures = 0
        max_backoff = 300  # 5 minutes cap
        while not self._stop_event.is_set():
            try:
                self.poll_once()
                consecutive_failures = 0
            except Exception:
                consecutive_failures += 1
                if consecutive_failures <= 3:
                    logger.exception("Context poller pass failed")
                else:
                    logger.error("Context poller pass failed (repeated, suppressing traceback)")

            backoff = min(self._interval * (2 ** consecutive_failures), max_backoff) if consecutive_failures else self._interval
            self._stop_event.wait(timeout=backoff)

    def poll_once(self) -> int:
        """Run a single polling pass over all active agents.

        Returns:
            Number of agents checked
        """
        checked = 0

        with self._app.app_context():
            # Read config at poll time so threshold changes take effect immediately
            config = self._app.config.get("APP_CONFIG", {})
            ctx_config = config.get("context_monitor", {})
            if not ctx_config.get("enabled", True):
                return 0
            warning_threshold = ctx_config.get("warning_threshold", DEFAULT_WARNING_THRESHOLD)
            high_threshold = ctx_config.get("high_threshold", DEFAULT_HIGH_THRESHOLD)

            agents = (
                db.session.query(Agent)
                .filter(
                    Agent.ended_at.is_(None),
                    Agent.tmux_pane_id.isnot(None),
                )
                .all()
            )

            now = datetime.now(timezone.utc)
            broadcast_agents = []

            for agent in agents:
                checked += 1

                # Debounce: skip if recently updated
                if agent.context_updated_at:
                    elapsed = (now - agent.context_updated_at).total_seconds()
                    if elapsed < DEBOUNCE_SECONDS:
                        continue

                # Non-blocking advisory lock: skip agents currently being
                # processed by hook routes to avoid contention.
                with advisory_lock_or_skip(LockNamespace.AGENT, agent.id) as acquired:
                    if not acquired:
                        logger.debug(
                            f"Context poller: agent {agent.id} locked — skipping"
                        )
                        continue

                    # Capture pane and parse context (with sidecar fallback)
                    ctx = None
                    pane_text = tmux_bridge.capture_pane(agent.tmux_pane_id, lines=5)
                    if pane_text:
                        ctx = parse_context_usage(pane_text)

                    # Fallback: read sidecar file written by statusline-command.sh
                    # (handles narrow terminals where the statusline is truncated)
                    if not ctx:
                        ctx = _read_sidecar(agent.tmux_pane_id)

                    if not ctx:
                        continue

                    # Update agent columns
                    agent.context_percent_used = ctx["percent_used"]
                    agent.context_remaining_tokens = ctx["remaining_tokens"]
                    agent.context_updated_at = now

                    # Check if tier changed
                    new_tier = _compute_tier(
                        ctx["percent_used"], warning_threshold, high_threshold
                    )
                    old_tier = self._last_tiers.get(agent.id)
                    self._last_tiers[agent.id] = new_tier

                    if old_tier is None or old_tier != new_tier:
                        broadcast_agents.append(agent)

                    # Commit inside lock scope so state is visible immediately
                    db.session.commit()

            # Broadcast card_refresh for agents whose tier changed (after commit)
            if broadcast_agents:
                try:
                    for agent in broadcast_agents:
                        broadcast_card_refresh(agent, "context_tier_changed")
                except Exception as e:
                    logger.debug(f"Context poller card_refresh broadcast failed: {e}")

            logger.debug(f"Context poller pass: checked={checked}")

        return checked
