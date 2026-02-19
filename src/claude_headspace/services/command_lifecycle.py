"""Command lifecycle manager for creating and managing commands."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..database import db
from ..models.agent import Agent
from ..models.event import Event, EventType
from ..models.command import Command, CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from .broadcaster import get_broadcaster
from .card_state import broadcast_card_refresh
from .event_writer import EventWriter, WriteResult
from .hook_agent_state import get_agent_hook_state
from .hook_extractors import mark_question_answered
from .intent_detector import IntentResult, detect_intent
from .state_machine import InvalidTransitionError, TransitionResult, validate_transition
from .team_content_detector import is_team_internal_content

logger = logging.getLogger(__name__)


@dataclass
class AnswerCompletionResult:
    """Result of completing an answer to an AWAITING_INPUT question."""

    turn: Turn
    new_state: CommandState


@dataclass
class SummarisationRequest:
    """A pending summarisation request to be executed after db commit."""

    type: str  # "turn", "instruction", "command_completion"
    turn: Optional[Turn] = None
    command: Optional[Command] = None
    command_text: Optional[str] = None


@dataclass
class TurnProcessingResult:
    """Result of processing a turn event."""

    success: bool
    command: Optional[Command] = None
    transition: Optional[TransitionResult] = None
    intent: Optional[IntentResult] = None
    event_written: bool = False
    error: Optional[str] = None
    new_command_created: bool = False
    pending_summarisations: list = field(default_factory=list)


def get_instruction_for_notification(command, max_length: int = 120) -> str | None:
    """Get command instruction for notification display.

    Falls back to the first USER COMMAND turn's raw text (truncated)
    when the AI-generated instruction summary isn't available yet.
    """
    if command.instruction:
        return command.instruction
    try:
        for t in command.turns:
            if t.actor == TurnActor.USER and t.intent == TurnIntent.COMMAND:
                text = (t.text or "").strip()
                if text:
                    return text[:max_length - 3] + "..." if len(text) > max_length else text
    except Exception as e:
        logger.warning(f"Failed to extract instruction for notification: {e}")
    return None


def complete_answer(
    command: Command,
    agent: Agent,
    text: str,
    *,
    file_metadata: dict | None = None,
    source: str = "unknown",
) -> AnswerCompletionResult:
    """Record an AWAITING_INPUT answer: mark question answered, create turn,
    transition state, commit, and broadcast.

    This is the shared path for voice_command, upload_file, and respond routes.

    Does NOT handle error/rollback or respond-inflight cleanup — the caller's
    except block handles that since each route has different error response formats.

    Args:
        command: The current command (must be in AWAITING_INPUT state).
        agent: The agent being answered.
        text: The user's answer text (or display text for file uploads).
        file_metadata: Optional file metadata dict (for file uploads).
        source: Caller label for broadcast/logging.

    Returns:
        AnswerCompletionResult with the new Turn and the resulting state.
    """
    # 1. Find the most recent QUESTION turn for answer linking
    answered_turn_id = None
    if command.turns:
        for t in reversed(command.turns):
            if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                answered_turn_id = t.id
                break

    # 2. Mark question as answered (updates tool_input status)
    mark_question_answered(command)

    # 3. Create USER/ANSWER turn
    turn = Turn(
        command_id=command.id,
        actor=TurnActor.USER,
        intent=TurnIntent.ANSWER,
        text=text,
        answered_by_turn_id=answered_turn_id,
        timestamp_source="user",
        file_metadata=file_metadata,
    )
    db.session.add(turn)

    # 4. Validate state transition; force PROCESSING on failure
    vr = validate_transition(command.state, TurnActor.USER, TurnIntent.ANSWER)
    if vr.valid:
        command.state = vr.to_state
    else:
        logger.warning(
            f"complete_answer: invalid transition {command.state.value} -> PROCESSING, "
            f"forcing (agent_id={agent.id}, command_id={command.id}, source={source})"
        )
        command.state = CommandState.PROCESSING

    new_state = command.state

    # 5. Update last_seen_at
    agent.last_seen_at = datetime.now(timezone.utc)

    # 6. Clear awaiting tool
    get_agent_hook_state().clear_awaiting_tool(agent.id)

    # 7. Commit
    db.session.commit()

    # 8. Set respond-pending AFTER commit
    get_agent_hook_state().set_respond_pending(agent.id)

    # 9. Broadcast card refresh
    broadcast_card_refresh(agent, source)

    # 10. Broadcast state_changed + turn_created
    try:
        broadcaster = get_broadcaster()
        broadcaster.broadcast("state_changed", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "event_type": source,
            "new_state": new_state.value,
            "message": f"User responded via {source}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        broadcaster.broadcast("turn_created", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": text,
            "actor": "user",
            "intent": "answer",
            "command_id": command.id,
            "command_instruction": command.instruction,
            "turn_id": turn.id,
            "timestamp": turn.timestamp.isoformat() if turn.timestamp else datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"complete_answer broadcast failed ({source}): {e}")

    return AnswerCompletionResult(turn=turn, new_state=new_state)


class CommandLifecycleManager:
    """
    Manager for command lifecycle operations.

    Handles command creation, state transitions, and event logging.
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

    def create_command(self, agent: Agent, initial_state: CommandState = CommandState.COMMANDED) -> Command:
        """
        Create a new command for an agent.

        Args:
            agent: The agent to create the command for
            initial_state: Initial state for the command (default: COMMANDED)

        Returns:
            The created Command instance
        """
        command = Command(
            agent_id=agent.id,
            state=initial_state,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(command)
        self._session.flush()  # Get the command ID

        logger.info(f"Created command id={command.id} for agent id={agent.id} with state={initial_state.value}")

        # Write state transition event for command creation
        if self._event_writer:
            self._write_transition_event(
                agent=agent,
                command=command,
                from_state=CommandState.IDLE,
                to_state=initial_state,
                trigger="user:command",
                confidence=1.0,
            )

        return command

    def get_current_command(self, agent: Agent) -> Optional[Command]:
        """
        Get the current (incomplete) command for an agent.

        Args:
            agent: The agent to get the command for

        Returns:
            The current Command, or None if no incomplete command exists
        """
        return (
            self._session.query(Command)
            .filter(
                Command.agent_id == agent.id,
                Command.state != CommandState.COMPLETE,
            )
            .order_by(Command.started_at.desc())
            .first()
        )

    def derive_agent_state(self, agent: Agent) -> CommandState:
        """
        Derive the agent's current state from its current command.

        This is a computed property - the agent's state is determined by
        its most recent incomplete command.

        Args:
            agent: The agent to get the state for

        Returns:
            The derived CommandState (IDLE if no active command)
        """
        current_command = self.get_current_command(agent)
        if current_command:
            return current_command.state
        return CommandState.IDLE

    def update_command_state(
        self,
        command: Command,
        to_state: CommandState,
        trigger: str,
        confidence: float = 1.0,
    ) -> bool:
        """
        Update a command's state.

        Args:
            command: The command to update
            to_state: The new state
            trigger: The trigger that caused the transition (e.g., "agent:question")
            confidence: Confidence in the transition (0.0-1.0)

        Returns:
            True if the update was successful
        """
        from_state = command.state

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
            "agent:end_of_command": (TurnActor.AGENT, TurnIntent.END_OF_COMMAND),
        }
        _actor, _intent = _actor_map.get(trigger, (TurnActor.AGENT, TurnIntent.PROGRESS))
        if to_state == CommandState.AWAITING_INPUT:
            _intent = TurnIntent.QUESTION
        elif to_state == CommandState.COMPLETE:
            _intent = TurnIntent.COMPLETION
        _vr = _validate(from_state, _actor, _intent)
        if not _vr.valid:
            raise InvalidTransitionError(_vr)

        command.state = to_state

        logger.debug(f"Command id={command.id} state updated: {from_state.value} -> {to_state.value}")

        # Send notification for awaiting_input state
        if to_state == CommandState.AWAITING_INPUT:
            try:
                # Lazy import to avoid circular imports and test context issues
                from .notification_service import get_notification_service
                notification_service = get_notification_service()

                instruction = self._get_instruction_for_notification(command)

                # Find the most recent AGENT QUESTION turn for context
                question_text = None
                try:
                    for t in reversed(command.turns):
                        if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                            question_text = t.summary or t.text
                            break
                except Exception as e:
                    logger.warning(f"Failed to extract question text: {e}")

                notification_service.notify_awaiting_input(
                    agent_id=str(command.agent_id),
                    agent_name=command.agent.name or f"Agent {command.agent_id}",
                    project=command.agent.project.name if command.agent.project else None,
                    command_instruction=instruction,
                    turn_text=question_text,
                )
            except Exception as notif_err:
                logger.warning(f"Notification send failed (non-fatal): {notif_err}")

        # Write state transition event
        if self._event_writer:
            self._write_transition_event(
                agent=command.agent,
                command=command,
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                confidence=confidence,
            )

        return True

    def complete_command(
        self,
        command: Command,
        trigger: str = "agent:completion",
        agent_text: str = "",
        intent: TurnIntent = TurnIntent.COMPLETION,
    ) -> bool:
        """Mark a command as complete.

        Sets the state to COMPLETE and records the completed_at timestamp.

        NOTE: Validation is advisory (log-only) here, unlike update_command_state()
        which enforces transitions strictly. This is intentional — session_end
        and reaper cleanup MUST be able to force-complete commands regardless of
        current state, since they represent external lifecycle events that
        override the state machine.

        Args:
            command: The command to complete
            trigger: The trigger that caused completion
            agent_text: Optional agent response text extracted from transcript
            intent: The turn intent for the completion record (COMPLETION or END_OF_COMMAND)

        Returns:
            True if the command was completed successfully
        """
        from_state = command.state

        # Validate through state machine (advisory only — forced completions
        # like session_end must still proceed even if the transition is unusual)
        _vr = validate_transition(from_state, TurnActor.AGENT, intent)
        if not _vr.valid:
            logger.warning(
                f"complete_command: transition not in VALID_TRANSITIONS (allowing anyway): "
                f"{from_state.value} -> COMPLETE trigger={trigger} "
                f"agent_id={command.agent_id} command_id={command.id} reason={_vr.reason}"
            )

        command.state = CommandState.COMPLETE
        command.completed_at = datetime.now(timezone.utc)

        # Persist full agent output on the command
        if agent_text:
            command.full_output = agent_text

        # Create completion turn record only when there is actual content.
        # Empty/whitespace-only text produces noisy Turn records that add no value.
        turn = None
        if agent_text and agent_text.strip():
            turn = Turn(
                command_id=command.id,
                actor=TurnActor.AGENT,
                intent=intent,
                text=agent_text,
                is_internal=is_team_internal_content(agent_text),
            )
            self._session.add(turn)
            self._session.flush()

        logger.info(f"Command id={command.id} completed at {command.completed_at.isoformat()}")

        # NOTE: Completion notification is sent by the caller (hook_receiver)
        # AFTER summarisation completes, so the notification contains the
        # AI-generated summary instead of raw transcript text.

        # Write state transition event
        if self._event_writer:
            self._write_transition_event(
                agent=command.agent,
                command=command,
                from_state=from_state,
                to_state=CommandState.COMPLETE,
                trigger=trigger,
                confidence=1.0,
            )

        # Queue summarisation requests (executed post-commit by caller)
        if turn:
            self._pending_summarisations.append(
                SummarisationRequest(type="turn", turn=turn)
            )
        self._pending_summarisations.append(
            SummarisationRequest(type="command_completion", command=command)
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
        Process a turn and update command state accordingly.

        This is the main entry point for handling turn events. It:
        1. Gets the current command (or determines if a new one is needed)
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
        current_command = self.get_current_command(agent)
        current_state = current_command.state if current_command else CommandState.IDLE

        # Detect intent
        intent_result = detect_intent(text, actor, current_state)
        logger.debug(
            f"Detected intent: {intent_result.intent.value} "
            f"(confidence={intent_result.confidence})"
        )

        # Special case: User command starts a new command.
        # This handles IDLE (no active command), AWAITING_INPUT (agent asked a question),
        # and PROCESSING (edge case: stop hook completion may not have been received).
        if actor == TurnActor.USER and intent_result.intent == TurnIntent.COMMAND:
            if current_state in (CommandState.IDLE, CommandState.AWAITING_INPUT, CommandState.PROCESSING, CommandState.COMMANDED):
                # User sends follow-up before agent starts — append to existing command
                if current_state == CommandState.COMMANDED and current_command:
                    if text:
                        existing = current_command.full_command or ""
                        current_command.full_command = (existing + "\n" + text).strip() if existing else text

                    turn = Turn(
                        command_id=current_command.id,
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
                            SummarisationRequest(type="instruction", command=current_command, command_text=current_command.full_command)
                        )

                    logger.info(
                        f"Attached follow-up USER COMMAND to commanded command id={current_command.id} "
                        f"(agent id={agent.id})"
                    )
                    return TurnProcessingResult(
                        success=True,
                        command=current_command,
                        intent=intent_result,
                        event_written=self._event_writer is not None,
                        new_command_created=False,
                        pending_summarisations=list(self._pending_summarisations),
                    )

                # Race condition fix: if the command is PROCESSING but has no USER
                # turns, it was created by post_tool_use:inferred before this
                # user_prompt_submit arrived. Attach the user turn to the
                # existing command rather than completing it and losing any PROGRESS
                # data already recorded on it.
                if (
                    current_command
                    and current_state == CommandState.PROCESSING
                    and Turn.query.filter_by(command_id=current_command.id)
                    .filter(Turn.actor == TurnActor.USER)
                    .count() == 0
                ):
                    if text:
                        current_command.full_command = text

                    turn = Turn(
                        command_id=current_command.id,
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
                            SummarisationRequest(type="instruction", command=current_command, command_text=text)
                        )

                    logger.info(
                        f"Attached USER COMMAND to inferred command id={current_command.id} "
                        f"(agent id={agent.id})"
                    )
                    return TurnProcessingResult(
                        success=True,
                        command=current_command,
                        intent=intent_result,
                        event_written=self._event_writer is not None,
                        new_command_created=False,
                        pending_summarisations=list(self._pending_summarisations),
                    )

                # Complete any existing command before creating a new one
                if current_command and current_command.state != CommandState.COMPLETE:
                    self.complete_command(current_command, trigger="user:new_command")

                # Create new command
                new_command = self.create_command(agent, CommandState.COMMANDED)

                # Persist full command text on the command
                if text:
                    new_command.full_command = text

                # Create turn record for the user command
                turn = Turn(
                    command_id=new_command.id,
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
                        SummarisationRequest(type="instruction", command=new_command, command_text=text)
                    )

                return TurnProcessingResult(
                    success=True,
                    command=new_command,
                    intent=intent_result,
                    event_written=self._event_writer is not None,
                    new_command_created=True,
                    pending_summarisations=list(self._pending_summarisations),
                )

        # No active command and not a user command - nothing to do
        if not current_command:
            logger.warning(f"No active command for agent id={agent.id} and turn is not a command")
            return TurnProcessingResult(
                success=False,
                error="No active command and turn is not a user command",
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
                command=current_command,
                transition=transition_result,
                intent=intent_result,
                error=transition_result.reason,
            )

        # Apply the transition
        if transition_result.to_state == CommandState.COMPLETE:
            self.complete_command(current_command, trigger=transition_result.trigger or "unknown")
        else:
            self.update_command_state(
                command=current_command,
                to_state=transition_result.to_state,
                trigger=transition_result.trigger or "unknown",
                confidence=intent_result.confidence,
            )

            # Create turn record for non-completion transitions
            turn = Turn(
                command_id=current_command.id,
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
            command=current_command,
            transition=transition_result,
            intent=intent_result,
            event_written=self._event_writer is not None,
            pending_summarisations=list(self._pending_summarisations),
        )

    def _write_transition_event(
        self,
        agent: Agent,
        command: Command,
        from_state: CommandState,
        to_state: CommandState,
        trigger: str,
        confidence: float,
    ) -> Optional[WriteResult]:
        """
        Write a state_transition event.

        Args:
            agent: The agent involved
            command: The command involved
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
            command_id=command.id,
            session=self._session,
        )

        if not result.success:
            logger.error(f"Failed to write state_transition event: {result.error}")

        return result

    def _get_instruction_for_notification(self, command: Command, max_length: int = 120) -> str | None:
        return get_instruction_for_notification(command, max_length)
