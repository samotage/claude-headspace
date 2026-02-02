"""Summarisation service for generating turn and task summaries via the inference layer."""

import logging
from datetime import datetime, timezone

from .inference_service import InferenceService, InferenceServiceError
from .prompt_registry import build_prompt

logger = logging.getLogger(__name__)


class SummarisationService:
    """Generates AI summaries for turns and tasks using the inference service."""

    def __init__(self, inference_service: InferenceService):
        """Initialize the summarisation service.

        Args:
            inference_service: The E3-S1 inference service for LLM calls
        """
        self._inference = inference_service

    def summarise_turn(self, turn, db_session=None) -> str | None:
        """Generate a summary for a turn.

        If the turn already has a summary, returns the existing summary.
        Skips summarisation when turn text is None or empty.
        Uses intent-aware prompts with task instruction context.

        Args:
            turn: Turn model instance with text, actor, intent
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed or skipped
        """
        # Return existing summary if present (permanent caching via DB)
        if turn.summary:
            return turn.summary

        # Empty text guard: skip summarisation when text is None/empty
        if not turn.text or not turn.text.strip():
            logger.debug(f"Skipping turn summarisation for turn {turn.id}: empty text")
            return None

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping turn summarisation")
            return None

        # Build prompt
        input_text = self._resolve_turn_prompt(turn)

        # Get entity associations for InferenceCall logging
        task_id = turn.task_id if turn.task_id else None
        agent_id = None
        project_id = None
        if hasattr(turn, "task") and turn.task:
            agent_id = turn.task.agent_id if hasattr(turn.task, "agent_id") else None
            if hasattr(turn.task, "agent") and turn.task.agent:
                project_id = turn.task.agent.project_id if hasattr(turn.task.agent, "project_id") else None

        try:
            result = self._inference.infer(
                level="turn",
                purpose="summarise_turn",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                task_id=task_id,
                turn_id=turn.id,
            )

            # Persist summary to turn model
            turn.summary = result.text
            turn.summary_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(turn)
                db_session.commit()

            return result.text

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Turn summarisation failed for turn {turn.id}: {e}")
            return None

    def summarise_task(self, task, db_session=None) -> str | None:
        """Generate a completion summary for a completed task.

        If the task already has a completion_summary, returns it.
        Skips summarisation if the final turn text is empty.
        Uses task instruction + final agent message as primary inputs.

        Args:
            task: Task model instance with turns, instruction
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed or skipped
        """
        # Return existing summary if present (permanent caching via DB)
        if task.completion_summary:
            return task.completion_summary

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping task summarisation")
            return None

        # Build prompt — returns None when there's nothing to summarise
        input_text = self._resolve_task_prompt(task)
        if input_text is None:
            logger.debug("No content to summarise for task %s, skipping", task.id)
            return None

        # Get entity associations for InferenceCall logging
        agent_id = task.agent_id if hasattr(task, "agent_id") else None
        project_id = None
        if hasattr(task, "agent") and task.agent:
            project_id = task.agent.project_id if hasattr(task.agent, "project_id") else None

        try:
            result = self._inference.infer(
                level="task",
                purpose="summarise_task",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                task_id=task.id,
            )

            # Persist summary to task model
            task.completion_summary = result.text
            task.completion_summary_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(task)
                db_session.commit()

            return result.text

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Task summarisation failed for task {task.id}: {e}")
            return None

    def summarise_instruction(self, task, command_text: str, db_session=None, reuse_summary: str | None = None) -> str | None:
        """Generate an instruction summary from the user's command text.

        Produces a 1-2 sentence summary of what the user instructed.
        When reuse_summary is provided (e.g. from a turn summary of the same
        command), it is used directly instead of making a separate LLM call.

        Args:
            task: Task model instance to persist the instruction to
            command_text: The full text of the user's command
            db_session: Database session for persisting
            reuse_summary: Pre-computed summary to reuse (avoids duplicate LLM call)

        Returns:
            The instruction text, or None if generation failed or skipped
        """
        # Return existing instruction if present
        if task.instruction:
            return task.instruction

        # Empty text guard
        if not command_text or not command_text.strip():
            logger.debug(f"Skipping instruction summarisation for task {task.id}: empty command text")
            return None

        # Reuse a pre-computed summary (e.g. from the turn_command summarisation)
        if reuse_summary:
            task.instruction = reuse_summary
            task.instruction_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(task)
                db_session.commit()

            logger.debug(f"Reused turn summary as instruction for task {task.id}")
            return reuse_summary

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping instruction summarisation")
            return None

        input_text = build_prompt("instruction", command_text=command_text)

        agent_id = task.agent_id if hasattr(task, "agent_id") else None
        project_id = None
        if hasattr(task, "agent") and task.agent:
            project_id = task.agent.project_id if hasattr(task.agent, "project_id") else None

        try:
            result = self._inference.infer(
                level="turn",
                purpose="summarise_instruction",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                task_id=task.id,
            )

            task.instruction = result.text
            task.instruction_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(task)
                db_session.commit()

            return result.text

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Instruction summarisation failed for task {task.id}: {e}")
            return None

    def execute_pending(self, requests, db_session) -> None:
        """Execute pending summarisation requests synchronously with SSE broadcasting.

        Called after db.session.commit() in the hook receiver to avoid the race
        condition where async threads can't find newly-created rows.

        When a turn (COMMAND intent) and instruction request are queued together,
        the turn summary is reused as the instruction — avoiding a duplicate LLM call.

        Args:
            requests: List of SummarisationRequest objects
            db_session: Database session for persisting summaries
        """
        # Track the last COMMAND turn summary so instruction requests can reuse it
        last_command_turn_summary = None

        for req in requests:
            try:
                if req.type == "turn" and req.turn:
                    summary = self.summarise_turn(req.turn, db_session=db_session)
                    if summary:
                        # Track COMMAND turn summaries for reuse by instruction requests
                        intent_value = req.turn.intent.value if hasattr(req.turn.intent, "value") else str(req.turn.intent)
                        if intent_value == "command":
                            last_command_turn_summary = summary

                        agent_id = req.turn.task.agent_id if req.turn.task else None
                        project_id = req.turn.task.agent.project_id if req.turn.task and req.turn.task.agent else None
                        self._broadcast_summary_update(
                            event_type="turn_summary",
                            entity_id=req.turn.id,
                            summary=summary,
                            agent_id=agent_id,
                            project_id=project_id,
                        )

                elif req.type == "instruction" and req.task:
                    instruction = self.summarise_instruction(
                        req.task, req.command_text, db_session=db_session,
                        reuse_summary=last_command_turn_summary,
                    )
                    if instruction:
                        agent_id = req.task.agent_id if hasattr(req.task, "agent_id") else None
                        project_id = req.task.agent.project_id if hasattr(req.task, "agent") and req.task.agent else None
                        self._broadcast_summary_update(
                            event_type="instruction_summary",
                            entity_id=req.task.id,
                            summary=instruction,
                            agent_id=agent_id,
                            project_id=project_id,
                        )

                elif req.type == "task_completion" and req.task:
                    completion = self.summarise_task(req.task, db_session=db_session)
                    if completion:
                        agent_id = req.task.agent_id if hasattr(req.task, "agent_id") else None
                        project_id = req.task.agent.project_id if hasattr(req.task, "agent") and req.task.agent else None
                        self._broadcast_summary_update(
                            event_type="task_summary",
                            entity_id=req.task.id,
                            summary=completion,
                            agent_id=agent_id,
                            project_id=project_id,
                            extra={"is_completion": True},
                        )

            except Exception as e:
                logger.warning(f"Pending summarisation failed for {req.type} (non-fatal): {e}")

    def _broadcast_summary_update(
        self,
        event_type: str,
        entity_id: int,
        summary: str,
        agent_id: int | None = None,
        project_id: int | None = None,
        extra: dict | None = None,
    ) -> None:
        """Broadcast a summary update via SSE."""
        try:
            from .broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            data = {
                "id": entity_id,
                "summary": summary,
            }
            if agent_id:
                data["agent_id"] = agent_id
            if project_id:
                data["project_id"] = project_id
            if extra:
                data.update(extra)

            broadcaster.broadcast(event_type, data)
            logger.debug(f"Broadcast {event_type} for entity {entity_id}")
        except Exception as e:
            logger.debug(f"Failed to broadcast summary update (non-fatal): {e}")

    @staticmethod
    def _resolve_turn_prompt(turn) -> str:
        """Build an intent-aware summarisation prompt for a turn.

        Uses different prompt templates based on the turn's intent,
        and includes the task instruction as context when available.
        """
        intent_value = turn.intent.value if hasattr(turn.intent, "value") else str(turn.intent)
        actor_value = turn.actor.value if hasattr(turn.actor, "value") else str(turn.actor)

        # Get task instruction context if available
        instruction_context = ""
        if hasattr(turn, "task") and turn.task:
            instruction = getattr(turn.task, "instruction", None)
            if instruction:
                instruction_context = f"Task instruction: {instruction}\n\n"

        # Select intent-specific template key
        prompt_type = f"turn_{intent_value}"
        try:
            return build_prompt(
                prompt_type,
                text=turn.text,
                actor=actor_value,
                intent=intent_value,
                instruction_context=instruction_context,
            )
        except KeyError:
            return build_prompt(
                "turn_default",
                text=turn.text,
                actor=actor_value,
                intent=intent_value,
                instruction_context=instruction_context,
            )

    @staticmethod
    def _resolve_task_prompt(task) -> str | None:
        """Build the completion summary prompt for a task.

        Primary inputs are the task instruction and the agent's final message.
        When the final turn text is empty, falls back to a summary of
        non-command turn activity to give the LLM context about what happened.
        """
        instruction = getattr(task, "instruction", None) or "No instruction recorded"

        turns = task.turns if hasattr(task, "turns") and task.turns else []
        final_turn_text = turns[-1].text.strip() if turns and turns[-1].text else ""

        if final_turn_text:
            return build_prompt(
                "task_completion",
                instruction=instruction,
                final_turn_text=final_turn_text,
            )

        # Final turn text is empty — build activity from non-command turns
        from ..models.turn import TurnIntent
        activity_lines = []
        for t in turns:
            intent_val = t.intent.value if hasattr(t.intent, "value") else str(t.intent)
            # Skip the initial command turn and turns with no text
            if intent_val == TurnIntent.COMMAND.value:
                continue
            text = (t.summary or t.text or "").strip()
            if not text:
                continue
            actor_val = t.actor.value if hasattr(t.actor, "value") else str(t.actor)
            activity_lines.append(f"- [{actor_val}/{intent_val}] {text[:200]}")

        if activity_lines:
            turn_activity = "\n".join(activity_lines)
            return build_prompt(
                "task_completion_from_activity",
                instruction=instruction,
                turn_activity=turn_activity,
            )

        # No turn activity at all — nothing meaningful to summarise
        return None
