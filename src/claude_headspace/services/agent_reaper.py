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


def _is_claude_running_in_pane(tmux_pane_id: str) -> bool | None:
    """Check if a `claude` process is running in a tmux pane's process tree.

    Delegates to tmux_bridge.check_health with PROCESS_TREE level.

    Returns:
        True if claude is running, False if pane exists but no claude,
        None if we can't determine (pane doesn't exist or error).
    """
    from . import tmux_bridge
    from .tmux_bridge import HealthCheckLevel

    health = tmux_bridge.check_health(
        tmux_pane_id,
        level=HealthCheckLevel.PROCESS_TREE,
    )

    if not health.available:
        return None  # Pane doesn't exist or error
    return health.running


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
        self._pending_summarisations: list = []

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
        consecutive_failures = 0
        max_backoff = 300  # 5 minutes cap
        while not self._stop_event.is_set():
            try:
                result = self.reap_once()
                consecutive_failures = 0
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
                consecutive_failures += 1
                if consecutive_failures <= 3:
                    logger.exception("Reaper pass failed")
                else:
                    logger.error("Reaper pass failed (repeated, suppressing traceback)")

            backoff = min(self._interval * (2 ** consecutive_failures), max_backoff) if consecutive_failures else self._interval
            self._stop_event.wait(timeout=backoff)

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

            # Build pane ownership: pane_key → newest agent.id (highest id = most recent).
            # Design: When multiple agents share a pane, only the newest (highest ID) is
            # the legitimate owner. Older agents in the same pane are stale remnants from
            # previous sessions that reused the pane, and will be reaped with reason
            # "stale_pane". This is by-design — a tmux pane can only run one Claude Code
            # session at a time, so the newest agent is always the current one.
            pane_owners: dict[tuple[str, str | None], int] = {}
            for a in agents:
                if a.iterm_pane_id:
                    key = (a.iterm_pane_id, a.tmux_pane_id)
                    if key not in pane_owners or a.id > pane_owners[key]:
                        pane_owners[key] = a.id

            for agent in agents:
                result.checked += 1
                age_seconds = (now - agent.started_at).total_seconds() if agent.started_at else None
                last_seen_ago = (now - agent.last_seen_at).total_seconds() if agent.last_seen_at else None

                # Grace period: skip recently created agents
                if agent.started_at > grace_cutoff:
                    result.skipped_grace += 1
                    logger.debug(
                        f"REAPER_CHECK agent_id={agent.id} uuid={agent.session_uuid} "
                        f"-> SKIP (grace period, age={age_seconds:.0f}s < {self._grace_period}s)"
                    )
                    continue

                reap_reason = None

                # --- Primary liveness: tmux process tree ---
                # When the agent has a tmux pane, check if `claude` is
                # actually running.  This is the definitive signal —
                # iTerm AppleScript is unreliable and commander can't
                # distinguish Claude Code from the bridge launcher.
                if agent.tmux_pane_id:
                    claude_alive = _is_claude_running_in_pane(agent.tmux_pane_id)
                    logger.info(
                        f"REAPER_CHECK agent_id={agent.id} uuid={agent.session_uuid} "
                        f"tmux_pane={agent.tmux_pane_id} claude_alive={claude_alive} "
                        f"age={age_seconds:.0f}s last_seen_ago={last_seen_ago:.0f}s"
                    )
                    if claude_alive is True:
                        result.skipped_alive += 1
                        continue
                    elif claude_alive is False:
                        # Pane exists but Claude Code has exited
                        # (bridge launcher still running)
                        reap_reason = "claude_exited"
                        logger.warning(
                            f"REAPER_KILL agent_id={agent.id} uuid={agent.session_uuid} "
                            f"reason=claude_exited tmux_pane={agent.tmux_pane_id} "
                            f"age={age_seconds:.0f}s last_seen_ago={last_seen_ago:.0f}s"
                        )
                else:
                    logger.info(
                        f"REAPER_CHECK agent_id={agent.id} uuid={agent.session_uuid} "
                        f"NO tmux_pane, iterm_pane={agent.iterm_pane_id} "
                        f"age={age_seconds:.0f}s last_seen_ago={last_seen_ago:.0f}s"
                    )

                # --- Fallback: iTerm pane check + inactivity ---
                if reap_reason is None and agent.iterm_pane_id:
                    status = check_pane_exists(agent.iterm_pane_id)
                    logger.info(
                        f"REAPER_ITERM agent_id={agent.id} iterm_pane={agent.iterm_pane_id} "
                        f"status={status}"
                    )

                    if status == PaneStatus.FOUND:
                        pane_key = (agent.iterm_pane_id, agent.tmux_pane_id)
                        if pane_owners.get(pane_key) != agent.id:
                            reap_reason = "stale_pane"
                            logger.warning(
                                f"REAPER_KILL agent_id={agent.id} uuid={agent.session_uuid} "
                                f"reason=stale_pane (owner={pane_owners.get(pane_key)}, this={agent.id})"
                            )
                        else:
                            # iTerm says pane exists — trust it
                            result.skipped_alive += 1
                            continue
                    elif status == PaneStatus.NOT_FOUND:
                        reap_reason = "pane_not_found"
                        logger.warning(
                            f"REAPER_KILL agent_id={agent.id} uuid={agent.session_uuid} "
                            f"reason=pane_not_found iterm_pane={agent.iterm_pane_id}"
                        )
                    elif status == PaneStatus.ITERM_NOT_RUNNING:
                        # Can't verify via iTerm — fall through to inactivity
                        if agent.last_seen_at is None or agent.last_seen_at < inactivity_cutoff:
                            reap_reason = "inactivity_timeout"
                            logger.warning(
                                f"REAPER_KILL agent_id={agent.id} uuid={agent.session_uuid} "
                                f"reason=inactivity_timeout (iterm_not_running) "
                                f"last_seen_ago={last_seen_ago}s timeout={self._inactivity_timeout}s"
                            )
                        else:
                            result.skipped_alive += 1
                            continue
                    else:
                        result.skipped_error += 1
                        continue

                # --- No pane info at all: inactivity only ---
                if reap_reason is None:
                    if agent.last_seen_at is None or agent.last_seen_at < inactivity_cutoff:
                        reap_reason = "inactivity_timeout"
                        logger.warning(
                            f"REAPER_KILL agent_id={agent.id} uuid={agent.session_uuid} "
                            f"reason=inactivity_timeout (no pane info) "
                            f"last_seen_ago={last_seen_ago}s timeout={self._inactivity_timeout}s"
                        )
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

                # Execute pending summarisations (after commit)
                if self._pending_summarisations:
                    try:
                        summarisation_svc = self._app.extensions.get("summarisation_service")
                        if summarisation_svc:
                            from ..database import db as _db
                            summarisation_svc.execute_pending(self._pending_summarisations, _db.session)
                    except Exception as e:
                        logger.debug(f"Reaper summarisation failed (non-fatal): {e}")
                    finally:
                        self._pending_summarisations = []

        return result

    def _reap_agent(self, agent, reason: str, now: datetime) -> None:
        """Mark an agent as ended, complete orphaned commands, and broadcast."""
        from ..database import db

        agent.ended_at = now
        agent.last_seen_at = now

        age_seconds = (now - agent.started_at).total_seconds() if agent.started_at else None
        logger.warning(
            f"REAPER_EXECUTING_KILL: agent_id={agent.id} uuid={agent.session_uuid} "
            f"reason={reason} tmux_pane={agent.tmux_pane_id} iterm_pane={agent.iterm_pane_id} "
            f"project={agent.project.name if agent.project else 'N/A'} "
            f"age={age_seconds:.0f}s"
        )

        # Centralized cache cleanup (correlator, hook_agent_state, commander, watchdog)
        try:
            from .session_correlator import invalidate_agent_caches
            invalidate_agent_caches(
                agent.id,
                session_id=agent.claude_session_id if hasattr(agent, 'claude_session_id') else None,
            )
        except Exception as e:
            logger.debug(f"Reaper cache cleanup failed (non-fatal): {e}")
        try:
            watchdog = self._app.extensions.get("tmux_watchdog")
            if watchdog:
                watchdog.unregister_agent(agent.id)
        except Exception:
            pass

        # Complete any orphaned commands (PROCESSING, COMMANDED, AWAITING_INPUT)
        self._complete_orphaned_commands(agent)

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

    def _complete_orphaned_commands(self, agent) -> None:
        """Complete non-COMPLETE commands for a reaped agent.

        Reads the agent's transcript, detects intent, and transitions
        each orphaned command to COMPLETE via CommandLifecycleManager.
        """
        from ..database import db
        from ..models.command import Command, CommandState
        from ..models.turn import TurnIntent

        try:
            active_commands = (
                db.session.query(Command)
                .filter(
                    Command.agent_id == agent.id,
                    Command.state.notin_([CommandState.COMPLETE, CommandState.IDLE]),
                )
                .order_by(Command.id.desc())
                .all()
            )

            if not active_commands:
                return

            logger.info(
                f"Reaper completing {len(active_commands)} orphaned command(s) "
                f"for agent {agent.id}"
            )

            # Read transcript once
            transcript_text = ""
            if agent.transcript_path:
                try:
                    from .transcript_reader import read_transcript_file
                    result = read_transcript_file(agent.transcript_path)
                    if result.success and result.text:
                        transcript_text = result.text
                except Exception as e:
                    logger.warning(f"Transcript extraction failed for agent {agent.id}: {e}")

            # Detect intent from transcript
            intent = TurnIntent.COMPLETION
            if transcript_text:
                try:
                    from .intent_detector import detect_agent_intent
                    result = detect_agent_intent(transcript_text)
                    if result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND):
                        intent = result.intent
                except Exception as e:
                    logger.debug(f"Intent detection failed for agent {agent.id}: {e}")

            # Complete commands via lifecycle manager
            from .command_lifecycle import CommandLifecycleManager
            try:
                event_writer = self._app.extensions.get("event_writer")
                lifecycle = CommandLifecycleManager(
                    session=db.session,
                    event_writer=event_writer,
                )
            except Exception as e:
                logger.warning(f"Could not create lifecycle manager: {e}")
                return

            for i, cmd in enumerate(active_commands):
                try:
                    # Most recent command (i==0) gets transcript text; older ones get empty
                    text = transcript_text if i == 0 else ""
                    lifecycle.complete_command(
                        command=cmd,
                        trigger="reaper:orphaned_command",
                        agent_text=text,
                        intent=intent,
                    )
                    logger.info(
                        f"Reaper completed command {cmd.id} (state was {cmd.state.value})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to complete orphaned command {cmd.id}: {e}"
                    )

            # Collect pending summarisations for post-commit execution
            pending = lifecycle.get_pending_summarisations()
            if pending:
                self._pending_summarisations.extend(pending)

        except Exception as e:
            logger.warning(f"Orphaned command completion failed for agent {agent.id}: {e}")
