"""Agent reaper service for cleaning up dead agents.

Periodically checks if agents are still alive by verifying iTerm pane
existence and/or checking for inactivity timeouts. Dead agents are marked
as ended and removed from the dashboard via SSE broadcast.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from flask import Flask

from ..config import get_value

logger = logging.getLogger(__name__)

# Defaults (overridden by config.yaml → reaper section)
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_INACTIVITY_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_GRACE_PERIOD_SECONDS = 300  # 5 minutes


@dataclass
class ReapDetail:
    """Details about a single reaped agent."""

    agent_id: int
    session_uuid: str
    reason: str  # "pane_not_found", "inactivity_timeout", or "stale_pane"


@dataclass
class ReapResult:
    """Result of a single reaper pass."""

    checked: int = 0
    reaped: int = 0
    skipped_grace: int = 0
    skipped_alive: int = 0
    skipped_error: int = 0
    details: list[ReapDetail] = field(default_factory=list)


class AgentReaper:
    """Background service that detects and cleans up dead agents.

    Two strategies:
    1. iTerm pane check — for agents with iterm_pane_id, silently verify the
       pane still exists in iTerm. If not found → reap.
    2. Inactivity timeout — for agents without a pane ID (or when iTerm is not
       running), reap if last_seen_at exceeds the configured threshold.
    """

    def __init__(self, app: Flask, config: dict) -> None:
        self._app = app
        reaper_config = config.get("reaper", {})
        self._enabled = get_value(config, "reaper", "enabled", default=True)
        self._interval = reaper_config.get(
            "interval_seconds", DEFAULT_INTERVAL_SECONDS
        )
        self._inactivity_timeout = reaper_config.get(
            "inactivity_timeout_seconds", DEFAULT_INACTIVITY_TIMEOUT_SECONDS
        )
        self._grace_period = reaper_config.get(
            "grace_period_seconds", DEFAULT_GRACE_PERIOD_SECONDS
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the reaper background thread."""
        if not self._enabled:
            logger.info("Agent reaper disabled by config")
            return

        if self._thread and self._thread.is_alive():
            logger.warning("Agent reaper already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._reap_loop, daemon=True, name="AgentReaper"
        )
        self._thread.start()
        logger.info(
            f"Agent reaper started (interval={self._interval}s, "
            f"inactivity_timeout={self._inactivity_timeout}s, "
            f"grace_period={self._grace_period}s)"
        )

    def stop(self) -> None:
        """Stop the reaper gracefully."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            self._thread = None
            logger.info("Agent reaper stopped")

    def _reap_loop(self) -> None:
        """Background loop that calls reap_once at the configured interval."""
        while not self._stop_event.is_set():
            try:
                result = self.reap_once()
                if result.reaped > 0:
                    logger.info(
                        f"Reaper pass: checked={result.checked}, "
                        f"reaped={result.reaped}, "
                        f"details={[d.reason for d in result.details]}"
                    )
                else:
                    logger.debug(
                        f"Reaper pass: checked={result.checked}, "
                        f"reaped=0"
                    )
            except Exception:
                logger.exception("Reaper pass failed")

            self._stop_event.wait(timeout=self._interval)

    def reap_once(self) -> ReapResult:
        """Run a single reaper pass. Safe to call from any context.

        Queries all agents with ended_at IS NULL, checks liveness,
        and marks dead agents as ended.

        Returns:
            ReapResult with statistics about the pass.
        """
        from .iterm_focus import PaneStatus, check_pane_exists

        result = ReapResult()
        now = datetime.now(timezone.utc)
        grace_cutoff = now - timedelta(seconds=self._grace_period)
        inactivity_cutoff = now - timedelta(seconds=self._inactivity_timeout)

        with self._app.app_context():
            from ..database import db
            from ..models.agent import Agent

            agents = (
                db.session.query(Agent)
                .filter(Agent.ended_at.is_(None))
                .all()
            )

            # Build pane ownership: pane_key → newest agent.id (highest id = most recent)
            # Use (iterm_pane_id, tmux_pane_id) as key so agents in different
            # tmux panes within the same iTerm window are treated as separate owners.
            pane_owners: dict[tuple[str, str | None], int] = {}
            for a in agents:
                if a.iterm_pane_id:
                    key = (a.iterm_pane_id, a.tmux_pane_id)
                    if key not in pane_owners or a.id > pane_owners[key]:
                        pane_owners[key] = a.id

            for agent in agents:
                result.checked += 1

                # Grace period: skip recently created agents
                if agent.started_at > grace_cutoff:
                    result.skipped_grace += 1
                    continue

                reap_reason = None

                if agent.iterm_pane_id:
                    status = check_pane_exists(agent.iterm_pane_id)

                    if status == PaneStatus.FOUND:
                        # Pane exists — but does this agent own it?
                        pane_key = (agent.iterm_pane_id, agent.tmux_pane_id)
                        if pane_owners.get(pane_key) != agent.id:
                            reap_reason = "stale_pane"
                        else:
                            result.skipped_alive += 1
                            continue
                    elif status == PaneStatus.NOT_FOUND:
                        reap_reason = "pane_not_found"
                    elif status == PaneStatus.ITERM_NOT_RUNNING:
                        # Can't verify via iTerm — fall through to inactivity
                        if agent.last_seen_at is None or agent.last_seen_at < inactivity_cutoff:
                            # Before reaping, check if tmux bridge is alive
                            if agent.tmux_pane_id:
                                try:
                                    commander = self._app.extensions.get("commander_availability")
                                    if commander and commander.check_agent(agent.id, agent.tmux_pane_id):
                                        agent.last_seen_at = now
                                        result.skipped_alive += 1
                                        logger.debug(
                                            f"Skipped reap for agent {agent.id}: bridge_alive"
                                        )
                                        continue
                                except Exception:
                                    logger.debug(f"Commander check failed for agent {agent.id}, proceeding with reap")
                            reap_reason = "inactivity_timeout"
                        else:
                            result.skipped_alive += 1
                            continue
                    else:
                        # ERROR — don't reap on uncertainty
                        result.skipped_error += 1
                        continue
                else:
                    # No pane ID — can only use inactivity timeout
                    if agent.last_seen_at is None or agent.last_seen_at < inactivity_cutoff:
                        # Before reaping, check if tmux bridge is alive
                        if agent.tmux_pane_id:
                            try:
                                commander = self._app.extensions.get("commander_availability")
                                if commander and commander.check_agent(agent.id, agent.tmux_pane_id):
                                    agent.last_seen_at = now
                                    result.skipped_alive += 1
                                    logger.debug(
                                        f"Skipped reap for agent {agent.id}: bridge_alive"
                                    )
                                    continue
                            except Exception:
                                logger.debug(f"Commander check failed for agent {agent.id}, proceeding with reap")
                        reap_reason = "inactivity_timeout"
                    else:
                        result.skipped_alive += 1
                        continue

                # Reap the agent
                self._reap_agent(agent, reap_reason, now)
                result.reaped += 1
                result.details.append(ReapDetail(
                    agent_id=agent.id,
                    session_uuid=str(agent.session_uuid),
                    reason=reap_reason,
                ))

            if result.reaped > 0:
                db.session.commit()
                # Broadcast card_refresh for each reaped agent (after commit)
                try:
                    from .card_state import broadcast_card_refresh

                    for detail in result.details:
                        agent_obj = db.session.get(Agent, detail.agent_id)
                        if agent_obj:
                            broadcast_card_refresh(agent_obj, f"reaper_{detail.reason}")
                except Exception as e:
                    logger.debug(f"Reaper card_refresh broadcast failed (non-fatal): {e}")

        return result

    def _reap_agent(self, agent, reason: str, now: datetime) -> None:
        """Mark an agent as ended and broadcast the event."""
        from ..database import db

        agent.ended_at = now
        agent.last_seen_at = now

        logger.info(
            f"Reaped agent {agent.id} ({agent.session_uuid}): {reason}"
        )

        # Broadcast session_ended so the dashboard removes the card
        try:
            from .broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            broadcaster.broadcast("session_ended", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "session_uuid": str(agent.session_uuid),
                "reason": f"reaper:{reason}",
                "timestamp": now.isoformat(),
            })
        except Exception as e:
            logger.debug(f"Reaper broadcast failed (non-fatal): {e}")

        # Log via event writer if available
        try:
            event_writer = self._app.extensions.get("event_writer")
            if event_writer:
                event_writer.write_event(
                    event_type="reaper_ended",
                    payload={
                        "session_uuid": str(agent.session_uuid),
                        "reason": reason,
                    },
                    agent_id=agent.id,
                    project_id=agent.project_id,
                )
        except Exception as e:
            logger.debug(f"Reaper event write failed (non-fatal): {e}")
