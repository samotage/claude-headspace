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

    Returns:
        True if claude is running, False if pane exists but no claude,
        None if we can't determine (pane doesn't exist or error).
    """
    import subprocess

    try:
        # Get the pane's root PID from tmux
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{pane_pid}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        pane_pid = None
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) == 2 and parts[0] == tmux_pane_id:
                pane_pid = parts[1]
                break

        if not pane_pid:
            return None  # Pane doesn't exist in tmux

        # Use `ps` to walk the process tree — macOS `pgrep -P` is unreliable
        # without specific flags, and pgrep -la shows argv[0] (version number
        # like "2.1.34") instead of the actual process name "claude".
        #
        # `ps -axo pid,ppid,comm` reliably shows all processes with their
        # parent PID and real command name on macOS.
        ps_result = subprocess.run(
            ["ps", "-axo", "pid,ppid,comm"],
            capture_output=True, text=True, timeout=5,
        )
        if ps_result.returncode != 0:
            return None

        # Build parent→children map for pane_pid and its children
        children: dict[str, list[tuple[str, str]]] = {}  # ppid → [(pid, comm)]
        for line in ps_result.stdout.strip().split("\n")[1:]:  # skip header
            parts = line.split(None, 2)
            if len(parts) >= 3:
                pid, ppid, comm = parts[0], parts[1], parts[2]
                children.setdefault(ppid, []).append((pid, comm))

        # Check direct children
        for child_pid, child_comm in children.get(pane_pid, []):
            if "claude" in child_comm.lower():
                return True
            # Check grandchildren (bridge → claude)
            for gc_pid, gc_comm in children.get(child_pid, []):
                if "claude" in gc_comm.lower():
                    return True

        # Pane exists (we found it in tmux) but no claude in process tree
        return False  # Pane exists but no claude process found in tree
    except Exception:
        return None


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

                # --- Primary liveness: tmux process tree ---
                # When the agent has a tmux pane, check if `claude` is
                # actually running.  This is the definitive signal —
                # iTerm AppleScript is unreliable and commander can't
                # distinguish Claude Code from the bridge launcher.
                if agent.tmux_pane_id:
                    claude_alive = _is_claude_running_in_pane(agent.tmux_pane_id)
                    if claude_alive is True:
                        result.skipped_alive += 1
                        continue
                    elif claude_alive is False:
                        # Pane exists but Claude Code has exited
                        # (bridge launcher still running)
                        reap_reason = "claude_exited"

                # --- Fallback: iTerm pane check + inactivity ---
                if reap_reason is None and agent.iterm_pane_id:
                    status = check_pane_exists(agent.iterm_pane_id)

                    if status == PaneStatus.FOUND:
                        pane_key = (agent.iterm_pane_id, agent.tmux_pane_id)
                        if pane_owners.get(pane_key) != agent.id:
                            reap_reason = "stale_pane"
                        else:
                            # iTerm says pane exists — trust it
                            result.skipped_alive += 1
                            continue
                    elif status == PaneStatus.NOT_FOUND:
                        reap_reason = "pane_not_found"
                    elif status == PaneStatus.ITERM_NOT_RUNNING:
                        # Can't verify via iTerm — fall through to inactivity
                        if agent.last_seen_at is None or agent.last_seen_at < inactivity_cutoff:
                            reap_reason = "inactivity_timeout"
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
                        from .hook_receiver import _execute_pending_summarisations
                        _execute_pending_summarisations(self._pending_summarisations)
                    except Exception as e:
                        logger.debug(f"Reaper summarisation failed (non-fatal): {e}")
                    finally:
                        self._pending_summarisations = []

        return result

    def _reap_agent(self, agent, reason: str, now: datetime) -> None:
        """Mark an agent as ended, complete orphaned tasks, and broadcast."""
        from ..database import db

        agent.ended_at = now
        agent.last_seen_at = now

        logger.info(
            f"Reaped agent {agent.id} ({agent.session_uuid}): {reason}"
        )

        # Complete any orphaned tasks (PROCESSING, COMMANDED, AWAITING_INPUT)
        self._complete_orphaned_tasks(agent)

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

    def _complete_orphaned_tasks(self, agent) -> None:
        """Complete non-COMPLETE tasks for a reaped agent.

        Reads the agent's transcript, detects intent, and transitions
        each orphaned task to COMPLETE via TaskLifecycleManager.
        """
        from ..database import db
        from ..models.task import Task, TaskState
        from ..models.turn import TurnIntent

        try:
            active_tasks = (
                db.session.query(Task)
                .filter(
                    Task.agent_id == agent.id,
                    Task.state.notin_([TaskState.COMPLETE, TaskState.IDLE]),
                )
                .order_by(Task.id.desc())
                .all()
            )

            if not active_tasks:
                return

            logger.info(
                f"Reaper completing {len(active_tasks)} orphaned task(s) "
                f"for agent {agent.id}"
            )

            # Read transcript once
            from .hook_receiver import _extract_transcript_content
            transcript_text = _extract_transcript_content(agent)

            # Detect intent from transcript
            intent = TurnIntent.COMPLETION
            if transcript_text:
                try:
                    from .intent_detector import detect_agent_intent
                    result = detect_agent_intent(transcript_text)
                    if result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_TASK):
                        intent = result.intent
                except Exception as e:
                    logger.debug(f"Intent detection failed for agent {agent.id}: {e}")

            # Complete tasks via lifecycle manager
            from .hook_receiver import _get_lifecycle_manager
            try:
                lifecycle = _get_lifecycle_manager()
            except Exception as e:
                logger.warning(f"Could not create lifecycle manager: {e}")
                return

            for i, task in enumerate(active_tasks):
                try:
                    # Most recent task (i==0) gets transcript text; older ones get empty
                    text = transcript_text if i == 0 else ""
                    lifecycle.complete_task(
                        task=task,
                        trigger="reaper:orphaned_task",
                        agent_text=text,
                        intent=intent,
                    )
                    logger.info(
                        f"Reaper completed task {task.id} (state was {task.state.value})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to complete orphaned task {task.id}: {e}"
                    )

            # Collect pending summarisations for post-commit execution
            pending = lifecycle.get_pending_summarisations()
            if pending:
                self._pending_summarisations.extend(pending)

        except Exception as e:
            logger.warning(f"Orphaned task completion failed for agent {agent.id}: {e}")
