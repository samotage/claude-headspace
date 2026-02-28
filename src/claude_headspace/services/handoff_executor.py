"""Handoff execution service.

Orchestrates the full handoff lifecycle: validate preconditions, instruct the
outgoing agent to write a handoff document, verify the file, create a Handoff
DB record, create a successor with the same persona, and deliver the handoff
injection prompt after skill injection.

The outgoing agent is NOT shut down — it remains alive after writing the
handoff document. The successor receives persona skill injection followed
by the handoff context via tmux bridge.

Two completion paths exist:
1. Background polling thread detects the handoff file (primary path).
2. Stop hook fires while handoff is in progress (fallback — agent chose to
   /exit on its own).
Both paths call complete_handoff(), which is idempotent.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from flask import current_app

from ..database import db
from ..models.agent import Agent
from ..models.handoff import Handoff

logger = logging.getLogger(__name__)

# In-memory tracking of agents with handoff in progress.
# Maps agent_id -> handoff metadata dict.
_handoff_in_progress: dict[int, dict] = {}
_handoff_lock = threading.Lock()

# Polling configuration
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300  # 5 minutes


class HandoffResult(NamedTuple):
    """Result of a handoff operation."""

    success: bool
    message: str
    error_code: str | None = None


class HandoffExecutor:
    """Orchestrates the full agent handoff lifecycle."""

    def __init__(self, app):
        self.app = app

    # ── Precondition validation ──────────────────────────────────────

    def validate_preconditions(self, agent_id: int) -> HandoffResult:
        """Validate that an agent is eligible for handoff.

        Checks: agent exists, is active, has a persona, has a tmux pane,
        and does not already have a Handoff DB record.
        """
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return HandoffResult(
                success=False, message="Agent not found", error_code="not_found"
            )

        if agent.ended_at is not None:
            return HandoffResult(
                success=False, message="Agent is not active", error_code="not_active"
            )

        if not agent.persona_id:
            return HandoffResult(
                success=False, message="Agent has no persona", error_code="no_persona"
            )

        if not agent.tmux_pane_id:
            return HandoffResult(
                success=False,
                message="Agent has no tmux pane",
                error_code="no_tmux_pane",
            )

        # Check for existing handoff record
        existing = Handoff.query.filter_by(agent_id=agent_id).first()
        if existing:
            return HandoffResult(
                success=False,
                message="Handoff already in progress",
                error_code="already_in_progress",
            )

        return HandoffResult(success=True, message="Preconditions met")

    # ── File path generation ─────────────────────────────────────────

    def generate_handoff_file_path(self, agent: Agent) -> str:
        """Generate an absolute handoff file path.

        Returns an absolute path so the agent writes to the correct location
        regardless of its working directory.

        Format: <project_root>/data/personas/{slug}/handoffs/{YYYYMMDDTHHmmss}-{agent-8digit}.md
        """
        # app.root_path points to the package dir (src/claude_headspace/)
        # parent.parent gets us to the project root (alongside data/, src/, etc.)
        project_root = Path(self.app.root_path).parent.parent
        persona = agent.persona
        slug = persona.slug
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        agent_suffix = str(agent.id).zfill(8)
        return str(
            project_root / "data" / "personas" / slug / "handoffs"
            / f"{timestamp}-{agent_suffix}.md"
        )

    # ── Handoff instruction composition ──────────────────────────────

    def compose_handoff_instruction(self, file_path: str) -> str:
        """Compose the instruction sent to the outgoing agent via tmux.

        Tells the agent to write a handoff document to the specified path.
        The agent is NOT told to exit — it stays alive after writing.
        """
        return (
            f"HANDOFF REQUESTED: Write a handoff document for your successor.\n\n"
            f"Write the document to: {file_path}\n\n"
            f"The document MUST include:\n"
            f"1. Current work: What you are working on right now\n"
            f"2. Progress: What has been completed so far\n"
            f"3. Decisions: Key decisions made and their rationale\n"
            f"4. Blockers: Any issues or blockers encountered\n"
            f"5. Files modified: List of files you have changed\n"
            f"6. Next steps: What your successor should do next\n\n"
            f"A successor agent will be created automatically with this context "
            f"once the document is written."
        )

    # ── Injection prompt composition ─────────────────────────────────

    def compose_injection_prompt(
        self, predecessor_agent: Agent, file_path: str
    ) -> str:
        """Compose the injection prompt sent to the successor agent.

        References the predecessor and points to the handoff file.
        """
        persona_name = (
            predecessor_agent.persona.name if predecessor_agent.persona else "Unknown"
        )
        project_name = (
            predecessor_agent.project.name if predecessor_agent.project else "Unknown"
        )
        return (
            f"You are continuing the work of a predecessor agent (Agent #{predecessor_agent.id}) "
            f"who was working as {persona_name} on project {project_name}.\n\n"
            f"Your predecessor wrote a handoff document before stopping. "
            f"Read this file to understand the current state of work:\n\n"
            f"  {file_path}\n\n"
            f"After reading the handoff document, continue where your predecessor "
            f"left off. Follow the next steps outlined in the document."
        )

    # ── Trigger handoff (async initiation) ───────────────────────────

    def trigger_handoff(self, agent_id: int, reason: str) -> HandoffResult:
        """Initiate the handoff flow for an agent.

        Validates preconditions, generates the file path, sends the handoff
        instruction to the agent via tmux, sets the handoff-in-progress flag,
        and starts a background polling thread to detect the handoff file.
        Returns immediately.
        """
        # Validate preconditions
        validation = self.validate_preconditions(agent_id)
        if not validation.success:
            return validation

        agent = db.session.get(Agent, agent_id)

        # Generate file path
        file_path = self.generate_handoff_file_path(agent)

        # Ensure directory exists
        dir_path = Path(file_path).parent
        dir_path.mkdir(parents=True, exist_ok=True)

        # Compose instruction
        instruction = self.compose_handoff_instruction(file_path)

        # Send instruction via tmux bridge
        from . import tmux_bridge

        result = tmux_bridge.send_text(
            pane_id=agent.tmux_pane_id,
            text=instruction,
        )

        if not result.success:
            error_msg = result.error_message or "Send failed"
            logger.error(
                f"handoff_trigger: failed to send instruction to agent {agent_id}: {error_msg}"
            )
            self._broadcast_error(
                agent, f"Failed to send handoff instruction: {error_msg}"
            )
            return HandoffResult(
                success=False,
                message=f"Failed to send handoff instruction: {error_msg}",
                error_code="send_failed",
            )

        # Set handoff-in-progress flag
        with _handoff_lock:
            _handoff_in_progress[agent_id] = {
                "file_path": file_path,
                "reason": reason,
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"handoff_trigger: initiated — agent_id={agent_id}, "
            f"file_path={file_path}, reason={reason}"
        )

        # Post "preparing handoff" message to voice chat so humans and machines
        # can see the handoff is in progress before summarisation begins.
        self._post_handoff_status_turn(
            agent, "Preparing handoff — summarising context for successor agent"
        )

        # Start background polling thread to detect when the file is written
        poll_thread = threading.Thread(
            target=self._poll_for_handoff_file,
            args=(agent_id,),
            daemon=True,
            name=f"handoff-poll-{agent_id}",
        )
        poll_thread.start()

        return HandoffResult(success=True, message="Handoff initiated")

    # ── Background file polling ───────────────────────────────────────

    def _poll_for_handoff_file(self, agent_id: int) -> None:
        """Poll for the handoff file in a background thread.

        Runs with app context. When the file is detected (exists + non-empty),
        calls complete_handoff(). Times out after POLL_TIMEOUT_SECONDS.
        """
        metadata = self.get_handoff_metadata(agent_id)
        if not metadata:
            return

        file_path = metadata["file_path"]
        start_time = time.monotonic()

        logger.info(
            f"handoff_poll: started — agent_id={agent_id}, file_path={file_path}"
        )

        while time.monotonic() - start_time < POLL_TIMEOUT_SECONDS:
            # Check if handoff was already completed (e.g. by stop hook path)
            if not self.is_handoff_in_progress(agent_id):
                logger.info(
                    f"handoff_poll: flag cleared (completed elsewhere) — "
                    f"agent_id={agent_id}"
                )
                return

            # Check for the file
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info(
                    f"handoff_poll: file detected — agent_id={agent_id}, "
                    f"file_path={file_path}"
                )
                # Complete the handoff within app context
                with self.app.app_context():
                    result = self.complete_handoff(agent_id)
                    if result.success:
                        logger.info(
                            f"handoff_poll: completion success — agent_id={agent_id}"
                        )
                    elif result.error_code == "already_completed":
                        logger.info(
                            f"handoff_poll: already completed — agent_id={agent_id}"
                        )
                    else:
                        logger.error(
                            f"handoff_poll: completion failed — agent_id={agent_id}, "
                            f"error={result.message}"
                        )
                return

            time.sleep(POLL_INTERVAL_SECONDS)

        # Timeout — file was never written
        logger.error(
            f"handoff_poll: timeout — agent_id={agent_id}, "
            f"file_path={file_path}, waited {POLL_TIMEOUT_SECONDS}s"
        )
        with self.app.app_context():
            agent = db.session.get(Agent, agent_id)
            if agent:
                self._broadcast_error(
                    agent,
                    f"Handoff timed out: agent did not write the handoff file "
                    f"within {POLL_TIMEOUT_SECONDS // 60} minutes",
                )
                self._notify_error(
                    agent,
                    f"Handoff timed out after {POLL_TIMEOUT_SECONDS // 60} minutes",
                )
        self._clear_handoff_flag(agent_id)

    # ── Core handoff completion ───────────────────────────────────────

    def complete_handoff(self, agent_id: int) -> HandoffResult:
        """Complete the handoff after the file is verified.

        Creates the Handoff DB record, creates the successor agent, and
        clears the handoff flag. The outgoing agent is NOT shut down.

        This method is idempotent — if a Handoff record already exists
        for this agent, it returns success without creating a duplicate.
        """
        metadata = self.get_handoff_metadata(agent_id)
        if not metadata:
            return HandoffResult(
                success=False,
                message="No handoff in progress for this agent",
                error_code="no_handoff",
            )

        file_path = metadata["file_path"]
        reason = metadata["reason"]

        # Verify handoff file
        verification = self.verify_handoff_file(file_path)
        if not verification.success:
            logger.error(
                f"handoff_complete: file verification failed — "
                f"agent_id={agent_id}, file_path={file_path}: {verification.message}"
            )
            agent = db.session.get(Agent, agent_id)
            if agent:
                self._broadcast_error(
                    agent, f"Handoff file verification failed: {verification.message}"
                )
                self._notify_error(
                    agent,
                    f"Handoff file verification failed: {verification.message}",
                )
            self._clear_handoff_flag(agent_id)
            return verification

        # Idempotent check — already completed by another path?
        existing = Handoff.query.filter_by(agent_id=agent_id).first()
        if existing:
            self._clear_handoff_flag(agent_id)
            return HandoffResult(
                success=True,
                message="Handoff already completed",
                error_code="already_completed",
            )

        agent = db.session.get(Agent, agent_id)
        if not agent:
            self._clear_handoff_flag(agent_id)
            return HandoffResult(
                success=False,
                message="Agent not found",
                error_code="not_found",
            )

        # Create Handoff DB record
        injection_prompt = self.compose_injection_prompt(agent, file_path)
        handoff_record = Handoff(
            agent_id=agent.id,
            reason=reason,
            file_path=file_path,
            injection_prompt=injection_prompt,
        )
        db.session.add(handoff_record)
        db.session.commit()

        logger.info(
            f"handoff_complete: record created — "
            f"handoff_id={handoff_record.id}, agent_id={agent.id}"
        )

        # Create successor agent (outgoing agent stays alive)
        successor_result = self._create_successor(agent)
        if not successor_result.success:
            logger.error(
                f"handoff_complete: successor creation failed — "
                f"agent_id={agent.id}: {successor_result.message}"
            )
            self._broadcast_error(
                agent, f"Successor creation failed: {successor_result.message}"
            )
            self._notify_error(
                agent, f"Successor creation failed: {successor_result.message}"
            )
            self._clear_handoff_flag(agent.id)
            return successor_result

        # Clear the handoff-in-progress flag
        self._clear_handoff_flag(agent.id)

        # Broadcast success
        self._broadcast_success(agent)

        logger.info(
            f"handoff_complete: done — outgoing_agent_id={agent.id}, "
            f"handoff_id={handoff_record.id}, successor pending registration"
        )

        return HandoffResult(success=True, message="Handoff complete")

    # ── Stop hook continuation (backward-compat fallback) ─────────────

    def is_handoff_in_progress(self, agent_id: int) -> bool:
        """Check if a handoff is in progress for the given agent."""
        with _handoff_lock:
            return agent_id in _handoff_in_progress

    def get_handoff_metadata(self, agent_id: int) -> dict | None:
        """Get handoff metadata for an agent, or None if no handoff in progress."""
        with _handoff_lock:
            return _handoff_in_progress.get(agent_id)

    def continue_after_stop(self, agent: Agent) -> HandoffResult:
        """Continue the handoff flow after the stop hook fires.

        Called by hook_receiver.process_stop() when it detects the
        handoff-in-progress flag. Delegates to complete_handoff() which
        is idempotent — safe even if the polling thread already completed it.

        The outgoing agent is NOT shut down (it already stopped on its own
        if the stop hook fired).
        """
        return self.complete_handoff(agent.id)

    # ── Successor injection delivery ─────────────────────────────────

    def deliver_injection_prompt(self, successor_agent: Agent) -> HandoffResult:
        """Deliver the handoff injection prompt to a successor agent.

        Called after skill injection completes for a successor agent that
        has a previous_agent_id with a Handoff record.
        """
        if not successor_agent.previous_agent_id:
            return HandoffResult(
                success=False,
                message="Agent has no previous_agent_id",
                error_code="no_predecessor",
            )

        # Find the Handoff record for the predecessor
        handoff = Handoff.query.filter_by(
            agent_id=successor_agent.previous_agent_id
        ).first()
        if not handoff:
            return HandoffResult(
                success=False,
                message="No handoff record found for predecessor",
                error_code="no_handoff_record",
            )

        if not handoff.injection_prompt:
            return HandoffResult(
                success=False,
                message="Handoff record has no injection prompt",
                error_code="no_injection_prompt",
            )

        if not successor_agent.tmux_pane_id:
            logger.warning(
                f"handoff_injection: successor agent {successor_agent.id} "
                f"has no tmux pane — cannot deliver injection prompt"
            )
            return HandoffResult(
                success=False,
                message="Successor agent has no tmux pane",
                error_code="no_tmux_pane",
            )

        # Send the injection prompt via tmux
        from . import tmux_bridge

        result = tmux_bridge.send_text(
            pane_id=successor_agent.tmux_pane_id,
            text=handoff.injection_prompt,
        )

        if not result.success:
            error_msg = result.error_message or "Send failed"
            logger.error(
                f"handoff_injection: failed — successor_agent_id={successor_agent.id}, "
                f"error={error_msg}"
            )
            return HandoffResult(
                success=False,
                message=f"Failed to deliver injection prompt: {error_msg}",
                error_code="send_failed",
            )

        logger.info(
            f"handoff_injection: success — successor_agent_id={successor_agent.id}, "
            f"predecessor_agent_id={successor_agent.previous_agent_id}, "
            f"handoff_id={handoff.id}"
        )

        return HandoffResult(success=True, message="Injection prompt delivered")

    # ── File verification ────────────────────────────────────────────

    def verify_handoff_file(self, file_path: str) -> HandoffResult:
        """Verify that the handoff file exists and is non-empty."""
        if not os.path.exists(file_path):
            return HandoffResult(
                success=False,
                message=f"Handoff file does not exist: {file_path}",
                error_code="file_not_found",
            )

        if os.path.getsize(file_path) == 0:
            return HandoffResult(
                success=False,
                message=f"Handoff file is empty: {file_path}",
                error_code="file_empty",
            )

        return HandoffResult(success=True, message="Handoff file verified")

    # ── Internal helpers ─────────────────────────────────────────────

    def _create_successor(self, outgoing_agent: Agent) -> HandoffResult:
        """Create a successor agent with the same persona."""
        from .agent_lifecycle import create_agent

        persona = outgoing_agent.persona
        if not persona:
            return HandoffResult(
                success=False,
                message="Outgoing agent has no persona",
                error_code="no_persona",
            )

        result = create_agent(
            project_id=outgoing_agent.project_id,
            persona_slug=persona.slug,
            previous_agent_id=outgoing_agent.id,
        )

        if not result.success:
            return HandoffResult(
                success=False,
                message=f"create_agent failed: {result.message}",
                error_code="create_failed",
            )

        logger.info(
            f"handoff_successor: created — outgoing_agent_id={outgoing_agent.id}, "
            f"persona_slug={persona.slug}, tmux_session={result.tmux_session_name}"
        )

        return HandoffResult(success=True, message="Successor agent created")

    def _clear_handoff_flag(self, agent_id: int) -> None:
        """Remove the handoff-in-progress flag for an agent."""
        with _handoff_lock:
            _handoff_in_progress.pop(agent_id, None)

    def _broadcast_error(self, agent: Agent, message: str) -> None:
        """Broadcast a handoff error via SSE."""
        try:
            from .broadcaster import get_broadcaster

            get_broadcaster().broadcast(
                "handoff_error",
                {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Handoff error broadcast failed: {e}")

    def _broadcast_success(self, agent: Agent) -> None:
        """Broadcast a handoff success via SSE."""
        try:
            from .broadcaster import get_broadcaster

            persona_name = agent.persona.name if agent.persona else "Unknown"
            get_broadcaster().broadcast(
                "handoff_complete",
                {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "persona_name": persona_name,
                    "message": f"Handoff complete — successor {persona_name} starting",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Handoff success broadcast failed: {e}")

    def _post_handoff_status_turn(self, agent: Agent, text: str) -> None:
        """Post a PROGRESS turn to voice chat for handoff status visibility.

        Creates a Turn record and broadcasts turn_created SSE so the message
        appears in voice/embed chat for both human viewers and machine consumers.
        """
        try:
            from ..models.turn import Turn, TurnActor, TurnIntent

            current_command = agent.get_current_command()
            if not current_command:
                logger.warning(
                    f"handoff_status_turn: agent {agent.id} has no current command "
                    f"— skipping status turn"
                )
                return

            turn = Turn(
                command_id=current_command.id,
                actor=TurnActor.AGENT,
                intent=TurnIntent.PROGRESS,
                text=text,
                timestamp_source="server",
            )
            db.session.add(turn)
            db.session.commit()

            from .broadcaster import get_broadcaster

            get_broadcaster().broadcast("turn_created", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "text": text,
                "actor": "agent",
                "intent": "progress",
                "command_id": current_command.id,
                "command_instruction": current_command.instruction,
                "turn_id": turn.id,
                "timestamp": turn.timestamp.isoformat(),
            })

            logger.info(
                f"handoff_status_turn: posted — agent_id={agent.id}, "
                f"turn_id={turn.id}, text='{text}'"
            )
        except Exception as e:
            logger.warning(f"handoff_status_turn: failed — {e}")

    def _notify_error(self, agent: Agent, message: str) -> None:
        """Send an OS notification for a handoff error."""
        try:
            from .notification_service import get_notification_service

            svc = get_notification_service()
            svc.notify_awaiting_input(
                agent_id=str(agent.id),
                agent_name=agent.name or f"Agent {agent.id}",
                project=agent.project.name if agent.project else None,
                command_instruction="Handoff Error",
                turn_text=message,
            )
        except Exception as e:
            logger.warning(f"Handoff error notification failed: {e}")


def reset_handoff_state() -> None:
    """Clear all handoff-in-progress flags (for testing)."""
    with _handoff_lock:
        _handoff_in_progress.clear()
