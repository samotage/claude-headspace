"""Deferred stop handler for Claude Code hook events.

When the stop hook fires before Claude has flushed its transcript to disk,
this module schedules a background thread that polls for the transcript
with exponential backoff, then applies the appropriate state transition.

Extracted from hook_receiver.py for modularity. Thread safety is provided
by AgentHookState (hook_agent_state.py).
"""

import logging
import threading
import time
from datetime import datetime, timezone

from ..database import db
from ..models.agent import Agent
from ..models.task import TaskState
from ..models.turn import TurnActor, TurnIntent

logger = logging.getLogger(__name__)


# ── Inlined helper functions ─────────────────────────────────────────
# Formerly imported from hook_helpers.py — direct service access.


def _get_lifecycle_manager():
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


def _trigger_priority_scoring() -> None:
    """Trigger rate-limited priority scoring after state transitions."""
    try:
        from flask import current_app
        service = current_app.extensions.get("priority_scoring_service")
        if service:
            service.trigger_scoring()
    except Exception as e:
        logger.warning(f"Priority scoring trigger failed: {e}")


def _execute_pending_summarisations(pending: list) -> None:
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


def _broadcast_turn_created(agent: Agent, text: str, task, tool_input: dict | None = None, turn_id: int | None = None, intent: str = "question", question_source_type: str | None = None) -> None:
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
            "task_instruction": task.instruction if task else None,
            "turn_id": turn_id,
            "question_source_type": question_source_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_input:
            payload["tool_input"] = tool_input
        get_broadcaster().broadcast("turn_created", payload)
    except Exception as e:
        logger.warning(f"Turn created broadcast failed: {e}")


def _send_completion_notification(agent: Agent, task) -> None:
    """Send task-complete notification using AI-generated summaries."""
    try:
        from .notification_service import get_notification_service
        from .task_lifecycle import get_instruction_for_notification
        svc = get_notification_service()
        svc.notify_task_complete(
            agent_id=str(agent.id),
            agent_name=agent.name or f"Agent {agent.id}",
            project=agent.project.name if agent.project else None,
            task_instruction=get_instruction_for_notification(task),
            turn_text=task.completion_summary or None,
        )
    except Exception as e:
        logger.warning(f"Completion notification failed (non-fatal): {e}")


def _extract_transcript_content(agent: Agent) -> str:
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


# ── Public API ───────────────────────────────────────────────────────


def schedule_deferred_stop(agent: Agent, current_task) -> None:
    """Schedule a background thread to retry transcript extraction after a delay.

    Instead of blocking the Flask request handler with time.sleep(), this
    spawns a daemon thread that waits, re-reads the transcript, and applies
    the appropriate state transition within a fresh app context.

    Uses AgentHookState.try_claim_deferred_stop() to prevent duplicate
    threads for the same agent.
    """
    from .hook_agent_state import get_agent_hook_state

    state = get_agent_hook_state()
    agent_id = agent.id
    task_id = current_task.id
    project_id = agent.project_id

    # Atomic claim: skip if a deferred stop is already in flight
    if not state.try_claim_deferred_stop(agent_id):
        logger.info(f"deferred_stop: agent_id={agent_id}, skipped (already pending)")
        return

    # Capture Flask app reference BEFORE starting thread
    # (current_app is not available inside background threads)
    try:
        from flask import current_app
        app = current_app._get_current_object()
    except RuntimeError:
        logger.warning("Cannot schedule deferred stop: no app context available")
        state.release_deferred_stop(agent_id)
        return

    def _deferred_check():
        try:
            with app.app_context():
                try:
                    _run_deferred_stop(
                        app=app,
                        agent_id=agent_id,
                        task_id=task_id,
                        project_id=project_id,
                    )
                except Exception as e:
                    logger.exception(f"deferred_stop failed for agent {agent_id}: {e}")
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
        finally:
            state.release_deferred_stop(agent_id)

    t = threading.Thread(target=_deferred_check, daemon=True, name=f"deferred-stop-{agent_id}")
    t.start()


def _run_deferred_stop(
    app,
    agent_id: int,
    task_id: int,
    project_id: int,
) -> None:
    """Core logic for the deferred stop background thread.

    Polls for transcript content with backoff, deduplicates against
    previously captured PROGRESS turns, detects intent, and applies
    the appropriate state transition.
    """
    from ..models.task import Task
    from .card_state import broadcast_card_refresh
    from .hook_agent_state import get_agent_hook_state
    from .intent_detector import detect_agent_intent

    state = get_agent_hook_state()

    # Poll for transcript content with backoff
    delays = [0.5, 1.0, 1.5, 2.0]  # Total: 5s max
    agent_text = ""
    for delay in delays:
        time.sleep(delay)

        task = db.session.get(Task, task_id)
        if not task or task.state == TaskState.COMPLETE:
            return  # Already completed by another hook

        agent_obj = db.session.get(Agent, agent_id)
        if not agent_obj:
            return

        # Refresh to avoid stale reads
        db.session.refresh(task)
        if task.state == TaskState.COMPLETE:
            return

        agent_text = _extract_transcript_content(agent_obj)
        if agent_text:
            break

    logger.info(
        f"deferred_stop: agent_id={agent_id}, "
        f"transcript_retry: len={len(agent_text) if agent_text else 0}, "
        f"polls={delays.index(delay) + 1 if agent_text else len(delays)}"
    )
    if not agent_text:
        # Still empty — complete with no transcript
        lifecycle = _get_lifecycle_manager()
        lifecycle.complete_task(task=task, trigger="hook:stop:deferred_empty")
        _trigger_priority_scoring()
        pending = lifecycle.get_pending_summarisations()
        db.session.commit()
        broadcast_card_refresh(agent_obj, "stop_deferred")
        _execute_pending_summarisations(pending)
        _send_completion_notification(agent_obj, task)
        logger.info(f"deferred_stop: agent_id={agent_id}, completed (empty transcript)")
        return

    # Deduplicate against captured PROGRESS turns
    full_agent_text = agent_text
    completion_text = agent_text
    captured = state.consume_progress_texts(agent_id)
    if captured:
        pos = state.get_transcript_position(agent_id) or 0
        if pos > 0 and agent_obj.transcript_path:
            from .transcript_reader import read_new_entries_from_position
            new_entries, _ = read_new_entries_from_position(agent_obj.transcript_path, pos)
            new_texts = [
                e.content.strip() for e in new_entries
                if e.role == "assistant" and e.content and e.content.strip()
            ]
            if new_texts:
                completion_text = "\n\n".join(new_texts)
            else:
                # All text captured as PROGRESS — use full
                # text so a COMPLETION Turn is still created.
                completion_text = full_agent_text
    state.clear_transcript_position(agent_id)

    inference_service = app.extensions.get("inference_service")

    intent_result = detect_agent_intent(
        full_agent_text, inference_service=inference_service,
        project_id=project_id, agent_id=agent_id,
    )

    # Check for stale notification turn to replace
    stale_notification_turn = None
    if task.turns:
        for t in reversed(task.turns):
            if (t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION
                    and t.text == "Claude is waiting for your input"):
                stale_notification_turn = t
                break

    lifecycle = _get_lifecycle_manager()
    if intent_result.intent == TurnIntent.QUESTION:
        if stale_notification_turn:
            stale_notification_turn.text = full_agent_text
            stale_notification_turn.question_text = full_agent_text
            stale_notification_turn.question_source_type = "free_text"
        else:
            from ..models.turn import Turn as _Turn
            turn = _Turn(
                task_id=task.id, actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION, text=full_agent_text,
                question_text=full_agent_text,
                question_source_type="free_text",
            )
            db.session.add(turn)
        lifecycle.update_task_state(
            task=task, to_state=TaskState.AWAITING_INPUT,
            trigger="hook:stop:deferred_question", confidence=intent_result.confidence,
        )
    elif intent_result.intent == TurnIntent.END_OF_TASK:
        if stale_notification_turn:
            stale_notification_turn.text = completion_text or ""
            stale_notification_turn.intent = TurnIntent.END_OF_TASK
            stale_notification_turn.question_text = None
            stale_notification_turn.question_source_type = None
        lifecycle.complete_task(
            task=task, trigger="hook:stop:deferred_end_of_task",
            agent_text=completion_text, intent=TurnIntent.END_OF_TASK,
        )
        if completion_text != full_agent_text:
            task.full_output = full_agent_text
    else:
        if stale_notification_turn:
            stale_notification_turn.text = completion_text or ""
            stale_notification_turn.intent = TurnIntent.COMPLETION
            stale_notification_turn.question_text = None
            stale_notification_turn.question_source_type = None
        lifecycle.complete_task(task=task, trigger="hook:stop:deferred", agent_text=completion_text)
        if completion_text != full_agent_text:
            task.full_output = full_agent_text

    _trigger_priority_scoring()
    pending = lifecycle.get_pending_summarisations()
    db.session.commit()
    broadcast_card_refresh(agent_obj, "stop_deferred")
    _execute_pending_summarisations(pending)

    if task.state == TaskState.COMPLETE:
        _send_completion_notification(agent_obj, task)
    # Broadcast agent turn for all intent types (voice chat needs this)
    if task.turns:
        broadcast_turn = None
        for t in reversed(task.turns):
            if t.actor == TurnActor.AGENT and t.intent in (
                TurnIntent.QUESTION, TurnIntent.COMPLETION, TurnIntent.END_OF_TASK,
            ):
                broadcast_turn = t
                break
        if not broadcast_turn:
            for t in reversed(task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.PROGRESS and t.text:
                    broadcast_turn = t
                    break
        if broadcast_turn:
            _broadcast_turn_created(
                agent_obj, broadcast_turn.text, task,
                tool_input=broadcast_turn.tool_input, turn_id=broadcast_turn.id,
                intent=broadcast_turn.intent.value,
                question_source_type=broadcast_turn.question_source_type,
            )

    logger.info(
        f"deferred_stop: agent_id={agent_id}, "
        f"new_state={task.state.value}, intent={intent_result.intent.value}"
    )
