"""Tmux pane watchdog for near-real-time turn gap detection.

Tier 3 of the three-tier reliability model. Periodically captures tmux pane
content, detects new agent output, and triggers reconciliation when no matching
Turn exists in the database after a configurable gap threshold.

This bridges the latency gap between hooks (Tier 1, unreliable) and JSONL
transcript reconciliation (Tier 2, authoritative but 2-10s delayed).
"""

import hashlib
import logging
import threading
from datetime import datetime, timedelta, timezone

from . import tmux_bridge

logger = logging.getLogger(__name__)


class TmuxWatchdog:
    """Near-real-time watchdog that detects missing turns via tmux pane monitoring.

    Runs on a daemon thread, polling registered agents' tmux panes for new
    output. When new output is detected but no matching Turn exists in the
    database after the gap threshold, triggers reconciliation.
    """

    def __init__(self, app=None, config=None):
        self._app = app
        self._config = config or {}
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

        # Per-agent state
        self._pane_ids: dict[int, str] = {}
        self._last_content_hash: dict[int, str] = {}
        self._gap_detected_at: dict[int, datetime] = {}

        # Config
        watchdog_config = self._config.get("headspace", {}).get("tmux_watchdog", {})
        self._poll_interval = watchdog_config.get("poll_interval_seconds", 3)
        self._gap_threshold = watchdog_config.get("gap_threshold_seconds", 5)
        self._capture_lines = watchdog_config.get("capture_lines", 20)

    def start(self):
        """Start the watchdog daemon thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watchdog_loop,
            name="tmux-watchdog",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Tmux watchdog started "
            f"(interval={self._poll_interval}s, threshold={self._gap_threshold}s)"
        )

    def stop(self):
        """Stop the watchdog daemon thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Tmux watchdog stopped")

    def register_agent(self, agent_id: int, tmux_pane_id: str | None):
        """Register an agent for watchdog monitoring.

        Args:
            agent_id: The agent ID
            tmux_pane_id: The tmux pane ID (may be None)
        """
        with self._lock:
            if tmux_pane_id:
                self._pane_ids[agent_id] = tmux_pane_id
            elif agent_id in self._pane_ids:
                del self._pane_ids[agent_id]

    def unregister_agent(self, agent_id: int):
        """Remove an agent from watchdog monitoring.

        Cleans up all per-agent state to prevent memory leaks.

        Args:
            agent_id: The agent ID
        """
        with self._lock:
            self._pane_ids.pop(agent_id, None)
            self._last_content_hash.pop(agent_id, None)
            self._gap_detected_at.pop(agent_id, None)

    def _watchdog_loop(self):
        """Main watchdog loop — runs on daemon thread."""
        while not self._stop_event.wait(self._poll_interval):
            try:
                self._check_all_agents()
            except Exception as e:
                logger.debug(f"[TMUX_WATCHDOG] Loop error: {e}")

    def _check_all_agents(self):
        """Check all registered agents for turn gaps."""
        with self._lock:
            agents_to_check = dict(self._pane_ids)

        for agent_id, pane_id in agents_to_check.items():
            try:
                self._check_agent(agent_id, pane_id)
            except Exception as e:
                logger.debug(
                    f"[TMUX_WATCHDOG] Agent {agent_id} check failed: {e}"
                )

    def _check_agent(self, agent_id: int, pane_id: str):
        """Check a single agent's tmux pane for new output without a matching turn."""
        # Capture pane content
        try:
            content = tmux_bridge.capture_pane(
                pane_id, lines=self._capture_lines, timeout=3
            )
        except Exception:
            logger.debug(
                f"[TMUX_WATCHDOG] Agent {agent_id} tmux capture failed — skipping"
            )
            return

        if not content or not content.strip():
            logger.debug(f"[TMUX_WATCHDOG] Agent {agent_id} pane content empty")
            return

        # Hash-based change detection
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        with self._lock:
            last_hash = self._last_content_hash.get(agent_id)
            self._last_content_hash[agent_id] = content_hash

        if content_hash == last_hash:
            logger.debug(f"[TMUX_WATCHDOG] Agent {agent_id} pane content unchanged")
            return

        # New output detected — check for matching turn in DB
        now = datetime.now(timezone.utc)
        has_match = self._check_recent_turn_match(agent_id, content)

        if has_match:
            # Turn exists — clear any gap tracker
            with self._lock:
                self._gap_detected_at.pop(agent_id, None)
            return

        # No matching turn — track gap
        with self._lock:
            if agent_id not in self._gap_detected_at:
                self._gap_detected_at[agent_id] = now
                return  # Wait for threshold before triggering

            gap_start = self._gap_detected_at[agent_id]
            gap_seconds = (now - gap_start).total_seconds()

        if gap_seconds < self._gap_threshold:
            return  # Not yet past threshold

        # Gap persisted past threshold — trigger reconciliation
        logger.info(
            f"[TMUX_WATCHDOG] Gap detected for agent {agent_id} — "
            f"new output in pane {pane_id} with no matching turn after "
            f"{gap_seconds:.1f}s, triggering reconciliation"
        )

        with self._lock:
            self._gap_detected_at.pop(agent_id, None)

        self._trigger_reconciliation(agent_id)

    def _check_recent_turn_match(self, agent_id: int, pane_content: str) -> bool:
        """Check if any recent Turn matches the new pane content.

        Uses a simple overlap check: extract the last few non-empty lines
        from the pane and check if any recent Turn's text contains them.
        """
        try:
            with self._app.app_context():
                from ..database import db
                from ..models.turn import Turn, TurnActor

                cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
                recent_turns = (
                    Turn.query
                    .join(Turn.task)
                    .filter(
                        Turn.actor == TurnActor.AGENT,
                        Turn.timestamp >= cutoff,
                    )
                    .all()
                )

                # Filter to turns belonging to this agent
                agent_turns = [
                    t for t in recent_turns
                    if t.task and t.task.agent_id == agent_id
                ]

                if not agent_turns:
                    return False

                # Extract representative lines from pane content
                lines = [l.strip() for l in pane_content.strip().splitlines() if l.strip()]
                if not lines:
                    return False

                # Check last 3 non-empty lines for overlap
                check_lines = lines[-3:]
                for turn in agent_turns:
                    if not turn.text:
                        continue
                    for line in check_lines:
                        if len(line) > 20 and line in turn.text:
                            return True

                return False
        except Exception as e:
            logger.debug(f"[TMUX_WATCHDOG] Turn match check failed: {e}")
            return False

    def _trigger_reconciliation(self, agent_id: int):
        """Trigger reconciliation for an agent via the per-agent lock."""
        try:
            with self._app.app_context():
                from ..database import db
                from ..models.agent import Agent
                from .transcript_reconciler import (
                    broadcast_reconciliation,
                    get_reconcile_lock,
                    reconcile_agent_session,
                )

                lock = get_reconcile_lock(agent_id)
                if not lock.acquire(blocking=False):
                    logger.debug(
                        f"[TMUX_WATCHDOG] Agent {agent_id} reconciliation "
                        f"already in progress — skipping"
                    )
                    return

                try:
                    agent = db.session.get(Agent, agent_id)
                    if not agent:
                        return

                    result = reconcile_agent_session(agent)
                    if result["created"]:
                        try:
                            broadcast_reconciliation(agent, result)
                        except Exception as e:
                            logger.warning(
                                f"[TMUX_WATCHDOG] Broadcast failed for agent "
                                f"{agent_id}: {e}"
                            )
                        db.session.commit()
                        logger.info(
                            f"[TMUX_WATCHDOG] Reconciliation for agent {agent_id} "
                            f"created {len(result['created'])} turn(s)"
                        )
                finally:
                    lock.release()
        except Exception as e:
            logger.debug(f"[TMUX_WATCHDOG] Reconciliation failed for agent {agent_id}: {e}")
