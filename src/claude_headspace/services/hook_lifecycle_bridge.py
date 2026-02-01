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

    @staticmethod
    def _trigger_priority_scoring() -> None:
        """Trigger rate-limited priority scoring after state transitions."""
        try:
            from flask import current_app
            service = current_app.extensions.get("priority_scoring_service")
            if service:
                service.trigger_scoring()
        except RuntimeError:
            logger.debug("No Flask app context for priority scoring trigger")
        except Exception as e:
            logger.debug(f"Priority scoring trigger failed (non-fatal): {e}")

    def process_user_prompt_submit(
        self,
        agent: Agent,
        claude_session_id: str,
        prompt_text: str | None = None,
    ) -> TurnProcessingResult:
        """
        Process a user_prompt_submit hook as a user command.

        Maps to: USER + COMMAND intent
        Expected transition: IDLE/AWAITING_INPUT -> COMMANDED -> PROCESSING

        Args:
            agent: The agent receiving the hook event
            claude_session_id: The Claude session identifier
            prompt_text: The user's prompt text (from Claude Code hook stdin)

        Returns:
            TurnProcessingResult with the outcome
        """
        lifecycle = self._get_lifecycle_manager()

        # User submitting a prompt is a USER COMMAND
        result = lifecycle.process_turn(
            agent=agent,
            actor=TurnActor.USER,
            text=prompt_text,
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

        # Trigger priority scoring on state change
        if result.success:
            self._trigger_priority_scoring()

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
        Process a stop (turn complete) hook event.

        Maps to: AGENT + COMPLETION intent
        Expected transition: PROCESSING -> COMPLETE

        The stop hook fires at end-of-turn only, so we transition
        the task to COMPLETE immediately. Also reads the transcript
        file to extract the agent's last response text.

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

        # Extract agent response text from transcript before completing
        agent_text = self._extract_transcript_content(agent)

        # Complete the task (creates the completion turn)
        lifecycle.complete_task(
            task=current_task,
            trigger="hook:stop",
            agent_text=agent_text,
        )

        # Trigger priority scoring on state change
        self._trigger_priority_scoring()

        logger.debug(
            f"HookLifecycleBridge.process_stop: "
            f"agent_id={agent.id}, session_id={claude_session_id}, "
            f"task_id={current_task.id}, completed, "
            f"transcript_text={'yes' if agent_text else 'no'}"
        )

        return TurnProcessingResult(
            success=True,
            task=current_task,
            event_written=self._event_writer is not None,
        )

    @staticmethod
    def _extract_transcript_content(agent: Agent) -> str:
        """
        Extract the last agent response from the transcript file.

        Args:
            agent: The agent whose transcript to read

        Returns:
            The extracted text, or empty string if unavailable
        """
        if not agent.transcript_path:
            return ""

        try:
            from .transcript_reader import read_transcript_file
            result = read_transcript_file(agent.transcript_path)
            if result.success and result.text:
                return result.text
            if not result.success:
                logger.warning(
                    f"Transcript read failed for agent_id={agent.id}: {result.error}"
                )
        except Exception as e:
            logger.warning(
                f"Error extracting transcript for agent_id={agent.id}: {e}"
            )

        return ""

    def process_post_tool_use(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a PostToolUse hook event.

        When the agent is in AWAITING_INPUT, PostToolUse signals that
        the user answered and the agent is resuming work.

        Maps to: USER + ANSWER intent (when AWAITING_INPUT)
        Expected transition: AWAITING_INPUT -> PROCESSING

        If not in AWAITING_INPUT, this is a no-op (tool use during normal processing).

        Args:
            agent: The agent receiving the hook event
            claude_session_id: The Claude session identifier

        Returns:
            TurnProcessingResult with the outcome
        """
        lifecycle = self._get_lifecycle_manager()

        current_task = lifecycle.get_current_task(agent)
        if not current_task:
            logger.debug(
                f"HookLifecycleBridge.process_post_tool_use: "
                f"No active task for agent_id={agent.id}"
            )
            return TurnProcessingResult(
                success=True,
                error="No active task",
            )

        if current_task.state != TaskState.AWAITING_INPUT:
            # Not awaiting input — PostToolUse during normal processing is a no-op
            logger.debug(
                f"HookLifecycleBridge.process_post_tool_use: "
                f"agent_id={agent.id}, task not AWAITING_INPUT "
                f"(state={current_task.state.value}), ignoring"
            )
            return TurnProcessingResult(
                success=True,
                task=current_task,
            )

        # Resume: AWAITING_INPUT → PROCESSING via USER + ANSWER
        result = lifecycle.process_turn(
            agent=agent,
            actor=TurnActor.USER,
            text=None,  # PostToolUse doesn't carry user text
        )

        # Trigger priority scoring on state change
        if result.success:
            self._trigger_priority_scoring()

        logger.debug(
            f"HookLifecycleBridge.process_post_tool_use: "
            f"agent_id={agent.id}, session_id={claude_session_id}, "
            f"success={result.success}, resumed from AWAITING_INPUT"
        )

        return result

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
