"""Summarisation service for generating turn and task summaries via the inference layer."""

import logging
import threading
from datetime import datetime, timezone

from .inference_service import InferenceService, InferenceServiceError
from .prompt_registry import build_prompt

logger = logging.getLogger(__name__)


class SummarisationService:
    """Generates AI summaries for turns and tasks using the inference service."""

    def __init__(self, inference_service: InferenceService, app=None):
        """Initialize the summarisation service.

        Args:
            inference_service: The E3-S1 inference service for LLM calls
            app: Flask app instance for app context in async threads
        """
        self._inference = inference_service
        self._app = app

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

        # Empty text guard: skip if final turn text is not available
        turns = task.turns if hasattr(task, "turns") and task.turns else []
        if turns:
            final_turn_text = turns[-1].text
            if not final_turn_text or not final_turn_text.strip():
                logger.debug(f"Skipping task summarisation for task {task.id}: final turn text empty")
                return None

        # Build prompt
        input_text = self._resolve_task_prompt(task)

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

    def summarise_instruction(self, task, command_text: str, db_session=None) -> str | None:
        """Generate an instruction summary from the user's command text.

        Produces a 1-2 sentence summary of what the user instructed.

        Args:
            task: Task model instance to persist the instruction to
            command_text: The full text of the user's command
            db_session: Database session for persisting

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

    def summarise_turn_async(self, turn_id: int) -> None:
        """Trigger turn summarisation asynchronously.

        Runs in a background thread with Flask app context.
        Broadcasts SSE event on completion.

        Args:
            turn_id: ID of the turn to summarise
        """
        if not self._inference.is_available:
            return

        if not self._app:
            logger.warning("No Flask app available for async summarisation")
            return

        thread = threading.Thread(
            target=self._async_summarise_turn,
            args=(turn_id,),
            daemon=True,
            name=f"summarise-turn-{turn_id}",
        )
        thread.start()

    def summarise_task_async(self, task_id: int) -> None:
        """Trigger task summarisation asynchronously.

        Runs in a background thread with Flask app context.
        Broadcasts SSE event on completion.

        Args:
            task_id: ID of the task to summarise
        """
        if not self._inference.is_available:
            return

        if not self._app:
            logger.warning("No Flask app available for async summarisation")
            return

        thread = threading.Thread(
            target=self._async_summarise_task,
            args=(task_id,),
            daemon=True,
            name=f"summarise-task-{task_id}",
        )
        thread.start()

    def summarise_instruction_async(self, task_id: int, command_text: str) -> None:
        """Trigger instruction summarisation asynchronously.

        Runs in a background thread with Flask app context.
        Broadcasts SSE event on completion.

        Args:
            task_id: ID of the task to generate instruction for
            command_text: The user's command text
        """
        if not self._inference.is_available:
            return

        if not self._app:
            logger.warning("No Flask app available for async summarisation")
            return

        if not command_text or not command_text.strip():
            return

        thread = threading.Thread(
            target=self._async_summarise_instruction,
            args=(task_id, command_text),
            daemon=True,
            name=f"summarise-instruction-{task_id}",
        )
        thread.start()

    def _async_summarise_turn(self, turn_id: int) -> None:
        """Background thread handler for turn summarisation."""
        try:
            with self._app.app_context():
                from ..database import db as flask_db
                from ..models.turn import Turn

                turn = flask_db.session.get(Turn, turn_id)
                if not turn:
                    logger.warning(f"Turn {turn_id} not found for async summarisation")
                    return

                if turn.summary:
                    return  # Already summarised

                summary = self.summarise_turn(turn, db_session=flask_db.session)

                if summary:
                    self._broadcast_summary_update(
                        event_type="turn_summary",
                        entity_id=turn_id,
                        summary=summary,
                        agent_id=turn.task.agent_id if turn.task else None,
                        project_id=turn.task.agent.project_id if turn.task and turn.task.agent else None,
                    )

        except Exception as e:
            logger.error(f"Async turn summarisation failed for turn {turn_id}: {e}")

    def _async_summarise_task(self, task_id: int) -> None:
        """Background thread handler for task summarisation."""
        try:
            with self._app.app_context():
                from ..database import db as flask_db
                from ..models.task import Task

                task = flask_db.session.get(Task, task_id)
                if not task:
                    logger.warning(f"Task {task_id} not found for async summarisation")
                    return

                if task.completion_summary:
                    return  # Already summarised

                summary = self.summarise_task(task, db_session=flask_db.session)

                if summary:
                    self._broadcast_summary_update(
                        event_type="task_summary",
                        entity_id=task_id,
                        summary=summary,
                        agent_id=task.agent_id,
                        project_id=task.agent.project_id if task.agent else None,
                    )

        except Exception as e:
            logger.error(f"Async task summarisation failed for task {task_id}: {e}")

    def _async_summarise_instruction(self, task_id: int, command_text: str) -> None:
        """Background thread handler for instruction summarisation."""
        try:
            with self._app.app_context():
                from ..database import db as flask_db
                from ..models.task import Task

                task = flask_db.session.get(Task, task_id)
                if not task:
                    logger.warning(f"Task {task_id} not found for async instruction summarisation")
                    return

                if task.instruction:
                    return  # Already has instruction

                instruction = self.summarise_instruction(task, command_text, db_session=flask_db.session)

                if instruction:
                    self._broadcast_summary_update(
                        event_type="instruction_summary",
                        entity_id=task_id,
                        summary=instruction,
                        agent_id=task.agent_id,
                        project_id=task.agent.project_id if task.agent else None,
                    )

        except Exception as e:
            logger.error(f"Async instruction summarisation failed for task {task_id}: {e}")

    def _broadcast_summary_update(
        self,
        event_type: str,
        entity_id: int,
        summary: str,
        agent_id: int | None = None,
        project_id: int | None = None,
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
    def _resolve_task_prompt(task) -> str:
        """Build the completion summary prompt for a task.

        Primary inputs are the task instruction and the agent's final message.
        Does not include timestamps or turn counts.
        """
        instruction = getattr(task, "instruction", None) or "No instruction recorded"

        turns = task.turns if hasattr(task, "turns") and task.turns else []
        final_turn_text = turns[-1].text if turns else "No final message recorded"

        return build_prompt(
            "task_completion",
            instruction=instruction,
            final_turn_text=final_turn_text,
        )
