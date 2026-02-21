"""Handoff execution service.

Orchestrates the full handoff lifecycle: validate preconditions, instruct the
outgoing agent to write a handoff document, verify the file, create a Handoff
DB record, shut down the outgoing agent, create a successor with the same
persona, and deliver the handoff injection prompt after skill injection.
"""

import logging
import os
import threading
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
        """Generate the handoff file path.

        Format: data/personas/{slug}/handoffs/{YYYYMMDDTHHmmss}-{agent-8digit}.md
        """
        persona = agent.persona
        slug = persona.slug
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        agent_suffix = str(agent.id).zfill(8)
        return f"data/personas/{slug}/handoffs/{timestamp}-{agent_suffix}.md"

    # ── Handoff instruction composition ──────────────────────────────

    def compose_handoff_instruction(self, file_path: str) -> str:
        """Compose the instruction sent to the outgoing agent via tmux.

        Tells the agent to write a handoff document to the specified path.
        """
        return (
            f"IMPORTANT: Your context window is running low. You need to write a "
            f"handoff document for your successor before stopping.\n\n"
            f"Write a handoff document to: {file_path}\n\n"
            f"The document MUST include:\n"
            f"1. Current work: What you are working on right now\n"
            f"2. Progress: What has been completed so far\n"
            f"3. Decisions: Key decisions made and their rationale\n"
            f"4. Blockers: Any issues or blockers encountered\n"
            f"5. Files modified: List of files you have changed\n"
            f"6. Next steps: What your successor should do next\n\n"
            f"After writing the document, use /exit to end your session. "
            f"A successor agent will be created automatically with this context."
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
        instruction to the agent via tmux, and sets the handoff-in-progress flag.
        Returns immediately — the flow continues when the stop hook fires.
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

        return HandoffResult(success=True, message="Handoff initiated")

    # ── Stop hook continuation ───────────────────────────────────────

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
        handoff-in-progress flag. Verifies the file, creates the DB record,
        shuts down the outgoing agent, creates the successor, and schedules
        injection delivery.
        """
        metadata = self.get_handoff_metadata(agent.id)
        if not metadata:
            return HandoffResult(
                success=False,
                message="No handoff in progress for this agent",
                error_code="no_handoff",
            )

        file_path = metadata["file_path"]
        reason = metadata["reason"]

        # Step 1: Verify handoff file
        verification = self.verify_handoff_file(file_path)
        if not verification.success:
            logger.error(
                f"handoff_continuation: file verification failed — "
                f"agent_id={agent.id}, file_path={file_path}: {verification.message}"
            )
            self._broadcast_error(
                agent, f"Handoff file verification failed: {verification.message}"
            )
            self._notify_error(
                agent,
                f"Handoff file verification failed: {verification.message}",
            )
            # Clear the flag — handoff failed
            self._clear_handoff_flag(agent.id)
            return verification

        # Step 2: Create Handoff DB record
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
            f"handoff_continuation: record created — "
            f"handoff_id={handoff_record.id}, agent_id={agent.id}"
        )

        # Step 3: Shut down outgoing agent
        from .agent_lifecycle import shutdown_agent

        shutdown_result = shutdown_agent(agent.id)
        if not shutdown_result.success:
            logger.warning(
                f"handoff_continuation: shutdown failed — agent_id={agent.id}: "
                f"{shutdown_result.message} (proceeding anyway)"
            )

        # Step 4: Create successor agent
        successor_result = self._create_successor(agent)
        if not successor_result.success:
            logger.error(
                f"handoff_continuation: successor creation failed — "
                f"agent_id={agent.id}: {successor_result.message}"
            )
            self._broadcast_error(
                agent, f"Successor creation failed: {successor_result.message}"
            )
            self._notify_error(
                agent, f"Successor creation failed: {successor_result.message}"
            )
            # Clear the flag — handoff partially completed (record preserved)
            self._clear_handoff_flag(agent.id)
            return successor_result

        # Clear the handoff-in-progress flag
        self._clear_handoff_flag(agent.id)

        # Step 5: Schedule injection delivery for the successor
        # The successor will register via session-start hook, receive skill
        # injection, then get the handoff injection prompt.
        # We store the handoff record ID so the session-start hook can find it.
        logger.info(
            f"handoff_continuation: complete — outgoing_agent_id={agent.id}, "
            f"handoff_id={handoff_record.id}, successor pending registration"
        )

        return HandoffResult(success=True, message="Handoff continuation complete")

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
