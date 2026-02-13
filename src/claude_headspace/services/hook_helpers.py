"""Service helper functions for hook receiver.

Thin wrappers around Flask app extensions and SSE broadcasting.
Moved from hook_receiver.py to reduce module size.
"""

import logging
from datetime import datetime, timezone

from ..database import db
from ..models.agent import Agent
from ..models.turn import Turn, TurnActor, TurnIntent

logger = logging.getLogger(__name__)


def get_lifecycle_manager():
    """Create a TaskLifecycleManager with the current app's event writer."""
    from .task_lifecycle import TaskLifecycleManager

    event_writer = None
    try:
        from flask import current_app
        event_writer = current_app.extensions.get("event_writer")
    except RuntimeError:
        logger.debug("No app context for event_writer")
    return TaskLifecycleManager(
        session=db.session,
        event_writer=event_writer,
    )


def trigger_priority_scoring() -> None:
    """Trigger rate-limited priority scoring after state transitions."""
    try:
        from flask import current_app
        service = current_app.extensions.get("priority_scoring_service")
        if service:
            service.trigger_scoring()
    except Exception as e:
        logger.warning(f"Priority scoring trigger failed: {e}")


def execute_pending_summarisations(pending: list) -> None:
    """Execute pending summarisation requests from the lifecycle manager."""
    if not pending:
        return
    try:
        from flask import current_app
        service = current_app.extensions.get("summarisation_service")
        if service:
            service.execute_pending(pending, db.session)
    except Exception as e:
        logger.warning(f"Post-commit summarisation failed (non-fatal): {e}")


def broadcast_state_change(agent: Agent, event_type: str, new_state: str, message: str | None = None) -> None:
    """Broadcast a state_changed SSE event."""
    try:
        from .broadcaster import get_broadcaster
        get_broadcaster().broadcast("state_changed", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "project_name": agent.project.name if agent.project else None,
            "agent_session": str(agent.session_uuid),
            "event_type": event_type,
            "new_state": new_state.upper() if isinstance(new_state, str) else new_state,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"State change broadcast failed: {e}")


def broadcast_turn_created(agent: Agent, text: str, task, tool_input: dict | None = None, turn_id: int | None = None, intent: str = "question") -> None:
    """Broadcast a turn_created SSE event."""
    try:
        from .broadcaster import get_broadcaster
        payload = {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": text,
            "actor": "agent",
            "intent": intent,
            "task_id": task.id if task else None,
            "turn_id": turn_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_input:
            payload["tool_input"] = tool_input
        get_broadcaster().broadcast("turn_created", payload)
    except Exception as e:
        logger.warning(f"Turn created broadcast failed: {e}")


def send_notification(agent: Agent, task, turn_text: str | None) -> None:
    """Send an OS notification for awaiting input."""
    try:
        from .notification_service import get_notification_service
        from .task_lifecycle import get_instruction_for_notification
        svc = get_notification_service()
        svc.notify_awaiting_input(
            agent_id=str(agent.id),
            agent_name=agent.name or f"Agent {agent.id}",
            project=agent.project.name if agent.project else None,
            task_instruction=get_instruction_for_notification(task),
            turn_text=turn_text,
        )
    except Exception as e:
        logger.warning(f"Notification send failed: {e}")


def send_completion_notification(agent: Agent, task) -> None:
    """Send task-complete notification using AI-generated summaries.

    Called AFTER summarisation so task.completion_summary and task.instruction
    are populated with useful content instead of raw transcript text.
    """
    try:
        from .notification_service import get_notification_service
        from .task_lifecycle import get_instruction_for_notification
        svc = get_notification_service()

        instruction = get_instruction_for_notification(task)
        completion_text = task.completion_summary or None

        svc.notify_task_complete(
            agent_id=str(agent.id),
            agent_name=agent.name or f"Agent {agent.id}",
            project=agent.project.name if agent.project else None,
            task_instruction=instruction,
            turn_text=completion_text,
        )
    except Exception as e:
        logger.warning(f"Completion notification failed (non-fatal): {e}")


def extract_transcript_content(agent: Agent) -> str:
    """Extract the last agent response from the transcript file."""
    if not agent.transcript_path:
        logger.debug(f"TRANSCRIPT_EXTRACT agent={agent.id}: no transcript_path")
        return ""
    try:
        from .transcript_reader import read_transcript_file
        result = read_transcript_file(agent.transcript_path)
        logger.debug(
            f"TRANSCRIPT_EXTRACT agent={agent.id}: success={result.success}, "
            f"text_len={len(result.text) if result.text else 0}, "
            f"error={result.error}"
        )
        if result.success and result.text:
            return result.text
    except Exception as e:
        logger.warning(f"Transcript extraction failed for agent {agent.id}: {e}")
    return ""


def capture_progress_text(agent: Agent, current_task, state) -> None:
    """Read new transcript entries and create PROGRESS turns for intermediate agent text.

    Called during post_tool_use when the agent is PROCESSING. Each assistant text
    entry written to the transcript since the last capture becomes a PROGRESS Turn,
    giving the voice bridge (and dashboard chat) real-time visibility into what
    the agent is doing between tool calls.

    Args:
        agent: The agent whose transcript to read
        current_task: The current active task
        state: AgentHookState instance for transcript position tracking
    """
    if not agent.transcript_path:
        return

    import os
    from .transcript_reader import read_new_entries_from_position

    # Initialize position to current file size if not yet tracked
    if state.get_transcript_position(agent.id) is None:
        try:
            state.set_transcript_position(agent.id, os.path.getsize(agent.transcript_path))
        except OSError:
            return
        return  # First call — just set the baseline, don't capture

    pos = state.get_transcript_position(agent.id)
    try:
        entries, new_pos = read_new_entries_from_position(agent.transcript_path, pos)
    except Exception as e:
        logger.debug(f"Progress capture failed for agent {agent.id}: {e}")
        return

    if new_pos == pos:
        return  # No new content

    state.set_transcript_position(agent.id, new_pos)

    # Filter for assistant entries with meaningful text
    MIN_PROGRESS_LEN = 10
    new_texts = []
    for entry in entries:
        if entry.role == "assistant" and entry.content and len(entry.content.strip()) >= MIN_PROGRESS_LEN:
            new_texts.append(entry.content.strip())

    if not new_texts:
        return

    for text in new_texts:
        state.append_progress_text(agent.id, text)

        # Create a PROGRESS Turn record
        turn = Turn(
            task_id=current_task.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text=text,
        )
        db.session.add(turn)
        db.session.flush()

        # Broadcast so SSE clients (voice bridge, dashboard) pick it up
        try:
            from .broadcaster import get_broadcaster
            get_broadcaster().broadcast("turn_created", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "text": text,
                "actor": "agent",
                "intent": "progress",
                "task_id": current_task.id,
                "turn_id": turn.id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"Progress turn broadcast failed: {e}")

    logger.info(
        f"progress_capture: agent_id={agent.id}, task_id={current_task.id}, "
        f"new_turns={len(new_texts)}, total_captured={len(state.get_progress_texts(agent.id))}"
    )
