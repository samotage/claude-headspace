"""Hook receiver service for Claude Code lifecycle events.

Processes incoming hook events and translates them into command state transitions
via CommandLifecycleManager, with SSE broadcasting and OS notifications.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple

from sqlalchemy.exc import IntegrityError

from ..database import db
from ..models.agent import Agent
from ..models.command import CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from .card_state import broadcast_card_refresh as _card_state_broadcast
from .hook_agent_state import get_agent_hook_state
from .hook_extractors import (
    capture_plan_write as _capture_plan_write,
    extract_question_text as _extract_question_text,
    extract_structured_options as _extract_structured_options,
    mark_question_answered as _mark_question_answered,
    synthesize_permission_options as _synthesize_permission_options,
)
from .intent_detector import detect_agent_intent
from .command_lifecycle import CommandLifecycleManager, TurnProcessingResult, get_instruction_for_notification
from .guardrail_sanitiser import contains_error_patterns, sanitise_error_output
from .team_content_detector import filter_skill_expansion, is_persona_injection, is_skill_expansion, is_team_internal_content

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
        elapsed = (datetime.now(timezone.utc) - agent.context_updated_at).total_seconds()
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


# Tools where post_tool_use should NOT resume from AWAITING_INPUT
# because user interaction happens AFTER the tool completes.
# NOTE: AskUserQuestion is intentionally excluded — its post_tool_use
# fires AFTER the user answers the dialog, so we should resume to PROCESSING.
# ExitPlanMode is different: post_tool_use fires after the plan is shown
# but BEFORE the user approves/rejects (approval comes as a new user prompt).
USER_INTERACTIVE_TOOLS = {"ExitPlanMode"}

# Tools where pre_tool_use should transition to AWAITING_INPUT
# (user interaction happens AFTER the tool completes, not via permission_request)
PRE_TOOL_USE_INTERACTIVE = {"AskUserQuestion", "ExitPlanMode"}

# Don't infer a new command from post_tool_use if the previous command
# completed less than this many seconds ago (tail-end tool activity).
INFERRED_COMMAND_COOLDOWN_SECONDS = 30

# ── Inlined helper functions ─────────────────────────────────────────
# Formerly in hook_helpers.py — thin wrappers around Flask app extensions.


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


def _broadcast_state_change(agent: Agent, event_type: str, new_state: str, message: str | None = None) -> None:
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


def _broadcast_turn_created(agent: Agent, text: str, command, tool_input: dict | None = None, turn_id: int | None = None, intent: str = "question", question_source_type: str | None = None) -> None:
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
            state.set_transcript_position(agent.id, os.path.getsize(agent.transcript_path))
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
        if entry.role == "assistant" and entry.content and len(entry.content.strip()) >= MIN_PROGRESS_LEN:
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
            get_broadcaster().broadcast("turn_created", {
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
            })
        except Exception as e:
            logger.warning(f"Progress turn broadcast failed: {e}")

    logger.info(
        f"progress_capture: agent_id={agent.id}, command_id={current_command.id}, "
        f"new_turns={len(progress_entries)}, total_captured={len(state.get_progress_texts(agent.id))}"
    )


# ── Per-agent state ──────────────────────────────────────────────────
# All mutable per-agent state is now managed by AgentHookState
# (hook_agent_state.py) with proper thread synchronization.
#
# The following module-level proxy objects are provided for backwards
# compatibility with external callers that import them directly.
# They delegate to get_agent_hook_state() internally.


class _AwaitingToolProxy:
    """Dict-like proxy to AgentHookState._awaiting_tool."""
    def __getitem__(self, agent_id):
        return get_agent_hook_state().get_awaiting_tool(agent_id)

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_awaiting_tool(agent_id, value)

    def __contains__(self, agent_id):
        return get_agent_hook_state().get_awaiting_tool(agent_id) is not None

    def get(self, agent_id, default=None):
        val = get_agent_hook_state().get_awaiting_tool(agent_id)
        return val if val is not None else default

    def pop(self, agent_id, *args):
        return get_agent_hook_state().clear_awaiting_tool(agent_id)

    def clear(self):
        state = get_agent_hook_state()
        with state._lock:
            state._awaiting_tool.clear()

    def __len__(self):
        # Only used by tests checking emptiness
        return 0


class _RespondPendingProxy:
    """Dict-like proxy to AgentHookState._respond_pending."""
    def __getitem__(self, agent_id):
        raise KeyError(agent_id)  # Not needed

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_respond_pending(agent_id)

    def __contains__(self, agent_id):
        state = get_agent_hook_state()
        with state._lock:
            return agent_id in state._respond_pending

    def pop(self, agent_id, *args):
        # consume_respond_pending returns bool, but callers expect timestamp or None
        state = get_agent_hook_state()
        with state._lock:
            return state._respond_pending.pop(agent_id, None if not args else args[0])

    def clear(self):
        state = get_agent_hook_state()
        with state._lock:
            state._respond_pending.clear()

    def __len__(self):
        return 0


class _DeferredStopProxy:
    """Set-like proxy to AgentHookState._deferred_stop_pending."""
    def add(self, agent_id):
        state = get_agent_hook_state()
        with state._lock:
            state._deferred_stop_pending.add(agent_id)

    def discard(self, agent_id):
        get_agent_hook_state().release_deferred_stop(agent_id)

    def __contains__(self, agent_id):
        return get_agent_hook_state().is_deferred_stop_pending(agent_id)

    def clear(self):
        state = get_agent_hook_state()
        with state._lock:
            state._deferred_stop_pending.clear()

    def __len__(self):
        return 0


class _TranscriptPositionsProxy:
    """Dict-like proxy to AgentHookState._transcript_positions."""
    def __getitem__(self, agent_id):
        val = get_agent_hook_state().get_transcript_position(agent_id)
        if val is None:
            raise KeyError(agent_id)
        return val

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_transcript_position(agent_id, value)

    def __contains__(self, agent_id):
        return get_agent_hook_state().get_transcript_position(agent_id) is not None

    def get(self, agent_id, default=None):
        val = get_agent_hook_state().get_transcript_position(agent_id)
        return val if val is not None else default

    def pop(self, agent_id, *args):
        return get_agent_hook_state().clear_transcript_position(agent_id)

    def clear(self):
        pass  # handled by reset


class _ProgressTextsProxy:
    """Dict-like proxy to AgentHookState._progress_texts."""
    def __getitem__(self, agent_id):
        val = get_agent_hook_state().get_progress_texts(agent_id)
        if not val:
            raise KeyError(agent_id)
        return val

    def __setitem__(self, agent_id, value):
        state = get_agent_hook_state()
        with state._lock:
            state._progress_texts[agent_id] = value

    def __contains__(self, agent_id):
        return len(get_agent_hook_state().get_progress_texts(agent_id)) > 0

    def get(self, agent_id, default=None):
        val = get_agent_hook_state().get_progress_texts(agent_id)
        return val if val else default

    def pop(self, agent_id, *args):
        return get_agent_hook_state().consume_progress_texts(agent_id)

    def clear(self):
        pass  # handled by reset


class _FileMetadataPendingProxy:
    """Dict-like proxy to AgentHookState._file_metadata_pending."""
    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_file_metadata_pending(agent_id, value)

    def pop(self, agent_id, *args):
        return get_agent_hook_state().consume_file_metadata_pending(agent_id)

    def clear(self):
        pass  # handled by reset


# Backwards-compatible module-level names (used by external callers)
_awaiting_tool_for_agent = _AwaitingToolProxy()
_respond_pending_for_agent = _RespondPendingProxy()
_deferred_stop_pending = _DeferredStopProxy()
_transcript_positions = _TranscriptPositionsProxy()
_progress_texts_for_agent = _ProgressTextsProxy()
_file_metadata_pending_for_agent = _FileMetadataPendingProxy()


# --- Data types ---

class HookEventType(str, Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    STOP = "stop"
    NOTIFICATION = "notification"
    POST_TOOL_USE = "post_tool_use"
    PRE_TOOL_USE = "pre_tool_use"
    PERMISSION_REQUEST = "permission_request"


class HookMode(str, Enum):
    HOOKS_ACTIVE = "hooks_active"
    POLLING_FALLBACK = "polling_fallback"


class HookEventResult(NamedTuple):
    success: bool
    agent_id: int | None = None
    state_changed: bool = False
    new_state: str | None = None
    error_message: str | None = None


# --- Receiver state ---

@dataclass
class HookReceiverState:
    enabled: bool = True
    last_event_at: datetime | None = None
    last_event_type: HookEventType | None = None
    mode: HookMode = HookMode.POLLING_FALLBACK
    events_received: int = 0
    polling_interval_with_hooks: int = 60
    polling_interval_fallback: int = 2
    fallback_timeout: int = 300
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_event(self, event_type: HookEventType) -> None:
        with self._lock:
            self.last_event_at = datetime.now(timezone.utc)
            self.last_event_type = event_type
            self.events_received += 1
            if self.mode == HookMode.POLLING_FALLBACK:
                self.mode = HookMode.HOOKS_ACTIVE
                logger.info("Hook receiver mode changed to HOOKS_ACTIVE")

    def check_fallback(self) -> None:
        with self._lock:
            if self.mode != HookMode.HOOKS_ACTIVE or self.last_event_at is None:
                return
            elapsed = (datetime.now(timezone.utc) - self.last_event_at).total_seconds()
            if elapsed > self.fallback_timeout:
                self.mode = HookMode.POLLING_FALLBACK
                logger.warning(f"No hook events for {elapsed:.0f}s, reverting to POLLING_FALLBACK")

    def get_polling_interval(self) -> int:
        with self._lock:
            return self.polling_interval_with_hooks if self.mode == HookMode.HOOKS_ACTIVE else self.polling_interval_fallback


_receiver_state = HookReceiverState()


def get_receiver_state() -> HookReceiverState:
    return _receiver_state


def configure_receiver(
    enabled: bool | None = None,
    polling_interval_with_hooks: int | None = None,
    fallback_timeout: int | None = None,
) -> None:
    state = get_receiver_state()
    with state._lock:
        if enabled is not None:
            state.enabled = enabled
        if polling_interval_with_hooks is not None:
            state.polling_interval_with_hooks = polling_interval_with_hooks
        if fallback_timeout is not None:
            state.fallback_timeout = fallback_timeout


def reset_receiver_state() -> None:
    global _receiver_state
    _receiver_state = HookReceiverState()
    get_agent_hook_state().reset()


# --- _capture_progress_text wrapper ---
# _capture_progress_text_impl requires an explicit state parameter.
# This wrapper provides the default AgentHookState for callers within this module.

def _capture_progress_text(agent: Agent, current_command) -> None:
    """Capture progress text from the agent's transcript.

    Previously used a per-agent in-memory lock for serialisation.
    Now relies on the advisory lock held by the hook route caller
    (all 8 hook routes acquire advisory_lock(AGENT, agent.id)).
    """
    state = get_agent_hook_state()
    _capture_progress_text_impl(agent, current_command, state)


# --- Deferred stop handler (INT-H1: non-blocking transcript retry) ---

def _schedule_deferred_stop(agent: Agent, current_command) -> None:
    """Schedule a background thread to retry transcript extraction.

    Delegates to hook_deferred_stop.schedule_deferred_stop().
    """
    from .hook_deferred_stop import schedule_deferred_stop
    schedule_deferred_stop(agent, current_command)


# --- Hook processors ---

def process_session_start(
    agent: Agent,
    claude_session_id: str,
    transcript_path: str | None = None,
    tmux_pane_id: str | None = None,
    tmux_session: str | None = None,
    persona_slug: str | None = None,
    previous_agent_id: str | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_START)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None  # Clear ended state for new session

        # Assign persona to agent by looking up the Persona record by slug
        if persona_slug:
            try:
                from ..models.persona import Persona

                persona = Persona.query.filter_by(slug=persona_slug).first()
                if persona:
                    agent.persona_id = persona.id
                    logger.info(
                        f"session_start: persona assigned — slug={persona_slug}, "
                        f"persona_id={persona.id}, agent_id={agent.id}"
                    )
                else:
                    logger.warning(
                        f"session_start: unrecognised persona_slug={persona_slug}, "
                        f"agent_id={agent.id} — agent created without persona"
                    )
            except Exception as e:
                logger.error(
                    f"session_start: DB error during Persona lookup for "
                    f"slug={persona_slug}, agent_id={agent.id}: {e}"
                )

        # Assign previous_agent_id (convert string from hook payload to int)
        if previous_agent_id:
            try:
                agent.previous_agent_id = int(previous_agent_id)
                logger.info(
                    f"session_start: previous_agent_id={previous_agent_id} "
                    f"set on agent_id={agent.id}"
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"session_start: invalid previous_agent_id={previous_agent_id!r}, "
                    f"agent_id={agent.id}: {e}"
                )
        # Always update transcript_path — context compression creates a new
        # Claude session (and new JSONL file).  The old guard `not agent.transcript_path`
        # caused the agent to read a stale file for the rest of its lifetime.
        if transcript_path:
            agent.transcript_path = transcript_path
        # Track the current Claude session ID so correlator/reconciler use the right file
        if claude_session_id:
            agent.claude_session_id = claude_session_id

        # Reset transcript position tracking for new session
        _transcript_positions.pop(agent.id, None)
        _progress_texts_for_agent.pop(agent.id, None)

        # Store tmux pane ID and register with availability tracker + watchdog
        if tmux_pane_id:
            agent.tmux_pane_id = tmux_pane_id
            try:
                from flask import current_app
                availability = current_app.extensions.get("commander_availability")
                if availability:
                    availability.register_agent(agent.id, tmux_pane_id)
                watchdog = current_app.extensions.get("tmux_watchdog")
                if watchdog:
                    watchdog.register_agent(agent.id, tmux_pane_id)
            except RuntimeError:
                logger.debug("No app context for commander_availability/tmux_watchdog")

        # Store tmux session name for dashboard attach action
        if tmux_session and not agent.tmux_session:
            agent.tmux_session = tmux_session

        db.session.commit()
        broadcast_card_refresh(agent, "session_start")

        # Inject persona skill files for persona-backed agents with a tmux pane
        if agent.persona_id and agent.tmux_pane_id:
            try:
                from .skill_injector import inject_persona_skills

                injected = inject_persona_skills(agent)
                if injected:
                    # Flag the agent so the next user_prompt_submit (the priming
                    # message echoed back by Claude Code) is marked is_internal.
                    get_agent_hook_state().set_skill_injection_pending(agent.id)
            except Exception as e:
                logger.error(
                    f"session_start: skill injection failed for agent_id={agent.id}: {e}"
                )

        # Deliver handoff or revival injection prompt for successor agents.
        # This runs AFTER skill injection so the successor is primed before
        # receiving the handoff/revival context.
        if agent.previous_agent_id and agent.tmux_pane_id:
            try:
                from flask import current_app as _app
                handoff_executor = _app.extensions.get("handoff_executor")
                handoff_delivered = False
                if handoff_executor:
                    injection_result = handoff_executor.deliver_injection_prompt(agent)
                    if injection_result.success:
                        handoff_delivered = True
                        logger.info(
                            f"session_start: handoff injection delivered — "
                            f"agent_id={agent.id}, predecessor_id={agent.previous_agent_id}"
                        )
                    elif injection_result.error_code != "no_handoff_record":
                        # no_handoff_record is expected for non-handoff successors
                        logger.warning(
                            f"session_start: handoff injection failed — "
                            f"agent_id={agent.id}: {injection_result.message}"
                        )

                # Revival injection: if no handoff record exists on the
                # predecessor, this is a revival successor. Inject the
                # revival instruction telling the agent to read its
                # predecessor's transcript.
                if not handoff_delivered:
                    from .revival_service import (
                        compose_revival_instruction,
                        is_revival_successor,
                    )

                    if is_revival_successor(agent):
                        revival_msg = compose_revival_instruction(agent.previous_agent_id)
                        from . import tmux_bridge
                        send_result = tmux_bridge.send_text(
                            agent.tmux_pane_id, revival_msg
                        )
                        if send_result.success:
                            logger.info(
                                f"session_start: revival injection delivered — "
                                f"agent_id={agent.id}, predecessor_id={agent.previous_agent_id}"
                            )
                        else:
                            logger.warning(
                                f"session_start: revival injection failed — "
                                f"agent_id={agent.id}: {send_result.error_message}"
                            )
            except RuntimeError:
                pass  # No app context
            except Exception as e:
                logger.error(
                    f"session_start: handoff/revival injection error for agent_id={agent.id}: {e}"
                )

        # Commit post-injection state (prompt_injected_at) so the
        # idempotency guard survives across requests (e.g. context compression
        # re-triggering session_start for the same agent).
        db.session.commit()

        logger.info(f"hook_event: type=session_start, agent_id={agent.id}, session_id={claude_session_id}")
        return HookEventResult(success=True, agent_id=agent.id, new_state=agent.state.value)
    except Exception as e:
        logger.exception(f"Error processing session_start: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_session_end(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_END)
    try:
        now = datetime.now(timezone.utc)
        logger.warning(
            f"SESSION_END_KILL: agent_id={agent.id} uuid={agent.session_uuid} "
            f"claude_session_id={claude_session_id} "
            f"tmux_pane={agent.tmux_pane_id} project={agent.project.name if agent.project else 'N/A'} "
            f"age={(now - agent.started_at).total_seconds() if agent.started_at else 'N/A'}s"
        )
        agent.last_seen_at = now
        agent.ended_at = now
        _awaiting_tool_for_agent.pop(agent.id, None)  # Clear pending tool tracking
        _transcript_positions.pop(agent.id, None)
        _progress_texts_for_agent.pop(agent.id, None)

        # Clear skill injection idempotency record
        from .skill_injector import clear_injection_record
        clear_injection_record(agent.id)

        # Centralized cache cleanup (correlator, hook_agent_state, commander, watchdog)
        from .session_correlator import invalidate_agent_caches
        invalidate_agent_caches(agent.id, session_id=claude_session_id)
        try:
            from flask import current_app
            watchdog = current_app.extensions.get("tmux_watchdog")
            if watchdog:
                watchdog.unregister_agent(agent.id)
        except RuntimeError:
            pass

        lifecycle = _get_lifecycle_manager()
        current_command = lifecycle.get_current_command(agent)
        if current_command:
            lifecycle.complete_command(current_command, trigger="hook:session_end")
        pending = lifecycle.get_pending_summarisations()

        # Phase 2: Reconcile JSONL transcript to backfill missed turns
        try:
            from .transcript_reconciler import reconcile_agent_session, broadcast_reconciliation
            recon_result = reconcile_agent_session(agent)
            if recon_result["created"]:
                logger.info(
                    f"session_end reconciliation: agent_id={agent.id}, "
                    f"created={len(recon_result['created'])} turns from JSONL"
                )
        except Exception as e:
            recon_result = None
            logger.warning(f"Session-end reconciliation failed: {e}")

        db.session.commit()
        broadcast_card_refresh(agent, "session_end")
        _execute_pending_summarisations(pending)

        # Phase 3: Broadcast reconciliation results after commit
        if recon_result and recon_result.get("created"):
            try:
                broadcast_reconciliation(agent, recon_result)
            except Exception as e:
                logger.warning(f"Session-end reconciliation broadcast failed: {e}")

        _broadcast_state_change(agent, "session_end", CommandState.COMPLETE.value, message="Session ended")
        try:
            from .broadcaster import get_broadcaster
            get_broadcaster().broadcast("session_ended", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "session_uuid": str(agent.session_uuid),
                "timestamp": now.isoformat(),
            })
        except Exception as e:
            logger.warning(f"Session ended broadcast failed: {e}")

        logger.info(f"hook_event: type=session_end, agent_id={agent.id}, session_id={claude_session_id}")
        return HookEventResult(success=True, agent_id=agent.id, state_changed=True, new_state=CommandState.COMPLETE.value)
    except Exception as e:
        logger.exception(f"Error processing session_end: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_user_prompt_submit(
    agent: Agent,
    claude_session_id: str,
    prompt_text: str | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.USER_PROMPT_SUBMIT)
    try:
        # Check if this prompt was already handled by the dashboard respond handler.
        # When a user responds via the tmux bridge, the respond handler creates the
        # turn and transitions AWAITING_INPUT -> PROCESSING.  Claude Code then fires
        # user_prompt_submit for the same text — skip it to avoid a duplicate command.
        # Check if a voice/respond send is in-flight (pre-commit).
        # The voice bridge sets this before tmux send to close the race
        # window between send and respond_pending (set after commit).
        if get_agent_hook_state().is_respond_inflight(agent.id):
            # Skip turn/state work (respond handler already did that), but still
            # initialize transcript position for the new response cycle.  Without
            # this, _capture_progress_text sees position=None on the first
            # post_tool_use, initializes to current file size (past any agent text
            # already written), and that text is permanently orphaned.
            _progress_texts_for_agent.pop(agent.id, None)
            if agent.transcript_path:
                import os
                try:
                    _transcript_positions[agent.id] = os.path.getsize(agent.transcript_path)
                except OSError:
                    _transcript_positions.pop(agent.id, None)
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            broadcast_card_refresh(agent, "user_prompt_submit_respond_inflight")
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=respond_inflight"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        # Use non-consuming check so the flag persists for the full TTL.
        # Slash commands (skills) trigger a second user_prompt_submit when
        # the Skill tool expands the command content — consuming the flag on
        # the first hook would leave the expansion hook unguarded, creating
        # a "COMMAND" bubble with the raw skill definition text.
        if get_agent_hook_state().is_respond_pending(agent.id):
            # Same as respond_inflight: skip turn/state work but initialize
            # transcript position so progress capture works for this cycle.
            _progress_texts_for_agent.pop(agent.id, None)
            if agent.transcript_path:
                import os
                try:
                    _transcript_positions[agent.id] = os.path.getsize(agent.transcript_path)
                except OSError:
                    _transcript_positions.pop(agent.id, None)
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            broadcast_card_refresh(agent, "user_prompt_submit_respond_pending")
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=respond_pending"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        # Filter out system-injected XML messages that aren't real user input.
        # Claude Code injects <task-notification> when background tasks complete,
        # and <system-reminder> for internal plumbing.  These fire the
        # user_prompt_submit hook but should NOT create turns or trigger state
        # transitions — they'd appear as nonsensical "COMMAND" bubbles in chat.
        if prompt_text and (
            "<task-notification>" in prompt_text
            or "<system-reminder>" in prompt_text
        ):
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=system_xml"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        # Filter out Claude Code interruption artifacts from tool use key injection.
        # When the voice bridge sends Down+Enter during an interactive tool,
        # Claude Code may interpret it as a user interruption.
        if prompt_text and "[Request interrupted by user for tool use]" in prompt_text:
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=tool_interruption_artifact"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        # Detect persona injection priming messages by content pattern.
        # When inject_persona_skills() sends a priming message via tmux,
        # Claude Code echoes it back as user_prompt_submit.  We must NOT
        # skip this entirely — a Command + internal Turn must be created
        # so the subsequent stop hook has a command to attach the agent's
        # introduction response to.  Without a command, the introduction
        # text is orphaned and absorbed into the next real command's
        # transcript.  The flag is used at process_turn() to mark the
        # Turn as is_internal so it doesn't appear in voice chat.
        content_is_persona_injection = bool(
            prompt_text and is_persona_injection(prompt_text)
        )
        if content_is_persona_injection:
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, persona_injection_content=true "
                f"(len={len(prompt_text)})"
            )

        # Detect skill expansion content BEFORE filter_skill_expansion truncates
        # it. Mark as is_internal so voice chat suppresses the raw skill .md file.
        content_is_skill_expansion = bool(
            prompt_text and is_skill_expansion(prompt_text)
        )

        # Content deduplication: suppress identical prompts within 30s.
        # Defence-in-depth against Claude Code firing the same hook hundreds
        # of times (e.g. persona injection storm — 395 times in 97 seconds).
        if prompt_text and get_agent_hook_state().is_duplicate_prompt(agent.id, prompt_text):
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=content_dedup "
                f"(len={len(prompt_text)})"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        # Command creation rate limiting: cap blast radius even if dedup misses.
        # Max 5 commands per 10s per agent.
        if get_agent_hook_state().is_command_rate_limited(agent.id):
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.warning(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=command_rate_limited"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        # Filter out skill/command expansion content.  When a user invokes a
        # slash command, Claude Code's Skill tool fires a SECOND
        # user_prompt_submit with the full .md file content.  For voice-bridge
        # commands this is already caught by respond_pending above, but for
        # commands typed directly in the terminal respond_pending is NOT set.
        # This defense-in-depth check prevents the expanded content from
        # creating a spurious COMMAND turn ("command prompt injection").
        if prompt_text and is_skill_expansion(prompt_text):
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=skill_expansion "
                f"(len={len(prompt_text)})"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                state_changed=False, new_state=None,
            )

        agent.last_seen_at = datetime.now(timezone.utc)
        _awaiting_tool_for_agent.pop(agent.id, None)  # Clear pending tool tracking
        _progress_texts_for_agent.pop(agent.id, None)  # New response cycle

        # Initialize transcript position for incremental PROGRESS capture.
        # Set to current file size so post_tool_use only reads NEW content.
        if agent.transcript_path:
            import os
            try:
                _transcript_positions[agent.id] = os.path.getsize(agent.transcript_path)
            except OSError:
                _transcript_positions.pop(agent.id, None)

        lifecycle = _get_lifecycle_manager()

        # Mark any pending question as answered before processing the new turn
        current_command = lifecycle.get_current_command(agent)
        if current_command and current_command.state == CommandState.AWAITING_INPUT:
            _mark_question_answered(current_command)
            # Detect plan approval: resuming from AWAITING_INPUT with plan content
            if current_command.plan_content and not current_command.plan_approved_at:
                current_command.plan_approved_at = datetime.now(timezone.utc)
                logger.info(
                    f"plan_approved: agent_id={agent.id}, command_id={current_command.id}"
                )

        pending_file_meta = _file_metadata_pending_for_agent.pop(agent.id, None)
        # When the upload endpoint set file metadata, it includes a clean
        # display text (_display_text) so the turn stores the user's text
        # rather than the raw tmux text (which has the file path prepended).
        # This lets the frontend dedup match the optimistic bubble text.
        if pending_file_meta and "_display_text" in pending_file_meta:
            prompt_text = pending_file_meta.pop("_display_text")
        # Truncate skill/command expansion content (e.g. /orch:40-test expands
        # to the full .md file).  Must match the same filter in transcript_reconciler.
        prompt_text = filter_skill_expansion(prompt_text)

        # Suppress persona skill injection priming from voice chat.
        # When inject_persona_skills() sends the priming message via tmux,
        # Claude Code echoes it back as a user_prompt_submit.  That turn is
        # system plumbing, not real user input — mark it internal so the
        # voice transcript query filters it out.
        # Two detection layers: flag-based (set during session_start) and
        # content-based (set earlier in this function).
        is_injection = get_agent_hook_state().consume_skill_injection_pending(agent.id)

        # Replace persona injection priming text with a clean label so the
        # dashboard card shows the persona name, not raw guardrails/skill content.
        if is_injection or content_is_persona_injection:
            persona = getattr(agent, "persona", None)
            persona_name = persona.name if persona else "agent"
            prompt_text = f"{persona_name} is ready"

        result = lifecycle.process_turn(
            agent=agent, actor=TurnActor.USER, text=prompt_text,
            file_metadata=pending_file_meta,
            is_internal=is_injection or content_is_persona_injection or content_is_skill_expansion or is_team_internal_content(prompt_text),
        )

        if result.success:
            _trigger_priority_scoring()
            # Record command creation for rate limiting
            if result.new_command_created:
                get_agent_hook_state().record_command_creation(agent.id)

        # Commit turn FIRST — turn must survive even if state transition fails.
        pending = lifecycle.get_pending_summarisations()
        db.session.commit()

        # Now attempt state transition in a separate commit scope.
        # Auto-transition COMMANDED → PROCESSING
        # Use agent:progress trigger because this transition represents the
        # agent starting to work, not the user issuing another command.
        if result.success and result.command and result.command.state == CommandState.COMMANDED:
            try:
                lifecycle.update_command_state(
                    command=result.command, to_state=CommandState.PROCESSING,
                    trigger="agent:progress", confidence=1.0,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_user_prompt_submit state transition failed: "
                    f"error={e} — turn(s) preserved"
                )

        # Broadcast user turn for voice chat IMMEDIATELY after commit —
        # before summarisation and card_refresh so the chat updates first.
        if prompt_text:
            try:
                from .broadcaster import get_broadcaster
                # Find the turn_id for the user turn just created by process_turn
                user_turn_id = None
                if result.command and result.command.turns:
                    for t in reversed(result.command.turns):
                        if t.actor == TurnActor.USER:
                            user_turn_id = t.id
                            break
                get_broadcaster().broadcast("turn_created", {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "text": prompt_text,
                    "actor": "user",
                    "intent": result.intent.intent.value if result.intent else "command",
                    "command_id": result.command.id if result.command else None,
                    "command_instruction": result.command.instruction if result.command else None,
                    "turn_id": user_turn_id,
                    "is_internal": is_injection or content_is_persona_injection or content_is_skill_expansion or is_team_internal_content(prompt_text),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.warning(f"Turn created broadcast failed: {e}")

        # Execute summarisations BEFORE the card refresh so that the
        # instruction (and turn summary) are already persisted when the card
        # JSON is built.  Previously the card refresh fired first, producing
        # a card with instruction=None on line 03.
        _execute_pending_summarisations(pending)
        broadcast_card_refresh(agent, "user_prompt_submit")

        new_state = result.command.state.value if result.command else CommandState.PROCESSING.value
        _broadcast_state_change(agent, "user_prompt_submit", new_state, message=prompt_text)

        logger.info(
            f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={new_state}"
        )
        return HookEventResult(
            success=result.success, agent_id=agent.id,
            state_changed=True, new_state=new_state, error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing user_prompt_submit: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_stop(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.STOP)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Check if this agent has a handoff in progress — if so, delegate
        # to HandoffExecutor for continuation (file verification, DB record,
        # successor creation) instead of normal stop processing.
        try:
            from flask import current_app as _app
            handoff_executor = _app.extensions.get("handoff_executor")
            if handoff_executor and handoff_executor.is_handoff_in_progress(agent.id):
                logger.info(
                    f"hook_event: type=stop, agent_id={agent.id}, "
                    f"handoff_in_progress — delegating to HandoffExecutor"
                )
                handoff_result = handoff_executor.continue_after_stop(agent)
                if handoff_result.success:
                    logger.info(
                        f"hook_event: type=stop, agent_id={agent.id}, "
                        f"handoff continuation complete"
                    )
                else:
                    logger.error(
                        f"hook_event: type=stop, agent_id={agent.id}, "
                        f"handoff continuation failed: {handoff_result.message}"
                    )
                # Whether handoff succeeded or failed, return — don't do
                # normal stop processing for a handoff agent.
                db.session.commit()
                broadcast_card_refresh(agent, "stop")
                return HookEventResult(
                    success=handoff_result.success,
                    agent_id=agent.id,
                    error_message=None if handoff_result.success else handoff_result.message,
                )
        except RuntimeError:
            pass  # No app context — skip handoff check

        lifecycle = _get_lifecycle_manager()
        current_command = lifecycle.get_current_command(agent)
        if not current_command:
            db.session.commit()
            broadcast_card_refresh(agent, "stop")
            logger.info(f"hook_event: type=stop, agent_id={agent.id}, no active command")
            return HookEventResult(success=True, agent_id=agent.id)

        # Guard: if an interactive tool (AskUserQuestion, ExitPlanMode) has
        # already set AWAITING_INPUT via pre_tool_use, the stop hook fires
        # BETWEEN pre_tool_use and post_tool_use while Claude waits for user
        # input.  Processing the transcript here would either create a new
        # Turn without tool_input (shadowing the structured options) or
        # complete the command entirely — both destroy the respond widget.
        if current_command.state == CommandState.AWAITING_INPUT:
            awaiting_tool = _awaiting_tool_for_agent.get(agent.id)
            if awaiting_tool:
                db.session.commit()
                broadcast_card_refresh(agent, "stop")
                logger.info(
                    f"hook_event: type=stop, agent_id={agent.id}, "
                    f"preserved AWAITING_INPUT (active interactive tool: {awaiting_tool})"
                )
                return HookEventResult(
                    success=True, agent_id=agent.id,
                    new_state="AWAITING_INPUT",
                )

        # Extract transcript and detect intent.
        # Claude Code may fire the stop hook before flushing the final assistant
        # response to the JSONL file.  If empty on first read, schedule a
        # deferred re-check on a background thread instead of blocking the
        # Flask request handler.
        agent_text = _extract_transcript_content(agent)
        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"transcript_extracted: len={len(agent_text) if agent_text else 0}, "
            f"empty={not agent_text}"
        )
        if not agent_text:
            # Defer transcript extraction: complete the request now and
            # schedule a background re-check after a short delay.
            _schedule_deferred_stop(agent, current_command)
            db.session.commit()
            broadcast_card_refresh(agent, "stop")
            logger.info(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"transcript empty — deferred re-check scheduled"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                new_state=current_command.state.value,
            )

        # Deduplicate: if PROGRESS turns already captured intermediate text,
        # only include NEW text in the COMPLETION turn to avoid duplicate
        # content in the voice bridge chat.  full_agent_text retains everything
        # for intent detection and command.full_output.
        full_agent_text = agent_text
        captured = _progress_texts_for_agent.pop(agent.id, None)
        completion_text = agent_text
        all_captured_by_progress = False
        if captured:
            pos = _transcript_positions.get(agent.id, 0)
            if pos > 0 and agent.transcript_path:
                from .transcript_reader import read_new_entries_from_position
                new_entries, _ = read_new_entries_from_position(agent.transcript_path, pos)
                new_texts = [
                    e.content.strip() for e in new_entries
                    if e.role == "assistant" and e.content and e.content.strip()
                ]
                if new_texts:
                    completion_text = "\n\n".join(new_texts)
                else:
                    # All text was captured as PROGRESS turns — upgrade
                    # the last PROGRESS turn instead of creating a duplicate.
                    completion_text = full_agent_text
                    all_captured_by_progress = True
            logger.info(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"progress_dedup: captured={len(captured)} turns, "
                f"full_len={len(full_agent_text)}, completion_len={len(completion_text)}"
            )
        _transcript_positions.pop(agent.id, None)

        try:
            from flask import current_app
            inference_service = current_app.extensions.get("inference_service")
        except RuntimeError:
            inference_service = None

        # Use full text for intent detection (completion patterns may be at the end)
        intent_result = detect_agent_intent(
            full_agent_text, inference_service=inference_service,
            project_id=agent.project_id, agent_id=agent.id,
        )

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"transcript_len={len(full_agent_text) if full_agent_text else 0}, "
            f"intent={intent_result.intent.value}, "
            f"confidence={intent_result.confidence}, "
            f"pattern={intent_result.matched_pattern!r}"
        )
        if full_agent_text:
            tail_lines = [l for l in full_agent_text.splitlines() if l.strip()][-5:]
            logger.debug(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"tail_5_lines={tail_lines!r}"
            )

        # Check for stale notification turn to replace (created by
        # notification hook before this stop hook arrived)
        stale_notification_turn = None
        if current_command.turns:
            for t in reversed(current_command.turns):
                if (t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION
                        and t.text == "Claude is waiting for your input"):
                    stale_notification_turn = t
                    break

        from .transcript_reconciler import _content_hash, is_content_duplicate
        agent_content_key = _content_hash("agent", full_agent_text or "")

        # Dedup guard: check if reconciler already created a turn with this
        # content (race condition — JSONL reconciliation can run between the
        # agent's response appearing in the transcript and the stop hook firing).
        existing_dup = None
        if full_agent_text and current_command.turns:
            for t in reversed(current_command.turns):
                if t.actor != TurnActor.AGENT:
                    continue
                # Tier 1: exact hash match
                if t.jsonl_entry_hash and t.jsonl_entry_hash == agent_content_key:
                    existing_dup = t
                    break
                # Tier 2: paragraph-level duck-typing for near-identical content
                # (e.g. minor whitespace/formatting differences between hook and JSONL text)
                if t.intent in (TurnIntent.QUESTION, TurnIntent.COMPLETION,
                                TurnIntent.END_OF_COMMAND, TurnIntent.PROGRESS):
                    if is_content_duplicate(t.text, full_agent_text, actor="agent"):
                        existing_dup = t
                        logger.info(
                            f"[HOOK_RECEIVER] process_stop dedup: fuzzy match against "
                            f"turn {t.id} (paragraph similarity) — skipping duplicate"
                        )
                        break

        if existing_dup:
            # Reconciler already has this turn — update it in-place rather than
            # creating a duplicate. Upgrade intent if the stop hook detected a
            # more specific one (e.g. QUESTION vs PROGRESS).
            if existing_dup.intent == TurnIntent.PROGRESS and intent_result.intent != TurnIntent.PROGRESS:
                existing_dup.intent = intent_result.intent
            if intent_result.intent == TurnIntent.QUESTION:
                existing_dup.question_text = full_agent_text or ""
                existing_dup.question_source_type = "free_text"
            if not existing_dup.jsonl_entry_hash:
                existing_dup.jsonl_entry_hash = agent_content_key
            db.session.commit()
            logger.info(
                f"[HOOK_RECEIVER] process_stop dedup: reusing existing turn {existing_dup.id} "
                f"(hash={agent_content_key}) instead of creating duplicate"
            )
            # Still drive lifecycle for COMPLETION/END_OF_COMMAND — the reconciler
            # may not have driven it (e.g. lifecycle failed on first attempt).
            # complete_command is idempotent via the state machine; if already
            # COMPLETE, the transition fails harmlessly and gets caught below.
            if intent_result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION):
                try:
                    trigger = "hook:stop:end_of_command" if intent_result.intent == TurnIntent.END_OF_COMMAND else "hook:stop"
                    lifecycle.complete_command(
                        command=current_command, trigger=trigger,
                        agent_text=completion_text, intent=intent_result.intent,
                    )
                    if completion_text != full_agent_text:
                        current_command.full_output = full_agent_text
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.debug(
                        f"[HOOK_RECEIVER] process_stop dedup lifecycle (expected if already complete): {e}"
                    )
        elif all_captured_by_progress:
            # All agent text was captured as PROGRESS turns — upgrade the
            # last PROGRESS turn's intent rather than creating a duplicate
            # COMPLETION turn with the same content.
            progress_turns = [
                t for t in current_command.turns
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.PROGRESS
            ]
            if progress_turns:
                last_progress = progress_turns[-1]
                if intent_result.intent != TurnIntent.PROGRESS:
                    last_progress.intent = intent_result.intent
                if intent_result.intent == TurnIntent.QUESTION:
                    last_progress.question_text = full_agent_text or ""
                    last_progress.question_source_type = "free_text"
                if not last_progress.jsonl_entry_hash:
                    last_progress.jsonl_entry_hash = agent_content_key
                db.session.commit()
                logger.info(
                    f"[HOOK_RECEIVER] process_stop: all text captured by PROGRESS — "
                    f"upgraded turn {last_progress.id} to {intent_result.intent.value}"
                )
                if intent_result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION):
                    try:
                        trigger = "hook:stop:end_of_command" if intent_result.intent == TurnIntent.END_OF_COMMAND else "hook:stop"
                        lifecycle.complete_command(
                            command=current_command, trigger=trigger,
                            agent_text=completion_text, intent=intent_result.intent,
                        )
                        if completion_text != full_agent_text:
                            current_command.full_output = full_agent_text
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        logger.debug(
                            f"[HOOK_RECEIVER] process_stop progress-upgrade lifecycle: {e}"
                        )
        elif intent_result.intent == TurnIntent.QUESTION:
            if stale_notification_turn:
                stale_notification_turn.text = full_agent_text or ""
                stale_notification_turn.question_text = full_agent_text or ""
                stale_notification_turn.question_source_type = "free_text"
                stale_notification_turn.jsonl_entry_hash = agent_content_key
            else:
                turn = Turn(
                    command_id=current_command.id, actor=TurnActor.AGENT,
                    intent=TurnIntent.QUESTION, text=full_agent_text or "",
                    question_text=full_agent_text or "",
                    question_source_type="free_text",
                    is_internal=is_team_internal_content(full_agent_text),
                    jsonl_entry_hash=agent_content_key,
                )
                db.session.add(turn)
            # Commit turn FIRST — turn must survive even if state transition fails.
            db.session.commit()
        elif intent_result.intent == TurnIntent.END_OF_COMMAND:
            if stale_notification_turn:
                stale_notification_turn.text = completion_text or ""
                stale_notification_turn.intent = TurnIntent.END_OF_COMMAND
                stale_notification_turn.question_text = None
                stale_notification_turn.question_source_type = None
                stale_notification_turn.jsonl_entry_hash = agent_content_key
            # Commit turn FIRST — turn must survive even if complete_command fails.
            db.session.commit()
            # Now attempt completion in a separate commit scope.
            try:
                lifecycle.complete_command(
                    command=current_command, trigger="hook:stop:end_of_command",
                    agent_text=completion_text, intent=TurnIntent.END_OF_COMMAND,
                )
                # Preserve full output even when completion turn is deduplicated
                if completion_text != full_agent_text:
                    current_command.full_output = full_agent_text
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_stop complete_command (END_OF_COMMAND) failed: "
                    f"error={e} — turn preserved"
                )
        else:
            if stale_notification_turn:
                stale_notification_turn.text = completion_text or ""
                stale_notification_turn.intent = TurnIntent.COMPLETION
                stale_notification_turn.question_text = None
                stale_notification_turn.question_source_type = None
                stale_notification_turn.jsonl_entry_hash = agent_content_key
            # Commit turn FIRST — turn must survive even if complete_command fails.
            db.session.commit()
            # Now attempt completion in a separate commit scope.
            try:
                lifecycle.complete_command(command=current_command, trigger="hook:stop", agent_text=completion_text)
                if completion_text != full_agent_text:
                    current_command.full_output = full_agent_text
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_stop complete_command (COMPLETION) failed: "
                    f"error={e} — turn preserved"
                )

        # Two-commit pattern complete: turns committed above, state transitions
        # (complete_command or QUESTION handling below) in separate commit scopes.
        _trigger_priority_scoring()
        pending = lifecycle.get_pending_summarisations()

        # Now attempt state transition (for QUESTION intent only — complete_command
        # handles its own transitions advisorily and already ran above).
        if intent_result.intent == TurnIntent.QUESTION:
            try:
                lifecycle.update_command_state(
                    command=current_command, to_state=CommandState.AWAITING_INPUT,
                    trigger="hook:stop:question_detected", confidence=intent_result.confidence,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_stop state transition failed: "
                    f"from={current_command.state.value} actor=AGENT intent=QUESTION "
                    f"error={e} — turn preserved"
                )

        # Broadcast agent turn for voice chat IMMEDIATELY after commit —
        # before card_refresh and summarisation so the chat updates first.
        # Summarisation involves blocking LLM calls that can delay turn
        # visibility by several seconds.
        if current_command.turns:
            broadcast_turn = None
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent in (
                    TurnIntent.QUESTION, TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND,
                ):
                    broadcast_turn = t
                    break
            # Fallback: when progress dedup captured all agent text and no
            # COMPLETION turn was created, broadcast the last PROGRESS turn
            # so the voice chat gets the agent's response via SSE.
            if not broadcast_turn:
                for t in reversed(current_command.turns):
                    if t.actor == TurnActor.AGENT and t.intent == TurnIntent.PROGRESS and t.text:
                        broadcast_turn = t
                        break
            if broadcast_turn:
                _broadcast_turn_created(
                    agent, broadcast_turn.text, current_command,
                    tool_input=broadcast_turn.tool_input, turn_id=broadcast_turn.id,
                    intent=broadcast_turn.intent.value,
                    question_source_type=broadcast_turn.question_source_type,
                )

        broadcast_card_refresh(agent, "stop")
        _execute_pending_summarisations(pending)

        actual_state = current_command.state.value
        _broadcast_state_change(agent, "stop", actual_state, message=f"\u2192 {actual_state.upper()}")

        # Send completion notification AFTER summarisation so it contains
        # the AI-generated summary instead of raw transcript text.
        if current_command.state == CommandState.COMPLETE:
            _send_completion_notification(agent, current_command)

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={actual_state}"
        )
        return HookEventResult(
            success=True, agent_id=agent.id,
            state_changed=True, new_state=actual_state,
        )
    except Exception as e:
        logger.exception(f"Error processing stop: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


# --- Awaiting input handlers (pre_tool_use, permission_request, notification) ---

def _handle_awaiting_input(
    agent: Agent,
    event_type_enum: HookEventType,
    event_type_str: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    message: str | None = None,
    title: str | None = None,
) -> HookEventResult:
    """Common handler for hooks that transition to AWAITING_INPUT."""
    state = get_receiver_state()
    state.record_event(event_type_enum)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)
        current_command = agent.get_current_command()

        if not current_command or current_command.state not in (CommandState.PROCESSING, CommandState.COMMANDED):
            db.session.commit()
            broadcast_card_refresh(agent, event_type_str)
            logger.info(f"hook_event: type={event_type_str}, agent_id={agent.id}, ignored (no active processing command)")
            return HookEventResult(success=True, agent_id=agent.id)

        # Flush any pending agent output from the transcript BEFORE creating
        # the question turn. This captures text the agent printed (e.g. plan
        # details, colour palette options, analysis) between the last tool
        # completion and this interactive tool call.
        _capture_progress_text(agent, current_command)

        # Build question text and create turn BEFORE state transition
        question_text = None
        question_turn = None
        structured_options = None
        permission_summary_needed = False
        if tool_name is not None or tool_input is not None:
            # pre_tool_use / permission_request: always create turn
            question_text = _extract_question_text(tool_name, tool_input)
            structured_options = _extract_structured_options(tool_name, tool_input)
            # Determine question source type and voice-friendly options
            q_source_type = None
            q_options = None
            if tool_name == "AskUserQuestion" and structured_options:
                q_source_type = "ask_user_question"
                # Extract normalized options for voice bridge
                questions = structured_options.get("questions", [])
                if questions and isinstance(questions, list) and len(questions) > 1:
                    # Multi-question: store full structure array for rendering
                    q_options = [{
                        "question": qq.get("question", ""),
                        "header": qq.get("header", ""),
                        "multiSelect": qq.get("multiSelect", False),
                        "options": [
                            {"label": o.get("label", ""), "description": o.get("description", "")}
                            for o in qq.get("options", []) if isinstance(o, dict)
                        ],
                    } for qq in questions if isinstance(qq, dict)]
                elif questions and isinstance(questions, list):
                    q = questions[0] if questions else {}
                    opts = q.get("options", [])
                    if opts:
                        q_options = [
                            {"label": o.get("label", ""), "description": o.get("description", "")}
                            for o in opts if isinstance(o, dict)
                        ]
            elif event_type_enum == HookEventType.PERMISSION_REQUEST:
                q_source_type = "permission_request"
            # For ExitPlanMode, synthesize default approval options + attach plan content
            if structured_options is None and tool_name == "ExitPlanMode":
                question_text = "Approve plan and proceed?"
                structured_options = {
                    "questions": [{
                        "question": question_text,
                        "options": [
                            {"label": "Yes", "description": "Approve the plan and begin implementation"},
                            {"label": "No", "description": "Reject and stay in plan mode"},
                        ],
                    }],
                    "source": "exit_plan_mode_default",
                }
                # Attach plan content so the voice chat can display it
                if current_command.plan_content:
                    structured_options["plan_content"] = current_command.plan_content
                    if current_command.plan_file_path:
                        structured_options["plan_file_path"] = current_command.plan_file_path
                q_source_type = "ask_user_question"
                q_options = [
                    {"label": "Yes", "description": "Approve the plan and begin implementation"},
                    {"label": "No", "description": "Reject and stay in plan mode"},
                ]
            # For permission_request, try capturing options + context from the tmux pane
            if structured_options is None and event_type_enum == HookEventType.PERMISSION_REQUEST:
                structured_options = _synthesize_permission_options(agent, tool_name, tool_input)
                # Use the synthesized question text (from permission summarizer) if available
                if structured_options:
                    synth_questions = structured_options.get("questions", [])
                    if synth_questions and synth_questions[0].get("question"):
                        question_text = synth_questions[0]["question"]
                    # Extract options for voice bridge
                    if synth_questions:
                        opts = synth_questions[0].get("options", [])
                        if opts:
                            q_options = [
                                {"label": o.get("label", ""), "description": o.get("description", "")}
                                for o in opts if isinstance(o, dict)
                            ]
                    # Check if LLM fallback needed (generic summary)
                    if question_text and question_text.startswith("Permission:"):
                        permission_summary_needed = True
            if structured_options:
                structured_options["status"] = "pending"
            question_turn = Turn(
                command_id=current_command.id, actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION, text=question_text,
                tool_input=structured_options,
                question_text=question_text,
                question_options=q_options,
                question_source_type=q_source_type,
                is_internal=is_team_internal_content(question_text),
            )
            db.session.add(question_turn)
        elif message or title:
            # Skip turn creation for standard NOTIFICATION hooks — they carry
            # generic text ("Claude is waiting for your input") with no actual
            # response content.  The stop hook creates the proper turn with
            # real transcript text.  State transition + OS notification still fire.
            if event_type_enum == HookEventType.NOTIFICATION:
                pass
            else:
                # Non-notification path (future code paths): dedup against recent turn
                has_recent = False
                if current_command.turns:
                    for t in reversed(current_command.turns):
                        if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                            has_recent = (datetime.now(timezone.utc) - t.timestamp).total_seconds() < 10
                            break
                if not has_recent:
                    question_text = (f"[{title}] " if title else "") + (message or "")
                    question_text = question_text.strip()
                    if question_text:
                        question_turn = Turn(
                            command_id=current_command.id, actor=TurnActor.AGENT,
                            intent=TurnIntent.QUESTION, text=question_text,
                            question_text=question_text,
                            question_source_type="free_text",
                            is_internal=is_team_internal_content(question_text),
                        )
                        db.session.add(question_turn)

        # Track which tool triggered AWAITING_INPUT so post_tool_use only
        # resumes when the matching tool completes (not unrelated tools)
        if tool_name:
            _awaiting_tool_for_agent[agent.id] = tool_name

        # Commit turn FIRST — turn must survive even if state transition fails.
        db.session.commit()

        # Now attempt state transition in a separate commit scope.
        lifecycle = _get_lifecycle_manager()
        try:
            lifecycle.update_command_state(
                current_command, CommandState.AWAITING_INPUT,
                trigger=event_type_str, confidence=1.0,
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(
                f"[HOOK_RECEIVER] _handle_awaiting_input state transition failed: "
                f"error={e} — turn preserved"
            )
        broadcast_card_refresh(agent, event_type_str)

        # Broadcast
        _broadcast_state_change(agent, event_type_str, "AWAITING_INPUT")
        if question_text:
            _broadcast_turn_created(agent, question_text, current_command,
                                    tool_input=structured_options,
                                    turn_id=question_turn.id if question_turn else None,
                                    question_source_type=question_turn.question_source_type if question_turn else None)
        elif current_command.turns:
            # Broadcast existing turn (dedup case: pre_tool_use fired first)
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    _broadcast_turn_created(agent, t.text, current_command, tool_input=t.tool_input, turn_id=t.id,
                                            question_source_type=t.question_source_type)
                    break

        # Queue LLM fallback for generic permission summaries
        if permission_summary_needed and current_command.turns:
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    from .command_lifecycle import SummarisationRequest
                    _execute_pending_summarisations([
                        SummarisationRequest(type="permission_summary", turn=t),
                    ])
                    break

        logger.info(f"hook_event: type={event_type_str}, agent_id={agent.id}, AWAITING_INPUT")
        return HookEventResult(success=True, agent_id=agent.id, state_changed=True, new_state="AWAITING_INPUT")
    except Exception as e:
        logger.exception(f"Error processing {event_type_str}: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_notification(
    agent: Agent,
    claude_session_id: str,
    message: str | None = None,
    title: str | None = None,
    notification_type: str | None = None,
) -> HookEventResult:
    # Filter team-internal XML notifications (sub-agent comms).
    if message and (
        "<task-notification>" in message
        or "<system-reminder>" in message
    ):
        state = get_receiver_state()
        state.record_event(HookEventType.NOTIFICATION)
        agent.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}, skipped=system_xml"
        )
        return HookEventResult(
            success=True, agent_id=agent.id,
            state_changed=False, new_state=None,
        )
    # Filter interruption artifact notifications from tmux key injection.
    if message and "Interruption detected" in message:
        state = get_receiver_state()
        state.record_event(HookEventType.NOTIFICATION)
        agent.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}, skipped=interruption_artifact"
        )
        return HookEventResult(
            success=True, agent_id=agent.id,
            state_changed=False, new_state=None,
        )
    return _handle_awaiting_input(
        agent, HookEventType.NOTIFICATION, "notification",
        message=message, title=title,
    )



def process_pre_tool_use(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    # Only transition to AWAITING_INPUT for known interactive tools
    # (where user interaction happens AFTER the tool completes).
    # For all other tools, pre_tool_use is just activity — no state change.
    if tool_name in PRE_TOOL_USE_INTERACTIVE:
        # Mark plan mode entry before handling the AWAITING_INPUT transition
        if tool_name == "EnterPlanMode":
            try:
                current_command = agent.get_current_command()
                if current_command and not current_command.plan_file_path:
                    current_command.plan_file_path = "pending"
                    # Don't commit yet — _handle_awaiting_input will commit
            except Exception as e:
                logger.warning(f"Failed to mark plan mode entry: {e}")
        return _handle_awaiting_input(
            agent, HookEventType.PRE_TOOL_USE, "pre_tool_use",
            tool_name=tool_name, tool_input=tool_input,
        )

    # Non-interactive tool: lightweight update, but recover stale AWAITING_INPUT.
    # If the agent is running a non-interactive tool, it's clearly not waiting
    # for user input. This recovers from lost post_tool_use hooks (e.g. server
    # restart killed the process before the hook could be received).
    receiver_state = get_receiver_state()
    receiver_state.record_event(HookEventType.PRE_TOOL_USE)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Capture plan file writes (Write to .claude/plans/)
        if tool_name == "Write":
            _capture_plan_write(agent, tool_input)

        current_command = agent.get_current_command()
        if current_command and current_command.state == CommandState.AWAITING_INPUT:
            _mark_question_answered(current_command)
            lifecycle = _get_lifecycle_manager()
            lifecycle.update_command_state(
                command=current_command, to_state=CommandState.PROCESSING,
                trigger="hook:pre_tool_use:stale_awaiting_recovery",
                confidence=0.9,
            )
            _awaiting_tool_for_agent.pop(agent.id, None)
            db.session.commit()
            broadcast_card_refresh(agent, "pre_tool_use_recovery")
            _broadcast_state_change(agent, "pre_tool_use", CommandState.PROCESSING.value)
            logger.info(
                f"hook_event: type=pre_tool_use, agent_id={agent.id}, tool={tool_name}, "
                f"recovered stale AWAITING_INPUT → PROCESSING"
            )
            return HookEventResult(success=True, agent_id=agent.id,
                                   state_changed=True, new_state=CommandState.PROCESSING.value)

        db.session.commit()
        logger.debug(f"hook_event: type=pre_tool_use, agent_id={agent.id}, tool={tool_name}, no state change")
        return HookEventResult(success=True, agent_id=agent.id)
    except Exception as e:
        logger.exception(f"Error processing pre_tool_use: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_permission_request(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    return _handle_awaiting_input(
        agent, HookEventType.PERMISSION_REQUEST, "permission_request",
        tool_name=tool_name, tool_input=tool_input,
    )


def process_post_tool_use(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.POST_TOOL_USE)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Capture plan file writes via post_tool_use (pre_tool_use only fires
        # for interactive tools, so Write hooks are only received here)
        if tool_name == "Write":
            _capture_plan_write(agent, tool_input)

        lifecycle = _get_lifecycle_manager()
        current_command = lifecycle.get_current_command(agent)

        if not current_command:
            # Guard: don't infer a command for ended/reaped agents
            if agent.ended_at is not None:
                db.session.commit()
                broadcast_card_refresh(agent, "post_tool_use")
                logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, skipped (agent ended)")
                return HookEventResult(success=True, agent_id=agent.id)

            # Guard: don't infer a command if the previous one just completed
            # (tail-end tool activity after session_end/stop)
            from ..models.command import Command

            recent_complete = (
                db.session.query(Command)
                .filter(
                    Command.agent_id == agent.id,
                    Command.state == CommandState.COMPLETE,
                    Command.completed_at.isnot(None),
                )
                .order_by(Command.completed_at.desc())
                .first()
            )
            if recent_complete and recent_complete.completed_at:
                elapsed = (datetime.now(timezone.utc) - recent_complete.completed_at).total_seconds()
                if elapsed < INFERRED_COMMAND_COOLDOWN_SECONDS:
                    db.session.commit()
                    broadcast_card_refresh(agent, "post_tool_use")
                    logger.info(
                        f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                        f"skipped inferred command (previous command {recent_complete.id} "
                        f"completed {elapsed:.1f}s ago)"
                    )
                    return HookEventResult(success=True, agent_id=agent.id)

            # No command — infer one from tool use evidence
            new_command = lifecycle.create_command(agent, CommandState.COMMANDED)

            # Defense-in-depth: recover user command from the transcript file.
            # If user_prompt_submit never fires (broken hook, timeout, etc.),
            # this ensures the user's instruction is still captured.
            if agent.transcript_path:
                try:
                    from .transcript_reader import read_last_user_message
                    result = read_last_user_message(agent.transcript_path)
                    if result.success and result.text:
                        new_command.full_command = result.text
                        turn = Turn(
                            command_id=new_command.id,
                            actor=TurnActor.USER,
                            intent=TurnIntent.COMMAND,
                            text=result.text,
                        )
                        db.session.add(turn)
                        db.session.flush()
                        from .command_lifecycle import SummarisationRequest
                        lifecycle._pending_summarisations.append(
                            SummarisationRequest(type="turn", turn=turn)
                        )
                        lifecycle._pending_summarisations.append(
                            SummarisationRequest(type="instruction", command=new_command, command_text=result.text)
                        )
                        logger.info(
                            f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                            f"recovered user command from transcript ({len(result.text)} chars)"
                        )
                except Exception as e:
                    logger.warning(f"Failed to recover user command from transcript: {e}")

            # Commit turn FIRST — turn must survive even if state transition fails.
            _trigger_priority_scoring()
            pending = lifecycle.get_pending_summarisations()
            db.session.commit()

            # Now attempt state transition in a separate commit scope.
            try:
                lifecycle.update_command_state(
                    command=new_command, to_state=CommandState.PROCESSING,
                    trigger="hook:post_tool_use:inferred", confidence=0.9,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_post_tool_use inferred command state transition failed: "
                    f"error={e} — turn(s) preserved"
                )

            broadcast_card_refresh(agent, "post_tool_use_inferred")
            _execute_pending_summarisations(pending)
            _broadcast_state_change(agent, "post_tool_use", CommandState.PROCESSING.value)
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, inferred PROCESSING command_id={new_command.id}")
            return HookEventResult(success=True, agent_id=agent.id, state_changed=True, new_state=CommandState.PROCESSING.value)

        if current_command.state == CommandState.AWAITING_INPUT and tool_name in USER_INTERACTIVE_TOOLS:
            # ExitPlanMode fires post_tool_use after showing the plan but before the
            # user approves/rejects — preserve AWAITING_INPUT until user_prompt_submit
            db.session.commit()
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                        f"preserved AWAITING_INPUT for interactive tool {tool_name}")
            return HookEventResult(success=True, agent_id=agent.id,
                                   new_state=CommandState.AWAITING_INPUT.value)

        if current_command.state == CommandState.AWAITING_INPUT:
            # Only resume if the completing tool matches the one that triggered
            # AWAITING_INPUT. Otherwise a parallel/unrelated tool completion
            # would incorrectly clear the pending user interaction.
            awaiting_tool = _awaiting_tool_for_agent.get(agent.id)
            if awaiting_tool and tool_name != awaiting_tool:
                # Different tool completed — preserve AWAITING_INPUT.
                # Don't broadcast card_refresh here: nothing changed, and doing so
                # floods the SSE stream when an agent uses many tools while a
                # user-interactive tool (AskUserQuestion) is pending.
                db.session.commit()
                logger.info(
                    f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                    f"preserved AWAITING_INPUT (awaiting={awaiting_tool}, got={tool_name})"
                )
                return HookEventResult(success=True, agent_id=agent.id,
                                       new_state=CommandState.AWAITING_INPUT.value)

            # Resume: matching tool completed (or no tracking) — user answered
            _mark_question_answered(current_command)
            _awaiting_tool_for_agent.pop(agent.id, None)
            # Detect plan approval via post_tool_use resume
            if current_command.plan_content and not current_command.plan_approved_at:
                current_command.plan_approved_at = datetime.now(timezone.utc)
                logger.info(f"plan_approved: agent_id={agent.id}, command_id={current_command.id} (post_tool_use)")
            result = lifecycle.process_turn(agent=agent, actor=TurnActor.USER, text=None)
            if result.success:
                _trigger_priority_scoring()
            pending = lifecycle.get_pending_summarisations()
            db.session.commit()
            broadcast_card_refresh(agent, "post_tool_use_resume")
            _execute_pending_summarisations(pending)
            new_state = result.command.state.value if result.command else None
            if new_state == CommandState.PROCESSING.value:
                _broadcast_state_change(
                    agent, "post_tool_use", CommandState.PROCESSING.value,
                    message=f"Tool: {tool_name}" if tool_name else None,
                )
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, resumed from AWAITING_INPUT")
            return HookEventResult(
                success=result.success, agent_id=agent.id,
                state_changed=new_state == CommandState.PROCESSING.value if new_state else False,
                new_state=new_state, error_message=result.error,
            )

        # Already PROCESSING/COMMANDED — capture intermediate PROGRESS text
        _capture_progress_text(agent, current_command)
        db.session.commit()
        logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, progress_capture (state={current_command.state.value})")
        return HookEventResult(success=True, agent_id=agent.id, new_state=current_command.state.value)
    except Exception as e:
        logger.exception(f"Error processing post_tool_use: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
