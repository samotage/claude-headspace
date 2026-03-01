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
from ..models.command import CommandState
from ..models.turn import TurnActor, TurnIntent
from .advisory_lock import LockNamespace, advisory_lock

logger = logging.getLogger(__name__)


# ── Shared helpers imported from hook_receiver ───────────────────────
# These were formerly inlined copies. Now imported to eliminate duplication.
from .hook_receiver import (
    _get_lifecycle_manager,
    _trigger_priority_scoring,
    _execute_pending_summarisations,
    _broadcast_turn_created,
    _send_completion_notification,
    _extract_transcript_content,
)


# ── Public API ───────────────────────────────────────────────────────


def schedule_deferred_stop(agent: Agent, current_command) -> None:
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
    command_id = current_command.id
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
                        command_id=command_id,
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
    command_id: int,
    project_id: int,
) -> None:
    """Core logic for the deferred stop background thread.

    Polls for transcript content with backoff, deduplicates against
    previously captured PROGRESS turns, detects intent, and applies
    the appropriate state transition.
    """
    from ..models.command import Command
    from .card_state import broadcast_card_refresh
    from .hook_agent_state import get_agent_hook_state
    from .intent_detector import detect_agent_intent

    state = get_agent_hook_state()

    # Phase 1: Sleep/retry loop WITHOUT holding the advisory lock.
    # The lock is only needed for state mutation, not for polling.
    delays = [0.5, 1.0, 1.5, 2.0]  # Total: 5s max
    agent_text = ""
    for delay in delays:
        time.sleep(delay)

        cmd = db.session.get(Command, command_id)
        if not cmd or cmd.state == CommandState.COMPLETE:
            return  # Already completed by another hook

        agent_obj = db.session.get(Agent, agent_id)
        if not agent_obj:
            return

        # Refresh to avoid stale reads
        db.session.refresh(cmd)
        if cmd.state == CommandState.COMPLETE:
            return

        agent_text = _extract_transcript_content(agent_obj)
        if agent_text:
            break

    # Phase 2: Acquire advisory lock BEFORE any state mutation.
    # Re-check command state after acquisition in case session_end
    # completed the command while we were waiting for the lock.
    with advisory_lock(LockNamespace.AGENT, agent_id):
        cmd = db.session.get(Command, command_id)
        if not cmd:
            return
        db.session.refresh(cmd)
        if cmd.state == CommandState.COMPLETE:
            logger.info(
                f"deferred_stop: agent_id={agent_id}, "
                f"command already COMPLETE after lock acquisition — skipping"
            )
            return

        agent_obj = db.session.get(Agent, agent_id)
        if not agent_obj:
            return

        _run_deferred_stop_locked(
            app=app,
            agent_id=agent_id,
            agent_obj=agent_obj,
            cmd=cmd,
            agent_text=agent_text,
            command_id=command_id,
            project_id=project_id,
            state=state,
            delays=delays,
        )


def _run_deferred_stop_locked(
    app,
    agent_id: int,
    agent_obj,
    cmd,
    agent_text: str,
    command_id: int,
    project_id: int,
    state,
    delays: list,
) -> None:
    """Core deferred stop logic, called while holding the advisory lock."""
    from .card_state import broadcast_card_refresh
    from .intent_detector import detect_agent_intent

    logger.info(
        f"deferred_stop: agent_id={agent_id}, "
        f"transcript_retry: len={len(agent_text) if agent_text else 0}, "
        f"polls={len(delays)}"
    )
    if not agent_text:
        # Still empty — complete with no transcript
        lifecycle = _get_lifecycle_manager()
        lifecycle.complete_command(command=cmd, trigger="hook:stop:deferred_empty")
        _trigger_priority_scoring()
        pending = lifecycle.get_pending_summarisations()
        db.session.commit()
        broadcast_card_refresh(agent_obj, "stop_deferred")
        _execute_pending_summarisations(pending)
        _send_completion_notification(agent_obj, cmd)
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

    # Dedup guard: the TmuxWatchdog reconciler may have already created a
    # turn from this same JSONL content while the deferred stop was sleeping.
    # Check by content hash AND fuzzy matching (same guard as process_stop).
    from .transcript_reconciler import _content_hash, is_content_duplicate
    from ..models.turn import Turn as _Turn

    agent_content_key = _content_hash("agent", full_agent_text or "")
    existing_dup = None
    # Refresh cmd.turns from DB to pick up reconciler-created turns
    db.session.refresh(cmd)
    if full_agent_text and cmd.turns:
        for t in reversed(cmd.turns):
            if t.actor != TurnActor.AGENT:
                continue
            if t.jsonl_entry_hash and t.jsonl_entry_hash == agent_content_key:
                existing_dup = t
                break
            if t.intent in (TurnIntent.QUESTION, TurnIntent.COMPLETION,
                            TurnIntent.END_OF_COMMAND, TurnIntent.PROGRESS):
                if is_content_duplicate(t.text, full_agent_text, actor="agent"):
                    existing_dup = t
                    logger.info(
                        f"[DEFERRED_STOP] dedup: fuzzy match against "
                        f"turn {t.id} (paragraph similarity)"
                    )
                    break

    # Check for stale notification turn to replace
    stale_notification_turn = None
    if cmd.turns:
        for t in reversed(cmd.turns):
            if (t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION
                    and t.text == "Claude is waiting for your input"):
                stale_notification_turn = t
                break

    lifecycle = _get_lifecycle_manager()
    if existing_dup:
        # Reconciler already created this turn — upgrade intent if needed
        if existing_dup.intent == TurnIntent.PROGRESS and intent_result.intent != TurnIntent.PROGRESS:
            existing_dup.intent = intent_result.intent
        if intent_result.intent == TurnIntent.QUESTION:
            existing_dup.question_text = full_agent_text or ""
            existing_dup.question_source_type = "free_text"
        if not existing_dup.jsonl_entry_hash:
            existing_dup.jsonl_entry_hash = agent_content_key
        db.session.commit()
        logger.info(
            f"[DEFERRED_STOP] dedup: reusing existing turn {existing_dup.id} "
            f"(hash={agent_content_key}) instead of creating duplicate"
        )
        # Still drive lifecycle for state-relevant intents
        if intent_result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION):
            try:
                trigger = "hook:stop:deferred_end_of_command" if intent_result.intent == TurnIntent.END_OF_COMMAND else "hook:stop:deferred"
                lifecycle.complete_command(
                    command=cmd, trigger=trigger,
                    agent_text=completion_text, intent=intent_result.intent,
                )
                if completion_text != full_agent_text:
                    cmd.full_output = full_agent_text
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.debug(
                    f"[DEFERRED_STOP] dedup lifecycle (expected if already complete): {e}"
                )
    elif intent_result.intent == TurnIntent.QUESTION:
        if stale_notification_turn:
            stale_notification_turn.text = full_agent_text
            stale_notification_turn.question_text = full_agent_text
            stale_notification_turn.question_source_type = "free_text"
        else:
            turn = _Turn(
                command_id=cmd.id, actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION, text=full_agent_text,
                question_text=full_agent_text,
                question_source_type="free_text",
                jsonl_entry_hash=agent_content_key,
            )
            db.session.add(turn)
    elif intent_result.intent == TurnIntent.END_OF_COMMAND:
        if stale_notification_turn:
            stale_notification_turn.text = completion_text or ""
            stale_notification_turn.intent = TurnIntent.END_OF_COMMAND
            stale_notification_turn.question_text = None
            stale_notification_turn.question_source_type = None
            stale_notification_turn.jsonl_entry_hash = agent_content_key
        lifecycle.complete_command(
            command=cmd, trigger="hook:stop:deferred_end_of_command",
            agent_text=completion_text, intent=TurnIntent.END_OF_COMMAND,
        )
        if completion_text != full_agent_text:
            cmd.full_output = full_agent_text
    else:
        if stale_notification_turn:
            stale_notification_turn.text = completion_text or ""
            stale_notification_turn.intent = TurnIntent.COMPLETION
            stale_notification_turn.question_text = None
            stale_notification_turn.question_source_type = None
            stale_notification_turn.jsonl_entry_hash = agent_content_key
        lifecycle.complete_command(command=cmd, trigger="hook:stop:deferred", agent_text=completion_text)
        if completion_text != full_agent_text:
            cmd.full_output = full_agent_text

    # Commit turn FIRST — turn must survive even if state transition fails.
    _trigger_priority_scoring()
    pending = lifecycle.get_pending_summarisations()
    db.session.commit()

    # Now attempt state transition for QUESTION intent in a separate commit scope.
    # complete_command handles its own transitions advisorily (doesn't raise).
    if intent_result.intent == TurnIntent.QUESTION:
        try:
            lifecycle.update_command_state(
                command=cmd, to_state=CommandState.AWAITING_INPUT,
                trigger="hook:stop:deferred_question", confidence=intent_result.confidence,
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(
                f"[DEFERRED_STOP] state transition failed: "
                f"error={e} — turn preserved"
            )
    broadcast_card_refresh(agent_obj, "stop_deferred")
    _execute_pending_summarisations(pending)

    if cmd.state == CommandState.COMPLETE:
        _send_completion_notification(agent_obj, cmd)
    # Broadcast agent turn for all intent types (voice chat needs this)
    if cmd.turns:
        broadcast_turn = None
        for t in reversed(cmd.turns):
            if t.actor == TurnActor.AGENT and t.intent in (
                TurnIntent.QUESTION, TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND,
            ):
                broadcast_turn = t
                break
        if not broadcast_turn:
            for t in reversed(cmd.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.PROGRESS and t.text:
                    broadcast_turn = t
                    break
        if broadcast_turn:
            _broadcast_turn_created(
                agent_obj, broadcast_turn.text, cmd,
                tool_input=broadcast_turn.tool_input, turn_id=broadcast_turn.id,
                intent=broadcast_turn.intent.value,
                question_source_type=broadcast_turn.question_source_type,
            )

    logger.info(
        f"deferred_stop: agent_id={agent_id}, "
        f"new_state={cmd.state.value}, intent={intent_result.intent.value}"
    )
