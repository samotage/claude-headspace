"""Shared helper functions for hook receiver handlers.

Thin wrappers around Flask app extensions and utility functions used by
multiple hook handler modules and by hook_deferred_stop.py.

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from ..database import (
    db,  # noqa: F401 — re-exported for handler modules + test patching
)
from ..models.agent import Agent
from ..models.turn import Turn, TurnActor, TurnIntent
from .card_state import broadcast_card_refresh as _card_state_broadcast
from .command_lifecycle import (
    CommandLifecycleManager,
    get_instruction_for_notification,
)
from .guardrail_sanitiser import contains_error_patterns, sanitise_error_output
from .hook_agent_state import get_agent_hook_state
from .intent_detector import (
    detect_agent_intent,  # noqa: F401 — re-exported for test patching
)
from .team_content_detector import is_team_internal_content

logger = logging.getLogger(__name__)


def _fetch_context_opportunistically(agent):
    """Update agent's context columns from tmux pane if stale (>15s)."""
    if not agent.tmux_pane_id or agent.ended_at is not None:
        return
    try:
        from flask import current_app

        config = current_app.config.get("APP_CONFIG", {})
        if not config.get("context_monitor", {}).get("enabled", True):
            return
    except RuntimeError:
        return
    if agent.context_updated_at:
        elapsed = (
            datetime.now(timezone.utc) - agent.context_updated_at
        ).total_seconds()
        if elapsed < 15:
            return
    from . import tmux_bridge
    from .context_parser import parse_context_usage

    pane_text = tmux_bridge.capture_pane(agent.tmux_pane_id, lines=5)
    if not pane_text:
        return
    ctx = parse_context_usage(pane_text)
    if ctx:
        agent.context_percent_used = ctx["percent_used"]
        agent.context_remaining_tokens = ctx["remaining_tokens"]
        agent.context_updated_at = datetime.now(timezone.utc)


def broadcast_card_refresh(agent, reason):
    """Wrapper: opportunistic context fetch + card refresh broadcast."""
    _fetch_context_opportunistically(agent)
    _card_state_broadcast(agent, reason)


def _get_lifecycle_manager():
    """Create a CommandLifecycleManager with the current app's event writer."""
    event_writer = None
    try:
        from flask import current_app

        event_writer = current_app.extensions.get("event_writer")
    except RuntimeError:
        logger.debug("No app context for event_writer")
    return CommandLifecycleManager(
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


def _broadcast_state_change(
    agent: Agent, event_type: str, new_state: str, message: str | None = None
) -> None:
    """Broadcast a state_changed SSE event."""
    try:
        from .broadcaster import get_broadcaster

        get_broadcaster().broadcast(
            "state_changed",
            {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "project_name": agent.project.name if agent.project else None,
                "agent_session": str(agent.session_uuid),
                "event_type": event_type,
                "new_state": new_state.upper()
                if isinstance(new_state, str)
                else new_state,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.warning(f"State change broadcast failed: {e}")


def _broadcast_turn_created(
    agent: Agent,
    text: str,
    command,
    tool_input: dict | None = None,
    turn_id: int | None = None,
    intent: str = "question",
    question_source_type: str | None = None,
) -> None:
    """Broadcast a turn_created SSE event."""
    try:
        from .broadcaster import get_broadcaster

        payload = {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": text,
            "actor": "agent",
            "intent": intent,
            "command_id": command.id if command else None,
            "command_instruction": command.instruction if command else None,
            "turn_id": turn_id,
            "is_internal": is_team_internal_content(text),
            "question_source_type": question_source_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_input:
            payload["tool_input"] = tool_input
        get_broadcaster().broadcast("turn_created", payload)
    except Exception as e:
        logger.warning(f"Turn created broadcast failed: {e}")


def _send_notification(agent: Agent, command, turn_text: str | None) -> None:
    """Send an OS notification for awaiting input."""
    try:
        from .notification_service import get_notification_service

        svc = get_notification_service()
        svc.notify_awaiting_input(
            agent_id=str(agent.id),
            agent_name=agent.name or f"Agent {agent.id}",
            project=agent.project.name if agent.project else None,
            command_instruction=get_instruction_for_notification(command),
            turn_text=turn_text,
        )
    except Exception as e:
        logger.warning(f"Notification send failed: {e}")


def _send_completion_notification(agent: Agent, command) -> None:
    """Send command-complete notification using AI-generated summaries."""
    try:
        from .notification_service import get_notification_service

        svc = get_notification_service()
        svc.notify_command_complete(
            agent_id=str(agent.id),
            agent_name=agent.name or f"Agent {agent.id}",
            project=agent.project.name if agent.project else None,
            command_instruction=get_instruction_for_notification(command),
            turn_text=command.completion_summary or None,
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


def _capture_progress_text_impl(agent: Agent, current_command, state) -> None:
    """Read new transcript entries and create PROGRESS turns for intermediate agent text."""
    if not agent.transcript_path:
        return

    import os

    from .transcript_reader import read_new_entries_from_position

    if state.get_transcript_position(agent.id) is None:
        try:
            state.set_transcript_position(
                agent.id, os.path.getsize(agent.transcript_path)
            )
        except OSError:
            return
        return

    pos = state.get_transcript_position(agent.id)
    try:
        entries, new_pos = read_new_entries_from_position(agent.transcript_path, pos)
    except Exception as e:
        logger.debug(f"Progress capture failed for agent {agent.id}: {e}")
        return

    if new_pos == pos:
        return

    state.set_transcript_position(agent.id, new_pos)

    MIN_PROGRESS_LEN = 10
    progress_entries = []
    for entry in entries:
        if (
            entry.role == "assistant"
            and entry.content
            and len(entry.content.strip()) >= MIN_PROGRESS_LEN
        ):
            progress_entries.append(entry)

    if not progress_entries:
        return

    from .transcript_reconciler import _content_hash

    # Determine if this agent has guardrails (remote agent) — if so,
    # sanitise any error output to prevent system detail leakage.
    has_guardrails = getattr(agent, "guardrails_version_hash", None) is not None

    for entry in progress_entries:
        text = entry.content.strip()

        # Sanitise error output for guardrail-protected agents
        if has_guardrails and contains_error_patterns(text):
            text = sanitise_error_output(text)

        content_key = _content_hash("agent", text)

        # Skip if reconciler already created this turn (race condition guard)
        existing = Turn.query.filter_by(
            command_id=current_command.id,
            actor=TurnActor.AGENT,
            jsonl_entry_hash=content_key,
        ).first()
        if existing:
            state.append_progress_text(agent.id, text)
            continue

        state.append_progress_text(agent.id, text)

        internal = is_team_internal_content(text)
        turn = Turn(
            command_id=current_command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text=text,
            timestamp=entry.timestamp or datetime.now(timezone.utc),
            timestamp_source="jsonl" if entry.timestamp else "server",
            is_internal=internal,
            jsonl_entry_hash=content_key,
        )
        db.session.add(turn)
        # Commit PROGRESS turn immediately — turn must survive even if the
        # caller's subsequent operations (state transitions, etc.) fail.
        try:
            db.session.commit()
        except IntegrityError:
            # Belt-and-suspenders: DB unique constraint caught a duplicate
            # that slipped past the application-level check (e.g. race
            # between the per-agent lock and a background reconciler).
            db.session.rollback()
            logger.info(
                f"progress_capture: duplicate hash {content_key} for "
                f"command {current_command.id} — caught by DB constraint"
            )
            continue

        try:
            from .broadcaster import get_broadcaster

            get_broadcaster().broadcast(
                "turn_created",
                {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "text": text,
                    "actor": "agent",
                    "intent": "progress",
                    "command_id": current_command.id,
                    "command_instruction": current_command.instruction,
                    "turn_id": turn.id,
                    "is_internal": internal,
                    "timestamp": turn.timestamp.isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Progress turn broadcast failed: {e}")

    logger.info(
        f"progress_capture: agent_id={agent.id}, command_id={current_command.id}, "
        f"new_turns={len(progress_entries)}, total_captured={len(state.get_progress_texts(agent.id))}"
    )


def _capture_progress_text(agent: Agent, current_command) -> None:
    """Capture progress text from the agent's transcript.

    Previously used a per-agent in-memory lock for serialisation.
    Now relies on the advisory lock held by the hook route caller
    (all 8 hook routes acquire advisory_lock(AGENT, agent.id)).
    """
    state = get_agent_hook_state()
    _capture_progress_text_impl(agent, current_command, state)


def _schedule_deferred_stop(agent: Agent, current_command) -> None:
    """Schedule a background thread to retry transcript extraction.

    Delegates to hook_deferred_stop.schedule_deferred_stop().
    """
    from .hook_deferred_stop import schedule_deferred_stop

    schedule_deferred_stop(agent, current_command)
