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
) -> HookEventResult:
    """
    Process a user prompt submit hook event.

    Uses HookLifecycleBridge for proper state machine validation and event logging.
    Transitions: IDLE -> COMMANDED -> PROCESSING

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

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
        result = bridge.process_user_prompt_submit(agent, claude_session_id)

        db.session.commit()

        # Determine new state for response
        new_state = result.task.state.value if result.task else TaskState.PROCESSING.value

        # Broadcast state change to SSE clients
        _broadcast_state_change(agent, "user_prompt_submit", new_state)

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

    Uses HookLifecycleBridge for proper state machine validation and event logging.
    Transitions: PROCESSING -> COMPLETE (agent returns to IDLE for next task)

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

        # Use lifecycle bridge for proper state management and event logging
        bridge = get_hook_bridge()
        result = bridge.process_stop(agent, claude_session_id)

        db.session.commit()

        # Broadcast state change to SSE clients
        # Agent is IDLE after task completion
        _broadcast_state_change(agent, "stop", TaskState.IDLE.value)

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state=idle"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=True,
            new_state=TaskState.IDLE.value,
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
) -> HookEventResult:
    """
    Process a notification hook event.

    Updates timestamp only, no state change.

    Args:
        agent: The correlated agent
        claude_session_id: The Claude session ID

    Returns:
        HookEventResult with processing outcome
    """
    state = get_receiver_state()
    state.record_event(HookEventType.NOTIFICATION)

    try:
        # Update agent timestamp only
        agent.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()

        logger.debug(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}"
        )

        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=False,
            new_state=agent.state.value,
        )
    except Exception as e:
        logger.exception(f"Error processing notification: {e}")
        db.session.rollback()
        return HookEventResult(
            success=False,
            error_message=str(e),
        )
