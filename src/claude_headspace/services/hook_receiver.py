"""Hook receiver service for Claude Code lifecycle events.

Processes incoming hook events and translates them into task state transitions
via TaskLifecycleManager, with SSE broadcasting and OS notifications.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple

from ..database import db
from ..models.agent import Agent
from ..models.task import TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from .card_state import broadcast_card_refresh
from .intent_detector import detect_agent_intent
from .task_lifecycle import TaskLifecycleManager, TurnProcessingResult, get_instruction_for_notification

logger = logging.getLogger(__name__)

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

# Don't infer a new task from post_tool_use if the previous task
# completed less than this many seconds ago (tail-end tool activity).
INFERRED_TASK_COOLDOWN_SECONDS = 30

# Track which tool triggered AWAITING_INPUT per agent, so post_tool_use
# only resumes when the matching tool completes (not unrelated tools).
_awaiting_tool_for_agent: dict[int, str | None] = {}


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
    _awaiting_tool_for_agent.clear()


# --- Internal helpers ---

def _get_lifecycle_manager() -> TaskLifecycleManager:
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
    try:
        from flask import current_app
        service = current_app.extensions.get("priority_scoring_service")
        if service:
            service.trigger_scoring()
    except Exception as e:
        logger.warning(f"Priority scoring trigger failed: {e}")


def _broadcast_state_change(agent: Agent, event_type: str, new_state: str, message: str | None = None) -> None:
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


def _broadcast_turn_created(agent: Agent, text: str, task, tool_input: dict | None = None) -> None:
    try:
        from .broadcaster import get_broadcaster
        payload = {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": text,
            "actor": "agent",
            "intent": "question",
            "task_id": task.id if task else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_input:
            payload["tool_input"] = tool_input
        get_broadcaster().broadcast("turn_created", payload)
    except Exception as e:
        logger.warning(f"Turn created broadcast failed: {e}")


def _extract_question_text(tool_name: str | None, tool_input: dict | None) -> str:
    if tool_input and isinstance(tool_input, dict):
        questions = tool_input.get("questions")
        if questions and isinstance(questions, list) and len(questions) > 0:
            q = questions[0]
            if isinstance(q, dict) and q.get("question"):
                return q["question"]
        # Non-AskUserQuestion tool_input with raw params (e.g. {"command": "..."})
        # Use permission summarizer for a meaningful description
        if tool_name and tool_name != "AskUserQuestion" and not questions:
            from .permission_summarizer import summarize_permission_command
            return summarize_permission_command(tool_name, tool_input)
    if tool_name:
        return f"Permission needed: {tool_name}"
    return "Awaiting input"


def _extract_structured_options(tool_name: str | None, tool_input: dict | None) -> dict | None:
    """Extract structured AskUserQuestion data for storage in Turn.tool_input.

    Returns the full tool_input dict when the tool is AskUserQuestion and
    contains valid questions with options. Returns None otherwise.
    """
    if tool_name != "AskUserQuestion" or not tool_input or not isinstance(tool_input, dict):
        return None
    questions = tool_input.get("questions")
    if not questions or not isinstance(questions, list) or len(questions) == 0:
        return None
    q = questions[0]
    if not isinstance(q, dict) or not q.get("options"):
        return None
    return tool_input


def _synthesize_permission_options(
    agent: Agent,
    tool_name: str | None,
    tool_input: dict | None,
) -> dict | None:
    """Capture permission dialog context from tmux pane and build AskUserQuestion-compatible dict.

    When a permission-request hook fires, the actual numbered options (e.g. "1. Yes / 2. No")
    are rendered in the terminal but not included in the hook payload. This function captures
    the tmux pane content, parses the options and command context, and wraps them in the same
    format that AskUserQuestion uses so the existing button-rendering pipeline works unchanged.

    Also generates a meaningful summary (e.g. "Bash: curl from localhost:5055") instead of
    the generic "Permission needed: Bash" using pattern matching on the tool_input.

    Returns None if the agent has no tmux_pane_id or if capture/parse fails.
    """
    if not agent.tmux_pane_id:
        return None

    try:
        from . import tmux_bridge
        pane_context = tmux_bridge.capture_permission_context(agent.tmux_pane_id)
    except Exception as e:
        logger.warning(f"Permission context capture failed for agent {agent.id}: {e}")
        return None

    if not pane_context:
        return None

    options = pane_context.get("options")
    if not options:
        return None

    # Generate meaningful summary using permission summarizer
    from .permission_summarizer import summarize_permission_command, classify_safety
    question_text = summarize_permission_command(tool_name, tool_input, pane_context)
    safety = classify_safety(tool_name, tool_input)

    # Build command context for future auto-responder
    command_context = {}
    if pane_context.get("command"):
        command_context["command"] = pane_context["command"]
    if pane_context.get("description"):
        command_context["description"] = pane_context["description"]

    result = {
        "questions": [{
            "question": question_text,
            "options": options,
        }],
        "source": "permission_pane_capture",
        "safety": safety,
    }
    if command_context:
        result["command_context"] = command_context

    return result


def _execute_pending_summarisations(pending: list) -> None:
    if not pending:
        return
    try:
        from flask import current_app
        service = current_app.extensions.get("summarisation_service")
        if service:
            service.execute_pending(pending, db.session)
    except Exception as e:
        logger.warning(f"Post-commit summarisation failed (non-fatal): {e}")


def _extract_transcript_content(agent: Agent) -> str:
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


def _send_notification(agent: Agent, task, turn_text: str | None) -> None:
    try:
        from .notification_service import get_notification_service
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


def _send_completion_notification(agent: Agent, task) -> None:
    """Send task-complete notification using AI-generated summaries.

    Called AFTER summarisation so task.completion_summary and task.instruction
    are populated with useful content instead of raw transcript text.
    """
    try:
        from .notification_service import get_notification_service
        svc = get_notification_service()

        instruction = get_instruction_for_notification(task)
        # Prefer AI-generated completion summary over raw transcript
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


# --- Deferred stop handler (INT-H1: non-blocking transcript retry) ---

def _schedule_deferred_stop(agent: Agent, current_task) -> None:
    """Schedule a background thread to retry transcript extraction after a delay.

    Instead of blocking the Flask request handler with time.sleep(), this
    spawns a daemon thread that waits, re-reads the transcript, and applies
    the appropriate state transition within a fresh app context.
    """
    agent_id = agent.id
    task_id = current_task.id
    project_id = agent.project_id

    def _deferred_check():
        import time
        time.sleep(1.5)  # Wait for Claude Code to flush transcript

        try:
            from flask import current_app
            app = current_app._get_current_object()
        except RuntimeError:
            # No app context — try to get it from the agent's module
            logger.warning("Deferred stop: no app context, skipping re-check")
            return

        with app.app_context():
            try:
                from ..models.task import Task
                task = db.session.get(Task, task_id)
                if not task or task.state == TaskState.COMPLETE:
                    return  # Already completed by another hook

                agent_obj = db.session.get(Agent, agent_id)
                if not agent_obj:
                    return

                agent_text = _extract_transcript_content(agent_obj)
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

                try:
                    from flask import current_app as _ca
                    inference_service = _ca.extensions.get("inference_service")
                except RuntimeError:
                    inference_service = None

                intent_result = detect_agent_intent(
                    agent_text, inference_service=inference_service,
                    project_id=project_id, agent_id=agent_id,
                )

                lifecycle = _get_lifecycle_manager()
                if intent_result.intent == TurnIntent.QUESTION:
                    from ..models.turn import Turn as _Turn
                    turn = _Turn(
                        task_id=task.id, actor=TurnActor.AGENT,
                        intent=TurnIntent.QUESTION, text=agent_text,
                    )
                    db.session.add(turn)
                    lifecycle.update_task_state(
                        task=task, to_state=TaskState.AWAITING_INPUT,
                        trigger="hook:stop:deferred_question", confidence=intent_result.confidence,
                    )
                elif intent_result.intent == TurnIntent.END_OF_TASK:
                    lifecycle.complete_task(
                        task=task, trigger="hook:stop:deferred_end_of_task",
                        agent_text=agent_text, intent=TurnIntent.END_OF_TASK,
                    )
                else:
                    lifecycle.complete_task(task=task, trigger="hook:stop:deferred", agent_text=agent_text)

                _trigger_priority_scoring()
                pending = lifecycle.get_pending_summarisations()
                db.session.commit()
                broadcast_card_refresh(agent_obj, "stop_deferred")
                _execute_pending_summarisations(pending)

                if task.state == TaskState.COMPLETE:
                    _send_completion_notification(agent_obj, task)
                if task.state == TaskState.AWAITING_INPUT and task.turns:
                    for t in reversed(task.turns):
                        if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                            _broadcast_turn_created(agent_obj, t.text, task, tool_input=t.tool_input)
                            break

                logger.info(
                    f"deferred_stop: agent_id={agent_id}, "
                    f"new_state={task.state.value}, intent={intent_result.intent.value}"
                )
            except Exception as e:
                logger.exception(f"deferred_stop failed for agent {agent_id}: {e}")
                try:
                    db.session.rollback()
                except Exception:
                    pass

    t = threading.Thread(target=_deferred_check, daemon=True, name=f"deferred-stop-{agent_id}")
    t.start()


# --- Hook processors ---

def process_session_start(
    agent: Agent,
    claude_session_id: str,
    transcript_path: str | None = None,
    tmux_pane_id: str | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_START)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None  # Clear ended state for new session
        if transcript_path and not agent.transcript_path:
            agent.transcript_path = transcript_path

        # Store tmux pane ID and register with availability tracker
        if tmux_pane_id:
            agent.tmux_pane_id = tmux_pane_id
            try:
                from flask import current_app
                availability = current_app.extensions.get("commander_availability")
                if availability:
                    availability.register_agent(agent.id, tmux_pane_id)
            except RuntimeError:
                logger.debug("No app context for commander_availability")

        db.session.commit()
        broadcast_card_refresh(agent, "session_start")
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
        agent.last_seen_at = now
        agent.ended_at = now
        _awaiting_tool_for_agent.pop(agent.id, None)  # Clear pending tool tracking

        lifecycle = _get_lifecycle_manager()
        current_task = lifecycle.get_current_task(agent)
        if current_task:
            lifecycle.complete_task(current_task, trigger="hook:session_end")
        pending = lifecycle.get_pending_summarisations()

        db.session.commit()
        broadcast_card_refresh(agent, "session_end")
        _execute_pending_summarisations(pending)

        _broadcast_state_change(agent, "session_end", TaskState.COMPLETE.value, message="Session ended")
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
        return HookEventResult(success=True, agent_id=agent.id, state_changed=True, new_state=TaskState.COMPLETE.value)
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
        agent.last_seen_at = datetime.now(timezone.utc)
        _awaiting_tool_for_agent.pop(agent.id, None)  # Clear pending tool tracking

        lifecycle = _get_lifecycle_manager()
        result = lifecycle.process_turn(agent=agent, actor=TurnActor.USER, text=prompt_text)

        # Auto-transition COMMANDED → PROCESSING
        if result.success and result.task and result.task.state == TaskState.COMMANDED:
            lifecycle.update_task_state(
                task=result.task, to_state=TaskState.PROCESSING,
                trigger="hook:user_prompt_submit", confidence=1.0,
            )

        if result.success:
            _trigger_priority_scoring()

        pending = lifecycle.get_pending_summarisations()
        db.session.commit()
        # Execute summarisations BEFORE the first card refresh so that the
        # instruction (and turn summary) are already persisted when the card
        # JSON is built.  Previously the card refresh fired first, producing
        # a card with instruction=None on line 03.
        _execute_pending_summarisations(pending)
        broadcast_card_refresh(agent, "user_prompt_submit")

        new_state = result.task.state.value if result.task else TaskState.PROCESSING.value
        _broadcast_state_change(agent, "user_prompt_submit", new_state, message=prompt_text)

        if prompt_text:
            try:
                from .broadcaster import get_broadcaster
                get_broadcaster().broadcast("turn_created", {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "text": prompt_text,
                    "actor": "user",
                    "intent": result.intent.intent.value if result.intent else "command",
                    "task_id": result.task.id if result.task else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.warning(f"Turn created broadcast failed: {e}")

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

        lifecycle = _get_lifecycle_manager()
        current_task = lifecycle.get_current_task(agent)
        if not current_task:
            db.session.commit()
            broadcast_card_refresh(agent, "stop")
            logger.info(f"hook_event: type=stop, agent_id={agent.id}, no active task")
            return HookEventResult(success=True, agent_id=agent.id)

        # Guard: if an interactive tool (AskUserQuestion, ExitPlanMode) has
        # already set AWAITING_INPUT via pre_tool_use, the stop hook fires
        # BETWEEN pre_tool_use and post_tool_use while Claude waits for user
        # input.  Processing the transcript here would either create a new
        # Turn without tool_input (shadowing the structured options) or
        # complete the task entirely — both destroy the respond widget.
        if current_task.state == TaskState.AWAITING_INPUT:
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
        if not agent_text:
            # Defer transcript extraction: complete the request now and
            # schedule a background re-check after a short delay.
            _schedule_deferred_stop(agent, current_task)
            db.session.commit()
            broadcast_card_refresh(agent, "stop")
            logger.info(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"transcript empty — deferred re-check scheduled"
            )
            return HookEventResult(
                success=True, agent_id=agent.id,
                new_state=current_task.state.value,
            )

        try:
            from flask import current_app
            inference_service = current_app.extensions.get("inference_service")
        except RuntimeError:
            inference_service = None

        intent_result = detect_agent_intent(
            agent_text, inference_service=inference_service,
            project_id=agent.project_id, agent_id=agent.id,
        )

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"transcript_len={len(agent_text) if agent_text else 0}, "
            f"intent={intent_result.intent.value}, "
            f"confidence={intent_result.confidence}, "
            f"pattern={intent_result.matched_pattern!r}"
        )
        if agent_text:
            tail_lines = [l for l in agent_text.splitlines() if l.strip()][-5:]
            logger.debug(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"tail_5_lines={tail_lines!r}"
            )

        if intent_result.intent == TurnIntent.QUESTION:
            turn = Turn(
                task_id=current_task.id, actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION, text=agent_text or "",
            )
            db.session.add(turn)
            lifecycle.update_task_state(
                task=current_task, to_state=TaskState.AWAITING_INPUT,
                trigger="hook:stop:question_detected", confidence=intent_result.confidence,
            )
        elif intent_result.intent == TurnIntent.END_OF_TASK:
            lifecycle.complete_task(
                task=current_task, trigger="hook:stop:end_of_task",
                agent_text=agent_text, intent=TurnIntent.END_OF_TASK,
            )
        else:
            lifecycle.complete_task(task=current_task, trigger="hook:stop", agent_text=agent_text)

        _trigger_priority_scoring()
        pending = lifecycle.get_pending_summarisations()
        db.session.commit()
        broadcast_card_refresh(agent, "stop")
        _execute_pending_summarisations(pending)

        actual_state = current_task.state.value
        _broadcast_state_change(agent, "stop", actual_state, message=f"\u2192 {actual_state.upper()}")

        # Send completion notification AFTER summarisation so it contains
        # the AI-generated summary instead of raw transcript text.
        if current_task.state == TaskState.COMPLETE:
            _send_completion_notification(agent, current_task)

        # Broadcast question turn if transitioned to AWAITING_INPUT
        if current_task.state == TaskState.AWAITING_INPUT and current_task.turns:
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    _broadcast_turn_created(agent, t.text, current_task, tool_input=t.tool_input)
                    break

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
        current_task = agent.get_current_task()

        if not current_task or current_task.state not in (TaskState.PROCESSING, TaskState.COMMANDED):
            db.session.commit()
            broadcast_card_refresh(agent, event_type_str)
            logger.info(f"hook_event: type={event_type_str}, agent_id={agent.id}, ignored (no active processing task)")
            return HookEventResult(success=True, agent_id=agent.id)

        # Build question text and create turn BEFORE state transition
        question_text = None
        structured_options = None
        permission_summary_needed = False
        if tool_name is not None or tool_input is not None:
            # pre_tool_use / permission_request: always create turn
            question_text = _extract_question_text(tool_name, tool_input)
            structured_options = _extract_structured_options(tool_name, tool_input)
            # For ExitPlanMode, synthesize default approval options
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
            # For permission_request, try capturing options + context from the tmux pane
            if structured_options is None and event_type_enum == HookEventType.PERMISSION_REQUEST:
                structured_options = _synthesize_permission_options(agent, tool_name, tool_input)
                # Use the synthesized question text (from permission summarizer) if available
                if structured_options:
                    synth_questions = structured_options.get("questions", [])
                    if synth_questions and synth_questions[0].get("question"):
                        question_text = synth_questions[0]["question"]
                    # Check if LLM fallback needed (generic summary)
                    if question_text and question_text.startswith("Permission:"):
                        permission_summary_needed = True
            db.session.add(Turn(
                task_id=current_task.id, actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION, text=question_text,
                tool_input=structured_options,
            ))
        elif message or title:
            # notification: dedup against recent pre_tool_use turn
            has_recent = False
            if current_task.turns:
                for t in reversed(current_task.turns):
                    if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                        has_recent = (datetime.now(timezone.utc) - t.timestamp).total_seconds() < 10
                        break
            if not has_recent:
                question_text = (f"[{title}] " if title else "") + (message or "")
                question_text = question_text.strip()
                if question_text:
                    db.session.add(Turn(
                        task_id=current_task.id, actor=TurnActor.AGENT,
                        intent=TurnIntent.QUESTION, text=question_text,
                    ))

        # Use lifecycle manager for state transition (writes event + sends notification)
        lifecycle = _get_lifecycle_manager()
        lifecycle.update_task_state(
            current_task, TaskState.AWAITING_INPUT,
            trigger=event_type_str, confidence=1.0,
        )

        # Track which tool triggered AWAITING_INPUT so post_tool_use only
        # resumes when the matching tool completes (not unrelated tools)
        if tool_name:
            _awaiting_tool_for_agent[agent.id] = tool_name

        db.session.commit()
        broadcast_card_refresh(agent, event_type_str)

        # Broadcast
        _broadcast_state_change(agent, event_type_str, "AWAITING_INPUT")
        if question_text:
            _broadcast_turn_created(agent, question_text, current_task, tool_input=structured_options)
        elif current_task.turns:
            # Broadcast existing turn (dedup case: pre_tool_use fired first)
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    _broadcast_turn_created(agent, t.text, current_task, tool_input=t.tool_input)

                    break

        # Queue LLM fallback for generic permission summaries
        if permission_summary_needed and current_task.turns:
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    from .task_lifecycle import SummarisationRequest
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

        current_task = agent.get_current_task()
        if current_task and current_task.state == TaskState.AWAITING_INPUT:
            lifecycle = _get_lifecycle_manager()
            lifecycle.update_task_state(
                task=current_task, to_state=TaskState.PROCESSING,
                trigger="hook:pre_tool_use:stale_awaiting_recovery",
                confidence=0.9,
            )
            _awaiting_tool_for_agent.pop(agent.id, None)
            db.session.commit()
            broadcast_card_refresh(agent, "pre_tool_use_recovery")
            _broadcast_state_change(agent, "pre_tool_use", TaskState.PROCESSING.value)
            logger.info(
                f"hook_event: type=pre_tool_use, agent_id={agent.id}, tool={tool_name}, "
                f"recovered stale AWAITING_INPUT → PROCESSING"
            )
            return HookEventResult(success=True, agent_id=agent.id,
                                   state_changed=True, new_state=TaskState.PROCESSING.value)

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
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.POST_TOOL_USE)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        lifecycle = _get_lifecycle_manager()
        current_task = lifecycle.get_current_task(agent)

        if not current_task:
            # Guard: don't infer a task for ended/reaped agents
            if agent.ended_at is not None:
                db.session.commit()
                broadcast_card_refresh(agent, "post_tool_use")
                logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, skipped (agent ended)")
                return HookEventResult(success=True, agent_id=agent.id)

            # Guard: don't infer a task if the previous one just completed
            # (tail-end tool activity after session_end/stop)
            from ..models.task import Task

            recent_complete = (
                db.session.query(Task)
                .filter(
                    Task.agent_id == agent.id,
                    Task.state == TaskState.COMPLETE,
                    Task.completed_at.isnot(None),
                )
                .order_by(Task.completed_at.desc())
                .first()
            )
            if recent_complete and recent_complete.completed_at:
                elapsed = (datetime.now(timezone.utc) - recent_complete.completed_at).total_seconds()
                if elapsed < INFERRED_TASK_COOLDOWN_SECONDS:
                    db.session.commit()
                    broadcast_card_refresh(agent, "post_tool_use")
                    logger.info(
                        f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                        f"skipped inferred task (previous task {recent_complete.id} "
                        f"completed {elapsed:.1f}s ago)"
                    )
                    return HookEventResult(success=True, agent_id=agent.id)

            # No task — infer one from tool use evidence
            new_task = lifecycle.create_task(agent, TaskState.COMMANDED)
            lifecycle.update_task_state(
                task=new_task, to_state=TaskState.PROCESSING,
                trigger="hook:post_tool_use:inferred", confidence=0.9,
            )
            _trigger_priority_scoring()
            pending = lifecycle.get_pending_summarisations()
            db.session.commit()
            broadcast_card_refresh(agent, "post_tool_use_inferred")
            _execute_pending_summarisations(pending)
            _broadcast_state_change(agent, "post_tool_use", TaskState.PROCESSING.value)
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, inferred PROCESSING task_id={new_task.id}")
            return HookEventResult(success=True, agent_id=agent.id, state_changed=True, new_state=TaskState.PROCESSING.value)

        if current_task.state == TaskState.AWAITING_INPUT and tool_name in USER_INTERACTIVE_TOOLS:
            # ExitPlanMode fires post_tool_use after showing the plan but before the
            # user approves/rejects — preserve AWAITING_INPUT until user_prompt_submit
            db.session.commit()
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                        f"preserved AWAITING_INPUT for interactive tool {tool_name}")
            return HookEventResult(success=True, agent_id=agent.id,
                                   new_state=TaskState.AWAITING_INPUT.value)

        if current_task.state == TaskState.AWAITING_INPUT:
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
                                       new_state=TaskState.AWAITING_INPUT.value)

            # Resume: matching tool completed (or no tracking) — user answered
            _awaiting_tool_for_agent.pop(agent.id, None)
            result = lifecycle.process_turn(agent=agent, actor=TurnActor.USER, text=None)
            if result.success:
                _trigger_priority_scoring()
            pending = lifecycle.get_pending_summarisations()
            db.session.commit()
            broadcast_card_refresh(agent, "post_tool_use_resume")
            _execute_pending_summarisations(pending)
            new_state = result.task.state.value if result.task else None
            if new_state == TaskState.PROCESSING.value:
                _broadcast_state_change(
                    agent, "post_tool_use", TaskState.PROCESSING.value,
                    message=f"Tool: {tool_name}" if tool_name else None,
                )
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, resumed from AWAITING_INPUT")
            return HookEventResult(
                success=result.success, agent_id=agent.id,
                state_changed=new_state == TaskState.PROCESSING.value if new_state else False,
                new_state=new_state, error_message=result.error,
            )

        # Already PROCESSING/COMMANDED — no-op
        db.session.commit()
        logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, no-op (state={current_task.state.value})")
        return HookEventResult(success=True, agent_id=agent.id, new_state=current_task.state.value)
    except Exception as e:
        logger.exception(f"Error processing post_tool_use: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
