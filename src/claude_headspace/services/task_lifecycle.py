"""Task lifecycle manager for creating and managing tasks."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models.agent import Agent
from ..models.event import Event, EventType
from ..models.task import Task, TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from .event_writer import EventWriter, WriteResult
from .intent_detector import IntentResult, detect_intent
from .state_machine import InvalidTransitionError, TransitionResult, validate_transition
from .team_content_detector import is_team_internal_content

logger = logging.getLogger(__name__)


@dataclass
class SummarisationRequest:
    """A pending summarisation request to be executed after db commit."""

    type: str  # "turn", "instruction", "task_completion"
    turn: Optional[Turn] = None
    task: Optional[Task] = None
    command_text: Optional[str] = None


@dataclass
class TurnProcessingResult:
    """Result of processing a turn event."""

    success: bool
    task: Optional[Task] = None
    transition: Optional[TransitionResult] = None
    intent: Optional[IntentResult] = None
    event_written: bool = False
    error: Optional[str] = None
    new_task_created: bool = False
    pending_summarisations: list = field(default_factory=list)


def get_instruction_for_notification(task, max_length: int = 120) -> str | None:
    """Get task instruction for notification display.

    Falls back to the first USER COMMAND turn's raw text (truncated)
    when the AI-generated instruction summary isn't available yet.
    """
    if task.instruction:
        return task.instruction
    try:
        for t in task.turns:
            if t.actor == TurnActor.USER and t.intent == TurnIntent.COMMAND:
                text = (t.text or "").strip()
                if text:
                    return text[:max_length - 3] + "..." if len(text) > max_length else text
    except Exception as e:
        logger.warning(f"Failed to extract instruction for notification: {e}")
    return None


class TaskLifecycleManager:
    """
    Manager for task lifecycle operations.

    Handles task creation, state transitions, and event logging.
    Uses dependency injection for the event writer and state machine.
    """

    def __init__(
        self,
        session: Session,
        event_writer: Optional[EventWriter] = None,
    ) -> None:
        self._session = session
        self._event_writer = event_writer
        self._pending_summarisations: list[SummarisationRequest] = []

    def get_pending_summarisations(self) -> list[SummarisationRequest]:
        """Return and clear pending summarisation requests."""
        pending = self._pending_summarisations
        self._pending_summarisations = []
        return pending

    def create_task(self, agent: Agent, initial_state: TaskState = TaskState.COMMANDED) -> Task:
        """
        Create a new task for an agent.

        Args:
            agent: The agent to create the task for
            initial_state: Initial state for the task (default: COMMANDED)

        Returns:
            The created Task instance
        """
        task = Task(
            agent_id=agent.id,
            state=initial_state,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(task)
        self._session.flush()  # Get the task ID

        logger.info(f"Created task id={task.id} for agent id={agent.id} with state={initial_state.value}")

        # Write state transition event for task creation
        if self._event_writer:
            self._write_transition_event(
                agent=agent,
                task=task,
                from_state=TaskState.IDLE,
                to_state=initial_state,
                trigger="user:command",
                confidence=1.0,
            )

        return task

    def get_current_task(self, agent: Agent) -> Optional[Task]:
        """
        Get the current (incomplete) task for an agent.

        Args:
            agent: The agent to get the task for

        Returns:
            The current Task, or None if no incomplete task exists
        """
        return (
            self._session.query(Task)
            .filter(
                Task.agent_id == agent.id,
                Task.state != TaskState.COMPLETE,
            )
            .order_by(Task.started_at.desc())
            .first()
        )

    def derive_agent_state(self, agent: Agent) -> TaskState:
        """
        Derive the agent's current state from its current task.

        This is a computed property - the agent's state is determined by
        its most recent incomplete task.

        Args:
            agent: The agent to get the state for

        Returns:
            The derived TaskState (IDLE if no active task)
        """
        current_task = self.get_current_task(agent)
        if current_task:
            return current_task.state
        return TaskState.IDLE

    def update_task_state(
        self,
        task: Task,
        to_state: TaskState,
        trigger: str,
        confidence: float = 1.0,
    ) -> bool:
        """
        Update a task's state.

        Args:
            task: The task to update
            to_state: The new state
            trigger: The trigger that caused the transition (e.g., "agent:question")
            confidence: Confidence in the transition (0.0-1.0)

        Returns:
            True if the update was successful
        """
        from_state = task.state

        # Validate through state machine — reject invalid transitions.
        from .state_machine import validate_transition as _validate
        # Build a synthetic actor/intent for validation.
        # Triggers from hook_receiver use "hook:*" patterns; triggers from
        # process_turn use "ACTOR:INTENT" patterns from the state machine.
        _actor_map = {
            "hook:user_prompt_submit": (TurnActor.USER, TurnIntent.COMMAND),
            "hook:stop:question_detected": (TurnActor.AGENT, TurnIntent.QUESTION),
            "hook:stop:deferred_question": (TurnActor.AGENT, TurnIntent.QUESTION),
            "hook:pre_tool_use:stale_awaiting_recovery": (TurnActor.AGENT, TurnIntent.PROGRESS),
            "hook:post_tool_use:inferred": (TurnActor.AGENT, TurnIntent.PROGRESS),
            "notification": (TurnActor.AGENT, TurnIntent.QUESTION),
            "pre_tool_use": (TurnActor.AGENT, TurnIntent.QUESTION),
            "permission_request": (TurnActor.AGENT, TurnIntent.QUESTION),
            "user:answer": (TurnActor.USER, TurnIntent.ANSWER),
            "user:command": (TurnActor.USER, TurnIntent.COMMAND),
            "agent:question": (TurnActor.AGENT, TurnIntent.QUESTION),
            "agent:progress": (TurnActor.AGENT, TurnIntent.PROGRESS),
            "agent:completion": (TurnActor.AGENT, TurnIntent.COMPLETION),
            "agent:end_of_task": (TurnActor.AGENT, TurnIntent.END_OF_TASK),
        }
        _actor, _intent = _actor_map.get(trigger, (TurnActor.AGENT, TurnIntent.PROGRESS))
        if to_state == TaskState.AWAITING_INPUT:
            _intent = TurnIntent.QUESTION
        elif to_state == TaskState.COMPLETE:
            _intent = TurnIntent.COMPLETION
        _vr = _validate(from_state, _actor, _intent)
        if not _vr.valid:
            raise InvalidTransitionError(_vr)

        task.state = to_state

        logger.debug(f"Task id={task.id} state updated: {from_state.value} -> {to_state.value}")

        # Send notification for awaiting_input state
        if to_state == TaskState.AWAITING_INPUT:
            try:
                # Lazy import to avoid circular imports and test context issues
                from .notification_service import get_notification_service
                notification_service = get_notification_service()

                instruction = self._get_instruction_for_notification(task)

                # Find the most recent AGENT QUESTION turn for context
                question_text = None
                try:
                    for t in reversed(task.turns):
                        if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                            question_text = t.summary or t.text
                            break
                except Exception as e:
                    logger.warning(f"Failed to extract question text: {e}")

                notification_service.notify_awaiting_input(
                    agent_id=str(task.agent_id),
                    agent_name=task.agent.name or f"Agent {task.agent_id}",
                    project=task.agent.project.name if task.agent.project else None,
                    task_instruction=instruction,
                    turn_text=question_text,
                )
            except Exception as notif_err:
                logger.warning(f"Notification send failed (non-fatal): {notif_err}")

        # Write state transition event
        if self._event_writer:
            self._write_transition_event(
                agent=task.agent,
                task=task,
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                confidence=confidence,
            )

        return True

    def complete_task(
        self,
        task: Task,
        trigger: str = "agent:completion",
        agent_text: str = "",
        intent: TurnIntent = TurnIntent.COMPLETION,
    ) -> bool:
        """Mark a task as complete.

        Sets the state to COMPLETE and records the completed_at timestamp.

        NOTE: Validation is advisory (log-only) here, unlike update_task_state()
        which enforces transitions strictly. This is intentional — session_end
        and reaper cleanup MUST be able to force-complete tasks regardless of
        current state, since they represent external lifecycle events that
        override the state machine.

        Args:
            task: The task to complete
            trigger: The trigger that caused completion
            agent_text: Optional agent response text extracted from transcript
            intent: The turn intent for the completion record (COMPLETION or END_OF_TASK)

        Returns:
            True if the task was completed successfully
        """
        from_state = task.state

        # Validate through state machine (advisory only — forced completions
        # like session_end must still proceed even if the transition is unusual)
        _vr = validate_transition(from_state, TurnActor.AGENT, intent)
        if not _vr.valid:
            logger.warning(
                f"complete_task: transition not in VALID_TRANSITIONS (allowing anyway): "
                f"{from_state.value} -> COMPLETE trigger={trigger} "
                f"agent_id={task.agent_id} task_id={task.id} reason={_vr.reason}"
            )

        task.state = TaskState.COMPLETE
        task.completed_at = datetime.now(timezone.utc)

        # Persist full agent output on the task
        if agent_text:
            task.full_output = agent_text

        # Create completion turn record only when there is actual content.
        # Empty/whitespace-only text produces noisy Turn records that add no value.
        turn = None
        if agent_text and agent_text.strip():
            turn = Turn(
                task_id=task.id,
                actor=TurnActor.AGENT,
                intent=intent,
                text=agent_text,
                is_internal=is_team_internal_content(agent_text),
            )
            self._session.add(turn)
            self._session.flush()

        logger.info(f"Task id={task.id} completed at {task.completed_at.isoformat()}")

        # NOTE: Completion notification is sent by the caller (hook_receiver)
        # AFTER summarisation completes, so the notification contains the
        # AI-generated summary instead of raw transcript text.

        # Write state transition event
        if self._event_writer:
            self._write_transition_event(
                agent=task.agent,
                task=task,
                from_state=from_state,
                to_state=TaskState.COMPLETE,
                trigger=trigger,
                confidence=1.0,
            )

        # Queue summarisation requests (executed post-commit by caller)
        if turn:
            self._pending_summarisations.append(
                SummarisationRequest(type="turn", turn=turn)
            )
        self._pending_summarisations.append(
            SummarisationRequest(type="task_completion", task=task)
        )

        return True

    def process_turn(
        self,
        agent: Agent,
        actor: TurnActor,
        text: Optional[str],
        file_metadata: Optional[dict] = None,
        is_internal: bool = False,
    ) -> TurnProcessingResult:
        """
        Process a turn and update task state accordingly.

        This is the main entry point for handling turn events. It:
        1. Gets the current task (or determines if a new one is needed)
        2. Detects the intent of the turn
        3. Validates and applies the state transition
        4. Logs the transition event

        Args:
            agent: The agent the turn is for
            actor: Who produced the turn (USER or AGENT)
            text: The text content of the turn

        Returns:
            TurnProcessingResult with the outcome
        """
        current_task = self.get_current_task(agent)
        current_state = current_task.state if current_task else TaskState.IDLE

        # Detect intent
        intent_result = detect_intent(text, actor, current_state)
        logger.debug(
            f"Detected intent: {intent_result.intent.value} "
            f"(confidence={intent_result.confidence})"
        )

        # Special case: User command starts a new task.
        # This handles IDLE (no active task), AWAITING_INPUT (agent asked a question),
        # and PROCESSING (edge case: stop hook completion may not have been received).
        if actor == TurnActor.USER and intent_result.intent == TurnIntent.COMMAND:
            if current_state in (TaskState.IDLE, TaskState.AWAITING_INPUT, TaskState.PROCESSING, TaskState.COMMANDED):
                # User sends follow-up before agent starts — append to existing task
                if current_state == TaskState.COMMANDED and current_task:
                    if text:
                        existing = current_task.full_command or ""
                        current_task.full_command = (existing + "\n" + text).strip() if existing else text

                    turn = Turn(
                        task_id=current_task.id,
                        actor=actor,
                        intent=TurnIntent.COMMAND,
                        text=text or "",
                        file_metadata=file_metadata,
                        is_internal=is_internal,
                    )
                    self._session.add(turn)
                    self._session.flush()

                    self._pending_summarisations.append(
                        SummarisationRequest(type="turn", turn=turn)
                    )
                    if text:
                        self._pending_summarisations.append(
                            SummarisationRequest(type="instruction", task=current_task, command_text=current_task.full_command)
                        )

                    logger.info(
                        f"Attached follow-up USER COMMAND to commanded task id={current_task.id} "
                        f"(agent id={agent.id})"
                    )
                    return TurnProcessingResult(
                        success=True,
                        task=current_task,
                        intent=intent_result,
                        event_written=self._event_writer is not None,
                        new_task_created=False,
                        pending_summarisations=list(self._pending_summarisations),
                    )

                # Race condition fix: if the task is PROCESSING but has no USER
                # turns, it was created by post_tool_use:inferred before this
                # user_prompt_submit arrived. Attach the user turn to the
                # existing task rather than completing it and losing any PROGRESS
                # data already recorded on it.
                if (
                    current_task
                    and current_state == TaskState.PROCESSING
                    and Turn.query.filter_by(task_id=current_task.id)
                    .filter(Turn.actor == TurnActor.USER)
                    .count() == 0
                ):
                    if text:
                        current_task.full_command = text

                    turn = Turn(
                        task_id=current_task.id,
                        actor=actor,
                        intent=intent_result.intent,
                        text=text or "",
                        file_metadata=file_metadata,
                        is_internal=is_internal,
                    )
                    self._session.add(turn)
                    self._session.flush()

                    self._pending_summarisations.append(
                        SummarisationRequest(type="turn", turn=turn)
                    )
                    if text:
                        self._pending_summarisations.append(
                            SummarisationRequest(type="instruction", task=current_task, command_text=text)
                        )

                    logger.info(
                        f"Attached USER COMMAND to inferred task id={current_task.id} "
                        f"(agent id={agent.id})"
                    )
                    return TurnProcessingResult(
                        success=True,
                        task=current_task,
                        intent=intent_result,
                        event_written=self._event_writer is not None,
                        new_task_created=False,
                        pending_summarisations=list(self._pending_summarisations),
                    )

                # Complete any existing task before creating a new one
                if current_task and current_task.state != TaskState.COMPLETE:
                    self.complete_task(current_task, trigger="user:new_command")

                # Create new task
                new_task = self.create_task(agent, TaskState.COMMANDED)

                # Persist full command text on the task
                if text:
                    new_task.full_command = text

                # Create turn record for the user command
                turn = Turn(
                    task_id=new_task.id,
                    actor=actor,
                    intent=intent_result.intent,
                    text=text or "",
                    file_metadata=file_metadata,
                    is_internal=is_internal,
                )
                self._session.add(turn)
                self._session.flush()

                # Queue summarisation requests (executed post-commit by caller)
                self._pending_summarisations.append(
                    SummarisationRequest(type="turn", turn=turn)
                )
                if text:
                    self._pending_summarisations.append(
                        SummarisationRequest(type="instruction", task=new_task, command_text=text)
                    )

                return TurnProcessingResult(
                    success=True,
                    task=new_task,
                    intent=intent_result,
                    event_written=self._event_writer is not None,
                    new_task_created=True,
                    pending_summarisations=list(self._pending_summarisations),
                )

        # No active task and not a user command - nothing to do
        if not current_task:
            logger.warning(f"No active task for agent id={agent.id} and turn is not a command")
            return TurnProcessingResult(
                success=False,
                error="No active task and turn is not a user command",
                intent=intent_result,
            )

        # Validate transition
        transition_result = validate_transition(
            from_state=current_state,
            actor=actor,
            intent=intent_result.intent,
        )

        if not transition_result.valid:
            logger.warning(f"Invalid transition rejected: {transition_result.reason}")
            return TurnProcessingResult(
                success=False,
                task=current_task,
                transition=transition_result,
                intent=intent_result,
                error=transition_result.reason,
            )

        # Apply the transition
        if transition_result.to_state == TaskState.COMPLETE:
            self.complete_task(current_task, trigger=transition_result.trigger or "unknown")
        else:
            self.update_task_state(
                task=current_task,
                to_state=transition_result.to_state,
                trigger=transition_result.trigger or "unknown",
                confidence=intent_result.confidence,
            )

            # Create turn record for non-completion transitions
            turn = Turn(
                task_id=current_task.id,
                actor=actor,
                intent=intent_result.intent,
                text=text or "",
                file_metadata=file_metadata,
                is_internal=is_internal,
            )
            self._session.add(turn)
            self._session.flush()

            # Queue turn summarisation (executed post-commit by caller)
            self._pending_summarisations.append(
                SummarisationRequest(type="turn", turn=turn)
            )

        return TurnProcessingResult(
            success=True,
            task=current_task,
            transition=transition_result,
            intent=intent_result,
            event_written=self._event_writer is not None,
            pending_summarisations=list(self._pending_summarisations),
        )

    def _write_transition_event(
        self,
        agent: Agent,
        task: Task,
        from_state: TaskState,
        to_state: TaskState,
        trigger: str,
        confidence: float,
    ) -> Optional[WriteResult]:
        """
        Write a state_transition event.

        Args:
            agent: The agent involved
            task: The task involved
            from_state: The previous state
            to_state: The new state
            trigger: What triggered the transition
            confidence: Confidence in the transition

        Returns:
            WriteResult if event writer is available, else None
        """
        if not self._event_writer:
            return None

        payload = {
            "from_state": from_state.value,
            "to_state": to_state.value,
            "trigger": trigger,
            "confidence": confidence,
        }

        result = self._event_writer.write_event(
            event_type=EventType.STATE_TRANSITION,
            payload=payload,
            agent_id=agent.id,
            task_id=task.id,
            session=self._session,
        )

        if not result.success:
            logger.error(f"Failed to write state_transition event: {result.error}")

        return result

    def _get_instruction_for_notification(self, task: Task, max_length: int = 120) -> str | None:
        return get_instruction_for_notification(task, max_length)

