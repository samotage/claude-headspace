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
# because user interaction happens AFTER the tool completes
USER_INTERACTIVE_TOOLS = {"ExitPlanMode"}


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


# --- Internal helpers ---

def _get_lifecycle_manager() -> TaskLifecycleManager:
    event_writer = None
    summarisation_service = None
    try:
        from flask import current_app
        event_writer = current_app.extensions.get("event_writer")
        summarisation_service = current_app.extensions.get("summarisation_service")
    except RuntimeError:
        pass
    return TaskLifecycleManager(
        session=db.session,
        event_writer=event_writer,
        summarisation_service=summarisation_service,
    )


def _trigger_priority_scoring() -> None:
    try:
        from flask import current_app
        service = current_app.extensions.get("priority_scoring_service")
        if service:
            service.trigger_scoring()
    except Exception:
        pass


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
    except Exception:
        pass


def _broadcast_turn_created(agent: Agent, text: str, task) -> None:
    try:
        from .broadcaster import get_broadcaster
        get_broadcaster().broadcast("turn_created", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": text,
            "actor": "agent",
            "intent": "question",
            "task_id": task.id if task else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


def _extract_question_text(tool_name: str | None, tool_input: dict | None) -> str:
    if tool_input and isinstance(tool_input, dict):
        questions = tool_input.get("questions")
        if questions and isinstance(questions, list) and len(questions) > 0:
            q = questions[0]
            if isinstance(q, dict) and q.get("question"):
                return q["question"]
    if tool_name:
        return f"Permission needed: {tool_name}"
    return "Awaiting input"


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
        return ""
    try:
        from .transcript_reader import read_transcript_file
        result = read_transcript_file(agent.transcript_path)
        if result.success and result.text:
            return result.text
    except Exception:
        pass
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
    except Exception:
        pass


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
                pass

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
        except Exception:
            pass

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
        broadcast_card_refresh(agent, "user_prompt_submit")
        _execute_pending_summarisations(pending)

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
            except Exception:
                pass

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

        # Extract transcript and detect intent
        agent_text = _extract_transcript_content(agent)

        try:
            from flask import current_app
            inference_service = current_app.extensions.get("inference_service")
        except RuntimeError:
            inference_service = None

        intent_result = detect_agent_intent(
            agent_text, inference_service=inference_service,
            project_id=agent.project_id, agent_id=agent.id,
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
                    _broadcast_turn_created(agent, t.text, current_task)
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

        current_task.state = TaskState.AWAITING_INPUT

        # Build question text and create turn
        question_text = None
        if tool_name is not None or tool_input is not None:
            # pre_tool_use / permission_request: always create turn
            question_text = _extract_question_text(tool_name, tool_input)
            db.session.add(Turn(
                task_id=current_task.id, actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION, text=question_text,
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

        # OS notification
        _send_notification(agent, current_task, turn_text=question_text or message or title)

        db.session.commit()
        broadcast_card_refresh(agent, event_type_str)

        # Broadcast
        _broadcast_state_change(agent, event_type_str, "AWAITING_INPUT")
        if question_text:
            _broadcast_turn_created(agent, question_text, current_task)
        elif current_task.turns:
            # Broadcast existing turn (dedup case: pre_tool_use fired first)
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    _broadcast_turn_created(agent, t.text, current_task)
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
    return _handle_awaiting_input(
        agent, HookEventType.PRE_TOOL_USE, "pre_tool_use",
        tool_name=tool_name, tool_input=tool_input,
    )


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
            # Interactive tools (e.g. ExitPlanMode) fire post_tool_use before the user
            # sees the dialog, so we must preserve AWAITING_INPUT state
            db.session.commit()
            broadcast_card_refresh(agent, "post_tool_use")
            logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                        f"preserved AWAITING_INPUT for interactive tool {tool_name}")
            return HookEventResult(success=True, agent_id=agent.id,
                                   new_state=TaskState.AWAITING_INPUT.value)

        if current_task.state == TaskState.AWAITING_INPUT:
            # Resume: user answered
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
        broadcast_card_refresh(agent, "post_tool_use")
        logger.info(f"hook_event: type=post_tool_use, agent_id={agent.id}, no-op (state={current_task.state.value})")
        return HookEventResult(success=True, agent_id=agent.id, new_state=current_task.state.value)
    except Exception as e:
        logger.exception(f"Error processing post_tool_use: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
