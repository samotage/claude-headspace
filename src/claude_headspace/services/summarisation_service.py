"""Summarisation service for generating turn and task summaries via the inference layer."""

import logging
import threading
from datetime import datetime, timezone

from .inference_service import InferenceService, InferenceServiceError

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
        Uses the inference service at "turn" level.

        Args:
            turn: Turn model instance with text, actor, intent
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed
        """
        # Return existing summary if present (permanent caching via DB)
        if turn.summary:
            return turn.summary

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping turn summarisation")
            return None

        # Build prompt
        input_text = self._build_turn_prompt(turn)

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
        """Generate a summary for a completed task.

        If the task already has a summary, returns the existing summary.
        Uses the inference service at "task" level.

        Args:
            task: Task model instance with turns, started_at, completed_at
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed
        """
        # Return existing summary if present (permanent caching via DB)
        if task.summary:
            return task.summary

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping task summarisation")
            return None

        # Build prompt
        input_text = self._build_task_prompt(task)

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
            task.summary = result.text
            task.summary_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(task)
                db_session.commit()

            return result.text

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Task summarisation failed for task {task.id}: {e}")
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

                if task.summary:
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
    def _build_turn_prompt(turn) -> str:
        """Build the summarisation prompt for a turn."""
        actor_value = turn.actor.value if hasattr(turn.actor, "value") else str(turn.actor)
        intent_value = turn.intent.value if hasattr(turn.intent, "value") else str(turn.intent)

        return (
            f"Summarise this turn in 1-2 concise sentences focusing on "
            f"what action was taken or requested:\n\n"
            f"Turn: {turn.text}\n"
            f"Actor: {actor_value}\n"
            f"Intent: {intent_value}"
        )

    @staticmethod
    def _build_task_prompt(task) -> str:
        """Build the summarisation prompt for a task."""
        started = task.started_at.isoformat() if task.started_at else "unknown"
        completed = task.completed_at.isoformat() if task.completed_at else "unknown"

        # Count turns and get final turn text
        turns = task.turns if hasattr(task, "turns") and task.turns else []
        turn_count = len(turns)
        final_turn_text = turns[-1].text if turns else "No turns recorded"

        return (
            f"Summarise the outcome of this completed task in 2-3 sentences:\n\n"
            f"Task started: {started}\n"
            f"Task completed: {completed}\n"
            f"Turns: {turn_count}\n"
            f"Final outcome: {final_turn_text}"
        )
