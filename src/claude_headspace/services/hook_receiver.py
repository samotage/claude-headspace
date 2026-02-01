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


def _broadcast_state_change(agent: Agent, event_type: str, new_state: str) -> None:
    """Broadcast state change to SSE clients."""
    try:
        from .broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        broadcaster.broadcast("state_changed", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "event_type": event_type,
            "new_state": new_state.upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"Broadcast failed (non-fatal): {e}")


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
        _broadcast_state_change(agent, "session_end", TaskState.COMPLETE.value)

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
        _broadcast_state_change(agent, "user_prompt_submit", new_state)

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

        # Use lifecycle bridge to transition task to COMPLETE
        bridge = get_hook_bridge()
        result = bridge.process_stop(agent, claude_session_id)

        db.session.commit()

        # Broadcast state change to SSE clients
        _broadcast_state_change(agent, "stop", TaskState.COMPLETE.value)

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"session_id={claude_session_id}, task completed"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=True,
            new_state=TaskState.COMPLETE.value,
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

            # Store notification context as a turn if message is provided
            if message or title:
                from ..models.turn import Turn, TurnActor, TurnIntent
                notification_text = ""
                if title:
                    notification_text = f"[{title}] "
                if message:
                    notification_text += message
                if notification_text:
                    turn = Turn(
                        task_id=current_task.id,
                        actor=TurnActor.AGENT,
                        intent=TurnIntent.QUESTION,
                        text=notification_text.strip(),
                    )
                    db.session.add(turn)

            logger.info(
                f"DB task transitioned to AWAITING_INPUT: agent_id={agent.id}, "
                f"task_id={current_task.id}, notification_type={notification_type}"
            )

        db.session.commit()

        if did_transition:
            _broadcast_state_change(agent, "notification", "AWAITING_INPUT")

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
            _broadcast_state_change(agent, "post_tool_use", TaskState.PROCESSING.value)

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
