"""Hook receiver service for processing Claude Code hook events.

This module processes incoming hook events from Claude Code and translates
them into appropriate state transitions via the HookLifecycleBridge.

Remediation Notes (Issue 3 & 9):
- Issue 3: Previously bypassed state machine validation by directly setting task.state
- Issue 9: Previously failed to write events to the audit log
- Now uses HookLifecycleBridge for proper state machine validation and event logging
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
from .hook_lifecycle_bridge import get_hook_bridge

logger = logging.getLogger(__name__)


class HookEventType(str, Enum):
    """Types of hook events from Claude Code."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    STOP = "stop"  # Turn complete
    NOTIFICATION = "notification"
    POST_TOOL_USE = "post_tool_use"
    PRE_TOOL_USE = "pre_tool_use"
    PERMISSION_REQUEST = "permission_request"


class HookMode(str, Enum):
    """Operating mode for the hook receiver."""

    HOOKS_ACTIVE = "hooks_active"  # Using hooks with infrequent polling
    POLLING_FALLBACK = "polling_fallback"  # Hooks silent, using frequent polling


class HookEventResult(NamedTuple):
    """Result of processing a hook event."""

    success: bool
    agent_id: int | None = None
    state_changed: bool = False
    new_state: str | None = None
    error_message: str | None = None


@dataclass
class HookReceiverState:
    """State tracking for the hook receiver."""

    enabled: bool = True
    last_event_at: datetime | None = None
    last_event_type: HookEventType | None = None
    mode: HookMode = HookMode.POLLING_FALLBACK
    events_received: int = 0

    # Configuration
    polling_interval_with_hooks: int = 60  # seconds
    polling_interval_fallback: int = 2  # seconds
    fallback_timeout: int = 300  # seconds before reverting to frequent polling

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_event(self, event_type: HookEventType) -> None:
        """Record that an event was received."""
        with self._lock:
            self.last_event_at = datetime.now(timezone.utc)
            self.last_event_type = event_type
            self.events_received += 1

            # Switch to hooks active mode
            if self.mode == HookMode.POLLING_FALLBACK:
                self.mode = HookMode.HOOKS_ACTIVE
                logger.info("Hook receiver mode changed to HOOKS_ACTIVE")

    def check_fallback(self) -> None:
        """Check if we should fall back to frequent polling."""
        with self._lock:
            if self.mode != HookMode.HOOKS_ACTIVE:
                return

            if self.last_event_at is None:
                return

            elapsed = (datetime.now(timezone.utc) - self.last_event_at).total_seconds()
            if elapsed > self.fallback_timeout:
                self.mode = HookMode.POLLING_FALLBACK
                logger.warning(
                    f"No hook events for {elapsed:.0f}s, "
                    f"reverting to POLLING_FALLBACK mode"
                )

    def get_polling_interval(self) -> int:
        """Get the current polling interval based on mode."""
        with self._lock:
            if self.mode == HookMode.HOOKS_ACTIVE:
                return self.polling_interval_with_hooks
            return self.polling_interval_fallback


# Global receiver state
_receiver_state = HookReceiverState()


def get_receiver_state() -> HookReceiverState:
    """Get the global hook receiver state."""
    return _receiver_state


def configure_receiver(
    enabled: bool | None = None,
    polling_interval_with_hooks: int | None = None,
    fallback_timeout: int | None = None,
) -> None:
    """
    Configure the hook receiver.

    Args:
        enabled: Whether hook reception is enabled
        polling_interval_with_hooks: Polling interval when hooks are active
        fallback_timeout: Timeout before falling back to frequent polling
    """
    state = get_receiver_state()
    with state._lock:
        if enabled is not None:
            state.enabled = enabled
        if polling_interval_with_hooks is not None:
            state.polling_interval_with_hooks = polling_interval_with_hooks
        if fallback_timeout is not None:
            state.fallback_timeout = fallback_timeout


def _broadcast_state_change(
    agent: Agent,
    event_type: str,
    new_state: str,
    message: str | None = None,
    payload: dict | None = None,
) -> None:
    """Broadcast state change to SSE clients.

    Args:
        agent: The agent whose state changed
        event_type: Hook event type (e.g. "stop", "notification")
        new_state: The resulting task state
        message: Human-readable message for the logging page
        payload: Additional payload data for the logging page
    """
    try:
        from .broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        broadcaster.broadcast("state_changed", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "project_name": agent.project.name if agent.project else None,
            "agent_session": str(agent.session_uuid),
            "event_type": event_type,
            "new_state": new_state.upper(),
            "message": message,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"Broadcast failed (non-fatal): {e}")


def _broadcast_turn_created(agent: Agent, text: str, task) -> None:
    """Broadcast turn_created SSE event so the dashboard updates the task summary."""
    try:
        from .broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        broadcaster.broadcast("turn_created", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": text,
            "actor": "agent",
            "intent": "question",
            "task_id": task.id if task else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"turn_created broadcast failed (non-fatal): {e}")


def _get_instruction_for_notification(task, max_length: int = 120) -> str | None:
    """
    Get task instruction for notification display.

    Falls back to the first USER COMMAND turn's raw text (truncated)
    when the AI-generated instruction summary isn't available yet.
    """
    if task.instruction:
        return task.instruction

    try:
        from ..models.turn import TurnActor, TurnIntent
        for t in task.turns:
            if t.actor == TurnActor.USER and t.intent == TurnIntent.COMMAND:
                text = (t.text or "").strip()
                if text:
                    if len(text) > max_length:
                        return text[:max_length - 3] + "..."
                    return text
    except Exception:
        pass

    return None


def _extract_question_text(tool_name: str | None, tool_input: dict | None) -> str:
    """
    Extract human-readable question text from tool_input.

    Handles the AskUserQuestion structure where the question is at
    tool_input.questions[0].question. Falls back to a generic message.
    """
    if tool_input and isinstance(tool_input, dict):
        # AskUserQuestion: questions[0].question
        questions = tool_input.get("questions")
        if questions and isinstance(questions, list) and len(questions) > 0:
            q = questions[0]
            if isinstance(q, dict) and q.get("question"):
                return q["question"]

    if tool_name:
        return f"Permission needed: {tool_name}"
    return "Awaiting input"


def reset_receiver_state() -> None:
    """Reset the global receiver state. Used in testing."""
    global _receiver_state
    _receiver_state = HookReceiverState()


def process_session_start(
    agent: Agent,
    claude_session_id: str,
    transcript_path: str | None = None,
) -> HookEventResult:
    """
    Process a session start hook event.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID
        transcript_path: Path to the transcript .jsonl file (from hook payload)

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_START)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Capture transcript path if provided
        if transcript_path and not agent.transcript_path:
            agent.transcript_path = transcript_path
            logger.info(
                f"Captured transcript_path for agent_id={agent.id}: {transcript_path}"
            )

        db.session.commit()

        logger.info(
            f"hook_event: type=session_start, agent_id={agent.id}, "
            f"session_id={claude_session_id}"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=False,
            new_state=agent.state.value,
        )
    except Exception as e:
        logger.exception(f"Error processing session_start: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_session_end(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    """
    Process a session end hook event.

    Uses HookLifecycleBridge for proper state machine validation and event logging.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_END)

    try:
        # Update agent timestamp and mark as ended
        now = datetime.now(timezone.utc)
        agent.last_seen_at = now
        agent.ended_at = now

        # Use lifecycle bridge for proper state management and event logging
        bridge = get_hook_bridge()
        result = bridge.process_session_end(agent, claude_session_id)

        db.session.commit()

        # Broadcast state change to SSE clients
        _broadcast_state_change(
            agent, "session_end", TaskState.COMPLETE.value,
            message="Session ended",
        )

        # Broadcast session_ended as a top-level event so dashboard removes the card
        try:
            from .broadcaster import get_broadcaster
            broadcaster = get_broadcaster()
            broadcaster.broadcast("session_ended", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "session_uuid": str(agent.session_uuid),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.debug(f"session_ended broadcast failed (non-fatal): {e}")

        logger.info(
            f"hook_event: type=session_end, agent_id={agent.id}, "
            f"session_id={claude_session_id}"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=True,
            new_state=TaskState.COMPLETE.value,
            error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing session_end: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_user_prompt_submit(
    agent: Agent,
    claude_session_id: str,
    prompt_text: str | None = None,
) -> HookEventResult:
    """
    Process a user prompt submit hook event.

    Uses HookLifecycleBridge for proper state machine validation and event logging.
    Transitions: IDLE -> COMMANDED -> PROCESSING

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID
        prompt_text: The user's prompt text (from Claude Code hook stdin)

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.USER_PROMPT_SUBMIT)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Use lifecycle bridge for proper state management and event logging
        bridge = get_hook_bridge()
        result = bridge.process_user_prompt_submit(agent, claude_session_id, prompt_text=prompt_text)

        db.session.commit()

        # Determine new state for response
        new_state = result.task.state.value if result.task else TaskState.PROCESSING.value

        # Broadcast state change to SSE clients
        _broadcast_state_change(
            agent, "user_prompt_submit", new_state,
            message=prompt_text,
        )

        # Broadcast turn_created so dashboard updates task summary with the command
        if prompt_text:
            try:
                from .broadcaster import get_broadcaster
                broadcaster = get_broadcaster()
                broadcaster.broadcast("turn_created", {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "text": prompt_text,
                    "actor": "user",
                    "intent": "command",
                    "task_id": result.task.id if result.task else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.debug(f"turn_created broadcast failed (non-fatal): {e}")

        logger.info(
            f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={new_state}"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=True,
            new_state=new_state,
            error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing user_prompt_submit: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_stop(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    """
    Process a stop (turn complete) hook event.

    The stop hook fires at end-of-turn only (not mid-turn between tool calls).
    We transition the current task to COMPLETE immediately.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.STOP)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Use lifecycle bridge to transition task (may be COMPLETE or AWAITING_INPUT)
        bridge = get_hook_bridge()
        result = bridge.process_stop(agent, claude_session_id)

        db.session.commit()

        # Only broadcast if there was actually a task to transition
        if result.task:
            actual_state = result.task.state.value
            _broadcast_state_change(
                agent, "stop", actual_state,
                message=f"\u2192 {actual_state.upper()}",
            )

            # If stop resulted in AWAITING_INPUT, broadcast the most recent
            # AGENT QUESTION turn so the dashboard shows the question text
            if result.task.state == TaskState.AWAITING_INPUT and result.task.turns:
                from ..models.turn import TurnActor, TurnIntent
                for t in reversed(result.task.turns):
                    if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                        _broadcast_turn_created(agent, t.text, result.task)
                        break
        else:
            actual_state = None

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={actual_state}"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=result.task is not None,
            new_state=actual_state,
            error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing stop: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_notification(
    agent: Agent,
    claude_session_id: str,
    message: str | None = None,
    title: str | None = None,
    notification_type: str | None = None,
) -> HookEventResult:
    """
    Process a notification hook event.

    Notifications fire when Claude needs user attention (e.g. AskUserQuestion,
    permission dialogs, idle prompts). This signals AWAITING_INPUT immediately.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID
        message: Notification message text from the hook payload
        title: Notification title from the hook payload
        notification_type: Type of notification (elicitation_dialog, permission_prompt, idle_prompt)

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.NOTIFICATION)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Backfill transcript_path if available on the agent but not yet set
        # (notifications also carry transcript_path in the payload)

        # Transition DB task to AWAITING_INPUT if currently PROCESSING or COMMANDED.
        current_task = agent.get_current_task()
        did_transition = False
        if current_task and current_task.state in (TaskState.PROCESSING, TaskState.COMMANDED):
            current_task.state = TaskState.AWAITING_INPUT
            did_transition = True

            # Send OS notification
            try:
                from .notification_service import get_notification_service
                svc = get_notification_service()
                svc.notify_awaiting_input(
                    agent_id=str(agent.id),
                    agent_name=agent.name or f"Agent {agent.id}",
                    project=agent.project.name if agent.project else None,
                    task_instruction=_get_instruction_for_notification(current_task),
                    turn_text=message or title,
                )
            except Exception as e:
                logger.warning(f"Notification send failed (non-fatal): {e}")

            # Store notification context as a turn if message is provided,
            # but skip if a recent AGENT QUESTION turn already exists (dedup
            # against PRE_TOOL_USE which may have fired just before this)
            notification_text = None
            if message or title:
                from ..models.turn import Turn, TurnActor, TurnIntent

                # Dedup: check if a recent AGENT QUESTION turn exists (within 10s)
                has_recent_question = False
                if current_task.turns:
                    for t in reversed(current_task.turns):
                        if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                            age = (datetime.now(timezone.utc) - t.timestamp).total_seconds()
                            if age < 10:
                                has_recent_question = True
                            break

                if not has_recent_question:
                    notification_text = ""
                    if title:
                        notification_text = f"[{title}] "
                    if message:
                        notification_text += message
                    notification_text = notification_text.strip()
                    if notification_text:
                        turn = Turn(
                            task_id=current_task.id,
                            actor=TurnActor.AGENT,
                            intent=TurnIntent.QUESTION,
                            text=notification_text,
                        )
                        db.session.add(turn)

            logger.info(
                f"DB task transitioned to AWAITING_INPUT: agent_id={agent.id}, "
                f"task_id={current_task.id}, notification_type={notification_type}"
            )

        db.session.commit()

        if did_transition:
            notif_msg = title or message or "Notification"
            _broadcast_state_change(
                agent, "notification", "AWAITING_INPUT",
                message=notif_msg,
            )
            # Broadcast the turn text so dashboard updates in real-time
            if notification_text:
                _broadcast_turn_created(agent, notification_text, current_task)
            elif current_task and current_task.turns:
                # A recent turn from PRE_TOOL_USE already exists; broadcast it
                from ..models.turn import TurnActor, TurnIntent
                for t in reversed(current_task.turns):
                    if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                        _broadcast_turn_created(agent, t.text, current_task)
                        break

        logger.info(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}, notification_type={notification_type}, "
            f"{'immediate AWAITING_INPUT' if did_transition else 'ignored (no active processing task)'}"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=did_transition,
            new_state="AWAITING_INPUT" if did_transition else None,
        )
    except Exception as e:
        logger.exception(f"Error processing notification: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_post_tool_use(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
) -> HookEventResult:
    """
    Process a PostToolUse hook event.

    PostToolUse fires after a tool completes. When the agent is in AWAITING_INPUT
    state, this signals that the user has responded and the agent is resuming work.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID
        tool_name: Name of the tool that was used

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.POST_TOOL_USE)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Backfill transcript_path if not yet set
        # (PostToolUse payloads include transcript_path)

        # Resume from AWAITING_INPUT → PROCESSING
        bridge = get_hook_bridge()
        result = bridge.process_post_tool_use(agent, claude_session_id)

        db.session.commit()

        new_state = None
        if result.task:
            new_state = result.task.state.value

        if result.success and new_state == TaskState.PROCESSING.value:
            _broadcast_state_change(
                agent, "post_tool_use", TaskState.PROCESSING.value,
                message=f"Tool: {tool_name}" if tool_name else None,
            )

        logger.info(
            f"hook_event: type=post_tool_use, agent_id={agent.id}, "
            f"session_id={claude_session_id}, tool_name={tool_name}, "
            f"state_changed={new_state == TaskState.PROCESSING.value if new_state else False}"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=new_state == TaskState.PROCESSING.value if new_state else False,
            new_state=new_state,
            error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing post_tool_use: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_pre_tool_use(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    """
    Process a PreToolUse hook event.

    PreToolUse fires before a tool executes. When the tool is AskUserQuestion,
    this signals AWAITING_INPUT immediately (faster than the Notification hook).

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID
        tool_name: Name of the tool about to be used (e.g. "AskUserQuestion")
        tool_input: The tool's input parameters (contains question text for AskUserQuestion)

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.PRE_TOOL_USE)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Transition DB task to AWAITING_INPUT if currently PROCESSING or COMMANDED
        current_task = agent.get_current_task()
        did_transition = False
        question_text = None
        if current_task and current_task.state in (TaskState.PROCESSING, TaskState.COMMANDED):
            current_task.state = TaskState.AWAITING_INPUT
            did_transition = True

            # Create AGENT QUESTION turn with extracted question text
            question_text = _extract_question_text(tool_name, tool_input)
            from ..models.turn import Turn, TurnActor, TurnIntent
            turn = Turn(
                task_id=current_task.id,
                actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION,
                text=question_text,
            )
            db.session.add(turn)

            # Send OS notification
            try:
                from .notification_service import get_notification_service
                svc = get_notification_service()
                svc.notify_awaiting_input(
                    agent_id=str(agent.id),
                    agent_name=agent.name or f"Agent {agent.id}",
                    project=agent.project.name if agent.project else None,
                    task_instruction=_get_instruction_for_notification(current_task),
                    turn_text=question_text,
                )
            except Exception as e:
                logger.warning(f"Notification send failed (non-fatal): {e}")

            logger.info(
                f"DB task transitioned to AWAITING_INPUT: agent_id={agent.id}, "
                f"task_id={current_task.id}, tool_name={tool_name}"
            )

        db.session.commit()

        if did_transition:
            _broadcast_state_change(
                agent, "pre_tool_use", "AWAITING_INPUT",
                message=f"Tool: {tool_name}" if tool_name else None,
            )
            if question_text:
                _broadcast_turn_created(agent, question_text, current_task)

        logger.info(
            f"hook_event: type=pre_tool_use, agent_id={agent.id}, "
            f"session_id={claude_session_id}, tool_name={tool_name}, "
            f"{'immediate AWAITING_INPUT' if did_transition else 'ignored (no active processing task)'}"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=did_transition,
            new_state="AWAITING_INPUT" if did_transition else None,
        )
    except Exception as e:
        logger.exception(f"Error processing pre_tool_use: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )


def process_permission_request(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    """
    Process a PermissionRequest hook event.

    PermissionRequest fires when a permission dialog is shown to the user.
    This signals AWAITING_INPUT immediately (faster than the Notification hook).

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID
        tool_name: Name of the tool requesting permission
        tool_input: The tool's input parameters

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.PERMISSION_REQUEST)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Transition DB task to AWAITING_INPUT if currently PROCESSING or COMMANDED
        current_task = agent.get_current_task()
        did_transition = False
        question_text = None
        if current_task and current_task.state in (TaskState.PROCESSING, TaskState.COMMANDED):
            current_task.state = TaskState.AWAITING_INPUT
            did_transition = True

            # Create AGENT QUESTION turn with extracted question text
            question_text = _extract_question_text(tool_name, tool_input)
            from ..models.turn import Turn, TurnActor, TurnIntent
            turn = Turn(
                task_id=current_task.id,
                actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION,
                text=question_text,
            )
            db.session.add(turn)

            # Send OS notification
            try:
                from .notification_service import get_notification_service
                svc = get_notification_service()
                svc.notify_awaiting_input(
                    agent_id=str(agent.id),
                    agent_name=agent.name or f"Agent {agent.id}",
                    project=agent.project.name if agent.project else None,
                    task_instruction=_get_instruction_for_notification(current_task),
                    turn_text=question_text,
                )
            except Exception as e:
                logger.warning(f"Notification send failed (non-fatal): {e}")

            logger.info(
                f"DB task transitioned to AWAITING_INPUT: agent_id={agent.id}, "
                f"task_id={current_task.id}, source=permission_request, tool_name={tool_name}"
            )

        db.session.commit()

        if did_transition:
            _broadcast_state_change(
                agent, "permission_request", "AWAITING_INPUT",
                message="Permission requested",
            )
            if question_text:
                _broadcast_turn_created(agent, question_text, current_task)

        logger.info(
            f"hook_event: type=permission_request, agent_id={agent.id}, "
            f"session_id={claude_session_id}, "
            f"{'immediate AWAITING_INPUT' if did_transition else 'ignored (no active processing task)'}"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=did_transition,
            new_state="AWAITING_INPUT" if did_transition else None,
        )
    except Exception as e:
        logger.exception(f"Error processing permission_request: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )
