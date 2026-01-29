"""Bridge between hook events and task lifecycle management.

This module translates hook events into proper lifecycle operations,
ensuring state machine validation and event logging occur for all
hook-driven state changes.

Issue 3 & 9 Remediation:
- Issue 3: Hook receiver was bypassing state machine validation
- Issue 9: Event log was not being populated for hook events
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from ..database import db
from ..models.agent import Agent
from ..models.task import Task, TaskState
from ..models.turn import TurnActor, TurnIntent
from .event_writer import EventWriter
from .task_lifecycle import TaskLifecycleManager, TurnProcessingResult

logger = logging.getLogger(__name__)


class HookLifecycleBridge:
    """
    Bridge between hook events and the task lifecycle system.

    Translates hook events into lifecycle operations with proper
    state machine validation and event logging.
    """

    def __init__(
        self,
        event_writer: Optional[EventWriter] = None,
    ) -> None:
        """
        Initialize the hook lifecycle bridge.

        Args:
            event_writer: Optional EventWriter for logging state transitions
        """
        self._event_writer = event_writer

    def _get_lifecycle_manager(self) -> TaskLifecycleManager:
        """Create a TaskLifecycleManager with the current event writer."""
        return TaskLifecycleManager(
            session=db.session,
            event_writer=self._event_writer,
        )

    def process_user_prompt_submit(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a user_prompt_submit hook as a user command.

        Maps to: USER + COMMAND intent
        Expected transition: IDLE/AWAITING_INPUT -> COMMANDED -> PROCESSING

        Args:
            agent: The agent receiving the hook event
            claude_session_id: The Claude session identifier

        Returns:
            TurnProcessingResult with the outcome
        """
        lifecycle = self._get_lifecycle_manager()

        # User submitting a prompt is a USER COMMAND
        result = lifecycle.process_turn(
            agent=agent,
            actor=TurnActor.USER,
            text=None,  # Hook doesn't provide text
        )

        # After user command, immediately transition to processing
        # since Claude will start working
        if result.success and result.task:
            current_state = result.task.state
            if current_state == TaskState.COMMANDED:
                # Simulate agent starting work
                lifecycle.update_task_state(
                    task=result.task,
                    to_state=TaskState.PROCESSING,
                    trigger="hook:user_prompt_submit",
                    confidence=1.0,
                )

        logger.debug(
            f"HookLifecycleBridge.process_user_prompt_submit: "
            f"agent_id={agent.id}, session_id={claude_session_id}, "
            f"success={result.success}, task_id={result.task.id if result.task else None}"
        )

        return result

    def process_stop(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a stop hook as agent completion.

        Maps to: AGENT + COMPLETION intent
        Expected transition: PROCESSING -> COMPLETE

        Args:
            agent: The agent receiving the hook event
            claude_session_id: The Claude session identifier

        Returns:
            TurnProcessingResult with the outcome
        """
        lifecycle = self._get_lifecycle_manager()

        current_task = lifecycle.get_current_task(agent)
        if not current_task:
            # No active task - nothing to complete
            logger.debug(
                f"HookLifecycleBridge.process_stop: No active task for agent_id={agent.id}"
            )
            return TurnProcessingResult(
                success=True,
                error="No active task to complete",
            )

        # Complete the task
        lifecycle.complete_task(
            task=current_task,
            trigger="hook:stop",
        )

        logger.debug(
            f"HookLifecycleBridge.process_stop: "
            f"agent_id={agent.id}, session_id={claude_session_id}, "
            f"task_id={current_task.id}, completed"
        )

        return TurnProcessingResult(
            success=True,
            task=current_task,
            event_written=self._event_writer is not None,
        )

    def process_session_end(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a session_end hook by completing any active task.

        This is a forced completion regardless of current state.

        Args:
            agent: The agent receiving the hook event
            claude_session_id: The Claude session identifier

        Returns:
            TurnProcessingResult with the outcome
        """
        lifecycle = self._get_lifecycle_manager()

        current_task = lifecycle.get_current_task(agent)
        if current_task:
            lifecycle.complete_task(
                task=current_task,
                trigger="hook:session_end",
            )
            logger.debug(
                f"HookLifecycleBridge.process_session_end: "
                f"agent_id={agent.id}, task_id={current_task.id}, completed"
            )
        else:
            logger.debug(
                f"HookLifecycleBridge.process_session_end: "
                f"agent_id={agent.id}, no active task"
            )

        return TurnProcessingResult(
            success=True,
            task=current_task,
            event_written=self._event_writer is not None,
        )


# Global bridge instance with lazy initialization
_bridge: Optional[HookLifecycleBridge] = None


def get_hook_bridge() -> HookLifecycleBridge:
    """
    Get or create the global hook lifecycle bridge.

    The bridge is created lazily and uses the app's event writer if available.

    Returns:
        The global HookLifecycleBridge instance
    """
    global _bridge
    if _bridge is None:
        # Try to get event writer from app extensions
        event_writer = _get_event_writer_from_app()
        _bridge = HookLifecycleBridge(event_writer=event_writer)
        logger.info(
            f"HookLifecycleBridge initialized "
            f"(event_writer={'enabled' if event_writer else 'disabled'})"
        )

    return _bridge


def reset_hook_bridge() -> None:
    """
    Reset the global hook bridge instance.

    Used primarily for testing to ensure clean state.
    """
    global _bridge
    _bridge = None


def _get_event_writer_from_app() -> Optional[EventWriter]:
    """
    Get the EventWriter from Flask app extensions.

    Returns:
        EventWriter if available, None otherwise
    """
    try:
        from flask import current_app

        return current_app.extensions.get("event_writer")
    except RuntimeError:
        # Outside Flask request context
        logger.debug("No Flask app context, event writer not available")
        return None
