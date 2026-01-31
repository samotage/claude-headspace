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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple

from ..database import db
from ..models.agent import Agent
from ..models.task import Task, TaskState
from .hook_lifecycle_bridge import get_hook_bridge

logger = logging.getLogger(__name__)


class HookEventType(str, Enum):
    """Types of hook events from Claude Code."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    STOP = "stop"  # Turn complete
    NOTIFICATION = "notification"


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


# --- Debounced AWAITING_INPUT ---
# The `stop` hook fires between tool calls (mid-turn), not just at end-of-turn.
# To avoid false "input needed" flashes, we debounce: schedule AWAITING_INPUT
# after a delay, and cancel it if user_prompt_submit arrives first.

_AWAITING_INPUT_DELAY = 5.0  # seconds before showing "input needed"
_awaiting_input_timers: dict[int, threading.Timer] = {}
_timers_lock = threading.Lock()


def _schedule_awaiting_input(agent_id: int, project_id: int) -> None:
    """Schedule a delayed AWAITING_INPUT broadcast for an agent."""
    # Capture Flask app for DB access in the timer thread
    app = None
    try:
        from flask import current_app
        app = current_app._get_current_object()
    except RuntimeError:
        logger.debug("No Flask app context for debounce DB persist")

    with _timers_lock:
        # Cancel any existing timer for this agent
        existing = _awaiting_input_timers.pop(agent_id, None)
        if existing:
            existing.cancel()

        timer = threading.Timer(
            _AWAITING_INPUT_DELAY,
            _fire_awaiting_input,
            args=[agent_id, project_id, app],
        )
        timer.daemon = True
        timer.start()
        _awaiting_input_timers[agent_id] = timer


def _cancel_awaiting_input(agent_id: int) -> None:
    """Cancel a pending AWAITING_INPUT broadcast for an agent."""
    with _timers_lock:
        timer = _awaiting_input_timers.pop(agent_id, None)
        if timer:
            timer.cancel()
            logger.debug(f"Cancelled pending AWAITING_INPUT for agent_id={agent_id}")


def _fire_awaiting_input(agent_id: int, project_id: int, app=None) -> None:
    """Fire the AWAITING_INPUT broadcast after the debounce period expires.

    Also persists the AWAITING_INPUT state to the DB so it survives server restarts.
    """
    with _timers_lock:
        _awaiting_input_timers.pop(agent_id, None)

    # Set display override so server-side rendering is consistent with SSE
    _set_display_override(agent_id, "AWAITING_INPUT")

    # Persist to DB so the state survives server restarts
    if app is not None:
        try:
            with app.app_context():
                agent = db.session.get(Agent, agent_id)
                if agent:
                    task = agent.get_current_task()
                    if task and task.state == TaskState.PROCESSING:
                        task.state = TaskState.AWAITING_INPUT
                        db.session.commit()
                        logger.info(
                            f"Persisted AWAITING_INPUT to DB: agent_id={agent_id}, "
                            f"task_id={task.id}"
                        )
        except Exception as e:
            logger.debug(f"DB persist for AWAITING_INPUT failed (non-fatal): {e}")

    try:
        from .broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        broadcaster.broadcast("state_changed", {
            "agent_id": agent_id,
            "project_id": project_id,
            "event_type": "stop_debounced",
            "new_state": "AWAITING_INPUT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Debounced AWAITING_INPUT broadcast for agent_id={agent_id}")
    except Exception as e:
        logger.debug(f"Debounced AWAITING_INPUT broadcast failed: {e}")


# --- Display state overrides ---
# In-memory overrides for server-side rendering consistency with SSE broadcasts.
# The debounce timer and notification handler both persist AWAITING_INPUT to the DB,
# so these overrides mainly serve as a fast cache to avoid an extra DB query on the
# dashboard route. They also cover the brief window between SSE broadcast and the
# next page load.

_agent_display_overrides: dict[int, str] = {}
_overrides_lock = threading.Lock()


def get_agent_display_state(agent_id: int) -> str | None:
    """Get the display state override for an agent, or None if no override."""
    with _overrides_lock:
        return _agent_display_overrides.get(agent_id)


def _set_display_override(agent_id: int, state: str) -> None:
    """Set a display state override for an agent."""
    with _overrides_lock:
        _agent_display_overrides[agent_id] = state
    logger.debug(f"Display override set: agent_id={agent_id}, state={state}")


def _clear_display_override(agent_id: int) -> None:
    """Clear the display state override for an agent."""
    with _overrides_lock:
        removed = _agent_display_overrides.pop(agent_id, None)
    if removed:
        logger.debug(f"Display override cleared: agent_id={agent_id}")


def reset_receiver_state() -> None:
    """Reset the global receiver state. Used in testing."""
    global _receiver_state
    _receiver_state = HookReceiverState()


def cancel_all_timers() -> None:
    """Cancel all pending AWAITING_INPUT timers. Used in testing."""
    with _timers_lock:
        for timer in _awaiting_input_timers.values():
            timer.cancel()
        _awaiting_input_timers.clear()


def clear_display_overrides() -> None:
    """Clear all display state overrides. Used in testing."""
    with _overrides_lock:
        _agent_display_overrides.clear()


def process_session_start(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    """
    Process a session start hook event.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_START)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)
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
        # Cancel any pending AWAITING_INPUT timer
        _cancel_awaiting_input(agent.id)

        # Clear display override - session is ending
        _clear_display_override(agent.id)

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
        # Cancel any pending AWAITING_INPUT timer - user is sending input,
        # so the previous stop was a mid-turn pause, not end-of-turn
        _cancel_awaiting_input(agent.id)

        # Clear display override - agent is now processing, not awaiting input
        _clear_display_override(agent.id)

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

    The stop hook fires between tool calls (mid-turn) AND at end-of-turn.
    We can't distinguish these, so we don't change model state here.
    Instead, we schedule a debounced AWAITING_INPUT transition. If
    user_prompt_submit arrives within the delay, the timer is cancelled
    (it was a mid-turn stop). If the timer expires, the task transitions
    to AWAITING_INPUT in the DB.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.STOP)

    try:
        # Update agent timestamp only - don't change task state
        agent.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()

        # Schedule debounced AWAITING_INPUT. If user_prompt_submit arrives
        # within the delay, the timer is cancelled (mid-turn stop).
        # If the timer expires, _fire_awaiting_input transitions the DB task.
        _schedule_awaiting_input(agent.id, agent.project_id)

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"session_id={claude_session_id} (awaiting_input debounce scheduled)"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=False,
            new_state=agent.state.value,
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
) -> HookEventResult:
    """
    Process a notification hook event.

    Notifications fire when Claude needs user attention (e.g. AskUserQuestion).
    This signals AWAITING_INPUT immediately - no debounce needed since
    notifications are a strong signal that the agent is blocked on user input.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.NOTIFICATION)

    try:
        # Update agent timestamp
        agent.last_seen_at = datetime.now(timezone.utc)

        # Cancel any pending debounce timer - notification is a stronger signal
        _cancel_awaiting_input(agent.id)

        # Transition DB task to AWAITING_INPUT if currently PROCESSING.
        # This uses the valid state machine transition:
        # PROCESSING + AGENT + QUESTION → AWAITING_INPUT
        current_task = agent.get_current_task()
        if current_task and current_task.state == TaskState.PROCESSING:
            current_task.state = TaskState.AWAITING_INPUT
            logger.info(
                f"DB task transitioned to AWAITING_INPUT: agent_id={agent.id}, "
                f"task_id={current_task.id}"
            )

        db.session.commit()

        # Set display override and broadcast AWAITING_INPUT immediately
        _set_display_override(agent.id, "AWAITING_INPUT")
        _broadcast_state_change(agent, "notification", "AWAITING_INPUT")

        logger.info(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}, immediate AWAITING_INPUT"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=True,
            new_state="AWAITING_INPUT",
        )
    except Exception as e:
        logger.exception(f"Error processing notification: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )
