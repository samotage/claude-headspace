"""Summarisation service for generating turn and command summaries via the inference layer."""

import json
import logging
import re
from datetime import datetime, timezone

from .inference_service import InferenceService, InferenceServiceError
from .prompt_registry import build_prompt

logger = logging.getLogger(__name__)

# Matches LLM preamble like "Here's a concise 18-token summary of..."
# Only strips when the line contains summarisation-related words to avoid
# false positives on legitimate content starting with "Here's".
_PREAMBLE_RE = re.compile(
    r"^(?:Sure[,.]?\s+)?"
    r"(?:Here(?:'s| is)\s+(?:a |the )?(?:very )?"
    r"(?:concise|brief|short|quick|simple)[\s\S]*?:\s*\n?)",
    re.IGNORECASE,
)

# Short confirmations that don't warrant LLM summarisation.
# Matched against lowercased, stripped turn text.
_TRIVIAL_CONFIRMATIONS = frozenset({
    "y", "yes", "ok", "okay", "k", "sure", "go", "go ahead",
    "do it", "proceed", "continue", "yep", "yup", "yeah",
    "confirmed", "approve", "approved", "accept", "right",
    "correct", "affirmative", "ack", "agreed", "sounds good",
    "looks good", "lgtm", "ship it",
})

# Slash-command pattern: /word or /word:word (with optional arguments after space)
_SLASH_COMMAND_RE = re.compile(r"^(/[\w:.=-]+)")

# Maximum character length to consider for trivial input bypass.
# Anything longer than this is sent to the LLM regardless.
_TRIVIAL_MAX_LENGTH = 40


class SummarisationService:
    """Generates AI summaries for turns and commands using the inference service."""

    def __init__(self, inference_service: InferenceService, config: dict | None = None):
        """Initialize the summarisation service.

        Args:
            inference_service: The E3-S1 inference service for LLM calls
            config: Application config dict (for headspace settings)
        """
        self._inference = inference_service
        headspace_config = (config or {}).get("headspace", {})
        self._headspace_enabled = headspace_config.get("enabled", True)

    @staticmethod
    def _clean_response(text: str) -> str:
        """Strip common LLM preamble and markdown fences from summary responses.

        Models sometimes echo back the prompt structure, e.g.
        "Here's a concise 18-token summary: <actual summary>".
        Some models (e.g. Haiku 4.5) also wrap output in markdown code fences.
        This method strips such artifacts and returns the actual content.
        """
        cleaned = text.strip()
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.match(r"^```(?:\w+)?\s*\n?(.*?)\n?\s*```$", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        cleaned = _PREAMBLE_RE.sub("", cleaned).strip()
        return cleaned if cleaned else text

    @staticmethod
    def _check_trivial_input(turn) -> str | None:
        """Check if turn text is trivial and return a direct summary without LLM.

        Handles two cases:
        1. Slash commands (/start-queue, /commit, etc.) — the command name is
           used directly as the summary since it IS the command description.
        2. Short confirmations (yes, ok, go ahead, etc.) — returns a brief
           confirmation label instead of wasting an LLM call on one word.

        Returns:
            A summary string if the input is trivial, None to proceed with LLM.
        """
        text = (turn.text or "").strip()
        if not text or len(text) > _TRIVIAL_MAX_LENGTH:
            return None

        # Slash commands: use the command portion as the summary
        m = _SLASH_COMMAND_RE.match(text)
        if m:
            return m.group(1)

        # Short confirmations: return a brief label
        normalised = text.lower().rstrip(".!,")
        if normalised in _TRIVIAL_CONFIRMATIONS:
            return "Confirmed"

        return None

    def summarise_turn(self, turn, db_session=None) -> str | None:
        """Generate a summary for a turn.

        If the turn already has a summary, returns the existing summary.
        Skips summarisation when turn text is None or empty.
        Bypasses LLM for trivial inputs (slash commands, short confirmations).
        Uses intent-aware prompts with command instruction context.

        Args:
            turn: Turn model instance with text, actor, intent
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed or skipped
        """
        # Return existing summary if present (permanent caching via DB)
        if turn.summary:
            return turn.summary

        # Internal turn guard: skip summarisation for system plumbing turns
        # (e.g. persona skill injection priming messages).
        # Use `is True` for strict comparison — avoids MagicMock truthiness in tests.
        if getattr(turn, 'is_internal', False) is True:
            logger.debug(f"Skipping turn summarisation for turn {turn.id}: is_internal=True")
            return None

        # Empty text guard: skip summarisation when text is None/empty
        if not turn.text or not turn.text.strip():
            logger.debug(f"Skipping turn summarisation for turn {turn.id}: empty text")
            return None

        # Row-level dedup: SELECT ... FOR UPDATE NOWAIT to prevent concurrent
        # summarisation of the same turn. If another thread holds the row lock,
        # we skip immediately instead of making a duplicate LLM call.
        if db_session and hasattr(turn, 'id') and turn.id:
            try:
                from sqlalchemy.orm import Session as SASession
                from ..models.turn import Turn as TurnModel

                # Only attempt row lock with a real SQLAlchemy session
                if isinstance(db_session, SASession):
                    locked_turn = (
                        db_session.query(TurnModel)
                        .filter(TurnModel.id == turn.id)
                        .with_for_update(nowait=True)
                        .first()
                    )
                    if locked_turn and isinstance(locked_turn.summary, str) and locked_turn.summary:
                        # Another thread completed summarisation while we waited
                        return locked_turn.summary
                    if locked_turn:
                        turn = locked_turn
            except Exception as e:
                # OperationalError from FOR UPDATE NOWAIT = another thread has the row
                error_str = str(e)
                if "could not obtain lock" in error_str or "lock not available" in error_str:
                    logger.debug(
                        f"Turn {turn.id} row locked by another thread — skipping summarisation"
                    )
                    try:
                        db_session.rollback()
                    except Exception:
                        pass
                    return None
                # Other errors: log and continue without the row lock
                logger.debug(f"FOR UPDATE NOWAIT failed for turn {turn.id}: {e}")
                try:
                    db_session.rollback()
                except Exception:
                    pass

        # Trivial input bypass: skip LLM for slash commands and short confirmations
        trivial = self._check_trivial_input(turn)
        if trivial is not None:
            logger.debug(f"Trivial input bypass for turn {turn.id}: {trivial!r}")
            turn.summary = trivial
            turn.summary_generated_at = datetime.now(timezone.utc)
            if db_session:
                db_session.add(turn)
                db_session.commit()
            return trivial

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping turn summarisation")
            return None

        # Check if project inference is paused
        if hasattr(turn, "command") and turn.command:
            agent = getattr(turn.command, "agent", None)
            if agent:
                project = getattr(agent, "project", None)
                if project and getattr(project, "inference_paused", None) is True:
                    logger.debug("Skipping turn summarisation for turn %s: project %s inference paused", turn.id, project.id)
                    return None

        # Determine if this is a USER turn eligible for frustration extraction
        actor_value = turn.actor.value if hasattr(turn.actor, "value") else str(turn.actor)
        use_frustration_prompt = self._headspace_enabled and actor_value == "user"

        # Build prompt
        if use_frustration_prompt:
            input_text = self._resolve_frustration_prompt(turn)
        else:
            input_text = self._resolve_turn_prompt(turn)

        # Get entity associations for InferenceCall logging
        command_id = turn.command_id if turn.command_id else None
        agent_id = None
        project_id = None
        if hasattr(turn, "command") and turn.command:
            agent_id = turn.command.agent_id if hasattr(turn.command, "agent_id") else None
            if hasattr(turn.command, "agent") and turn.command.agent:
                project_id = turn.command.agent.project_id if hasattr(turn.command.agent, "project_id") else None

        # Step 1: Inference call
        try:
            result = self._inference.infer(
                level="turn",
                purpose="summarise_turn",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn.id,
            )
        except (InferenceServiceError, Exception) as e:
            logger.error(f"Turn summarisation inference failed for turn {turn.id}: {e}")
            return None

        # Step 2: Parse response
        summary = None
        frustration_score = None
        try:
            if use_frustration_prompt:
                summary, frustration_score = self._parse_frustration_response(result.text)
            else:
                summary = self._clean_response(result.text)
        except Exception as e:
            logger.error(f"Turn summarisation parse failed for turn {turn.id}: {e}")
            # Fall back to raw text
            summary = self._clean_response(result.text) if result and result.text else None

        # Step 3: Persist whatever succeeded
        if summary:
            try:
                turn.summary = summary
                turn.summary_generated_at = datetime.now(timezone.utc)
                if frustration_score is not None:
                    turn.frustration_score = frustration_score

                if db_session:
                    db_session.add(turn)
                    db_session.commit()
            except Exception as e:
                logger.error(f"Turn summarisation persist failed for turn {turn.id}: {e}")

        # Trigger headspace recalculation after successful summarisation
        if frustration_score is not None:
            try:
                self._trigger_headspace_recalculation(turn)
            except Exception as e:
                logger.warning(f"Headspace recalculation trigger failed (non-fatal): {e}")

        return summary

    def summarise_permission(self, turn, db_session=None) -> str | None:
        """Generate a summary for a permission request turn via LLM.

        Extracts tool_name and command from the turn's context (tool_input or text)
        and generates a concise summary like "Bash: curl from localhost".

        Args:
            turn: Turn model instance with text containing the permission question
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed or skipped
        """
        if turn.summary:
            return turn.summary

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping permission summarisation")
            return None

        # Extract tool name and command from the turn context
        tool_name = "Unknown"
        command = ""
        description_line = ""

        # Parse from tool_input (synthesized permission context)
        tool_input = turn.tool_input
        if tool_input and isinstance(tool_input, dict):
            # Get tool name from the question text
            questions = tool_input.get("questions", [])
            if questions and isinstance(questions, list):
                q_text = questions[0].get("question", "")
                if q_text and ":" in q_text:
                    tool_name = q_text.split(":")[0].strip()

            # Get command from command_context
            cmd_ctx = tool_input.get("command_context", {})
            if cmd_ctx:
                command = cmd_ctx.get("command", "")
                desc = cmd_ctx.get("description", "")
                if desc:
                    description_line = f"Description: {desc}\n"

        # Fallback: parse from turn text
        if not command and turn.text:
            command = turn.text

        if not command:
            logger.debug(f"No command content for permission summary, turn {turn.id}")
            return None

        input_text = build_prompt(
            "permission_summary",
            tool_name=tool_name,
            command=command,
            description_line=description_line,
        )

        # Get entity associations
        command_id = turn.command_id if turn.command_id else None
        agent_id = None
        project_id = None
        if hasattr(turn, "command") and turn.command:
            agent_id = turn.command.agent_id if hasattr(turn.command, "agent_id") else None
            if hasattr(turn.command, "agent") and turn.command.agent:
                project_id = turn.command.agent.project_id if hasattr(turn.command.agent, "project_id") else None

        try:
            result = self._inference.infer(
                level="turn",
                purpose="summarise_permission",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn.id,
            )

            summary = self._clean_response(result.text)
            turn.summary = summary
            turn.summary_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(turn)
                db_session.commit()

            return summary

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Permission summarisation failed for turn {turn.id}: {e}")
            return None

    def summarise_command(self, command, db_session=None) -> str | None:
        """Generate a completion summary for a completed command.

        If the command already has a completion_summary, returns it.
        Skips summarisation if the final turn text is empty.
        Uses command instruction + final agent message as primary inputs.

        Args:
            command: Command model instance with turns, instruction
            db_session: Database session for persisting the summary

        Returns:
            The summary text, or None if generation failed or skipped
        """
        # Return existing summary if present (permanent caching via DB)
        if command.completion_summary:
            return command.completion_summary

        # Internal turns guard: skip if all user turns are internal
        # (e.g. command created entirely by persona injection priming)
        try:
            turns = command.turns if hasattr(command, "turns") and command.turns else []
        except Exception:
            turns = []
        if turns:
            user_turns = [t for t in turns if hasattr(t, 'actor') and (t.actor.value if hasattr(t.actor, 'value') else str(t.actor)) == 'user']
            if user_turns and all(getattr(t, 'is_internal', False) is True for t in user_turns):
                logger.debug(f"Skipping command summarisation for command {command.id}: all user turns are internal")
                return None

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping command summarisation")
            return None

        # Check if project inference is paused
        agent = getattr(command, "agent", None)
        if agent:
            project = getattr(agent, "project", None)
            if project and getattr(project, "inference_paused", None) is True:
                logger.debug("Skipping command summarisation for command %s: project %s inference paused", command.id, project.id)
                return None

        # Build prompt — returns None when there's nothing to summarise
        input_text = self._resolve_command_prompt(command)
        if input_text is None:
            logger.debug("No content to summarise for command %s, skipping", command.id)
            return None

        # Get entity associations for InferenceCall logging
        agent_id = command.agent_id if hasattr(command, "agent_id") else None
        project_id = None
        if hasattr(command, "agent") and command.agent:
            project_id = command.agent.project_id if hasattr(command.agent, "project_id") else None

        try:
            result = self._inference.infer(
                level="command",
                purpose="summarise_command",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command.id,
            )

            # Persist summary to command model (strip LLM preamble)
            summary = self._clean_response(result.text)
            command.completion_summary = summary
            command.completion_summary_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(command)
                db_session.commit()

            return summary

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Command summarisation failed for command {command.id}: {e}")
            return None

    def summarise_instruction(self, command, command_text: str, db_session=None, reuse_summary: str | None = None) -> str | None:
        """Generate an instruction summary from the user's command text.

        Produces a 1-2 sentence summary of what the user instructed.
        When reuse_summary is provided (e.g. from a turn summary of the same
        command), it is used directly instead of making a separate LLM call.

        Args:
            command: Command model instance to persist the instruction to
            command_text: The full text of the user's command
            db_session: Database session for persisting
            reuse_summary: Pre-computed summary to reuse (avoids duplicate LLM call)

        Returns:
            The instruction text, or None if generation failed or skipped
        """
        # Return existing instruction if present
        if command.instruction:
            return command.instruction

        # Empty text guard
        if not command_text or not command_text.strip():
            logger.debug(f"Skipping instruction summarisation for command {command.id}: empty command text")
            return None

        # Internal turns guard: skip if all user turns on this command are internal
        try:
            turns = command.turns if hasattr(command, "turns") and command.turns else []
        except Exception:
            turns = []
        if turns:
            user_turns = [t for t in turns if hasattr(t, 'actor') and (t.actor.value if hasattr(t.actor, 'value') else str(t.actor)) == 'user']
            if user_turns and all(getattr(t, 'is_internal', False) is True for t in user_turns):
                logger.debug(f"Skipping instruction summarisation for command {command.id}: all user turns are internal")
                return None

        # Slash command bypass: use the command name directly as the instruction
        stripped = command_text.strip()
        m = _SLASH_COMMAND_RE.match(stripped)
        if m:
            command.instruction = m.group(1)
            command.instruction_generated_at = datetime.now(timezone.utc)
            if db_session:
                db_session.add(command)
                db_session.commit()
            logger.info(f"Slash command bypass for command {command.id}: {command.instruction!r}")
            return command.instruction

        # Reuse a pre-computed summary (e.g. from the turn_command summarisation)
        if reuse_summary:
            command.instruction = self._clean_response(reuse_summary)
            command.instruction_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(command)
                db_session.commit()

            logger.debug(f"Reused turn summary as instruction for command {command.id}")
            return command.instruction

        if not self._inference.is_available:
            logger.debug("Inference service unavailable, skipping instruction summarisation")
            return None

        # Check if project inference is paused
        agent = getattr(command, "agent", None)
        if agent:
            project = getattr(agent, "project", None)
            if project and getattr(project, "inference_paused", None) is True:
                logger.debug("Skipping instruction summarisation for command %s: project %s inference paused", command.id, project.id)
                return None

        input_text = build_prompt("instruction", command_text=command_text)

        agent_id = command.agent_id if hasattr(command, "agent_id") else None
        project_id = None
        if hasattr(command, "agent") and command.agent:
            project_id = command.agent.project_id if hasattr(command.agent, "project_id") else None

        try:
            result = self._inference.infer(
                level="turn",
                purpose="summarise_instruction",
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command.id,
            )

            instruction = self._clean_response(result.text)
            command.instruction = instruction
            command.instruction_generated_at = datetime.now(timezone.utc)

            if db_session:
                db_session.add(command)
                db_session.commit()

            return instruction

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Instruction summarisation failed for command {command.id}: {e}")
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

        # Check if batch contains an instruction request — if so, suppress
        # intermediate card_refresh from turn summaries to avoid a flicker
        # where the card briefly shows "No instruction" before the instruction
        # summary arrives.
        has_instruction_request = any(r.type == "instruction" for r in requests)

        for req in requests:
            try:
                if req.type == "turn" and req.turn:
                    summary = self.summarise_turn(req.turn, db_session=db_session)
                    if summary:
                        # Track COMMAND turn summaries for reuse by instruction requests
                        intent_value = req.turn.intent.value if hasattr(req.turn.intent, "value") else str(req.turn.intent)
                        if intent_value == "command":
                            last_command_turn_summary = summary

                        agent_id = req.turn.command.agent_id if req.turn.command else None
                        project_id = req.turn.command.agent.project_id if req.turn.command and req.turn.command.agent else None
                        self._broadcast_summary_update(
                            event_type="turn_summary",
                            entity_id=req.turn.id,
                            summary=summary,
                            agent_id=agent_id,
                            project_id=project_id,
                        )
                        if not has_instruction_request:
                            self._broadcast_card_refresh_for_agent(agent_id, db_session, "turn_summary_updated")

                elif req.type == "instruction" and req.command:
                    instruction = self.summarise_instruction(
                        req.command, req.command_text, db_session=db_session,
                        reuse_summary=last_command_turn_summary,
                    )
                    if instruction:
                        agent_id = req.command.agent_id if hasattr(req.command, "agent_id") else None
                        project_id = req.command.agent.project_id if hasattr(req.command, "agent") and req.command.agent else None
                        self._broadcast_summary_update(
                            event_type="instruction_summary",
                            entity_id=req.command.id,
                            summary=instruction,
                            agent_id=agent_id,
                            project_id=project_id,
                        )
                        self._broadcast_card_refresh_for_agent(agent_id, db_session, "instruction_updated")

                elif req.type == "command_completion" and req.command:
                    completion = self.summarise_command(req.command, db_session=db_session)
                    if completion:
                        agent_id = req.command.agent_id if hasattr(req.command, "agent_id") else None
                        project_id = req.command.agent.project_id if hasattr(req.command, "agent") and req.command.agent else None
                        self._broadcast_summary_update(
                            event_type="command_summary",
                            entity_id=req.command.id,
                            summary=completion,
                            agent_id=agent_id,
                            project_id=project_id,
                            extra={"is_completion": True},
                        )
                        self._broadcast_card_refresh_for_agent(agent_id, db_session, "command_summary_updated")

                elif req.type == "permission_summary" and req.turn:
                    summary = self.summarise_permission(req.turn, db_session=db_session)
                    if summary:
                        agent_id = req.turn.command.agent_id if req.turn.command else None
                        self._broadcast_card_refresh_for_agent(agent_id, db_session, "permission_summary_updated")

            except Exception as e:
                logger.warning(f"Pending summarisation failed for {req.type} (non-fatal): {e}")

    @staticmethod
    def _broadcast_card_refresh_for_agent(agent_id: int | None, db_session, reason: str) -> None:
        """Load agent and broadcast card_refresh. No-op if agent not found."""
        if not agent_id:
            return
        try:
            from ..models.agent import Agent
            from .card_state import broadcast_card_refresh

            agent = db_session.get(Agent, agent_id)
            if agent:
                broadcast_card_refresh(agent, reason)
        except Exception as e:
            logger.info(f"card_refresh for agent {agent_id} failed (non-fatal): {e}")

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
            logger.info(f"Broadcast {event_type} for entity {entity_id}")
        except Exception as e:
            logger.warning(f"Failed to broadcast summary update (non-fatal): {e}")

    @staticmethod
    def _get_prior_command_context(turn) -> str:
        """Get context from the previous command for this agent.

        For COMMAND turns that create a new command, the current command has no
        instruction yet. The user's command may implicitly reference work
        from the previous command (e.g. "verify" without saying what).
        This method provides that continuity.
        """
        try:
            command = turn.command if hasattr(turn, "command") else None
            if not command:
                return ""
            agent = getattr(command, "agent", None)
            if not agent or not hasattr(agent, "commands"):
                return ""

            # Find the previous command (the one before the current one)
            prior_commands = [
                t for t in agent.commands
                if t.id < command.id and t.instruction
            ]
            if not prior_commands:
                return ""

            prior = prior_commands[0]  # Most recent prior command with an instruction
            parts = [f"Prior command: {prior.instruction}"]
            if prior.completion_summary:
                parts.append(f"Prior outcome: {prior.completion_summary}")
            return "\n".join(parts) + "\n\n"
        except Exception as e:
            logger.warning(f"Failed to fetch prior command context: {e}")
            return ""

    @staticmethod
    def _resolve_turn_prompt(turn) -> str:
        """Build an intent-aware summarisation prompt for a turn.

        Uses different prompt templates based on the turn's intent,
        and includes the command instruction as context when available.
        For COMMAND turns without a command instruction, includes prior
        command context to help the LLM understand implicit references.
        """
        intent_value = turn.intent.value if hasattr(turn.intent, "value") else str(turn.intent)
        actor_value = turn.actor.value if hasattr(turn.actor, "value") else str(turn.actor)

        # Get command instruction context if available
        instruction_context = ""
        if hasattr(turn, "command") and turn.command:
            instruction = getattr(turn.command, "instruction", None)
            if instruction:
                instruction_context = f"Command instruction: {instruction}\n\n"
            elif intent_value == "command":
                # COMMAND turns have no instruction yet — use prior command for context
                instruction_context = SummarisationService._get_prior_command_context(turn)

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
    def _resolve_command_prompt(command) -> str | None:
        """Build the completion summary prompt for a command.

        Primary inputs are the command instruction and the agent's final message.
        When the final turn text is empty, falls back to a summary of
        non-command turn activity to give the LLM context about what happened.
        """
        instruction = getattr(command, "instruction", None) or "No instruction recorded"

        try:
            turns = command.turns if hasattr(command, "turns") and command.turns else []
        except Exception as e:
            # Guard against DetachedInstanceError when command was loaded in a
            # different session context (e.g. post-commit summarisation).
            logger.warning(f"Failed to access command.turns for command {command.id} (defaulting to empty): {e}")
            turns = []
        final_turn_text = turns[-1].text.strip() if turns and turns[-1].text else ""

        if final_turn_text:
            return build_prompt(
                "command_completion",
                instruction=instruction,
                final_turn_text=final_turn_text,
            )

        # Final turn text is empty — build activity from all turns with content
        activity_lines = []
        for t in turns:
            text = (t.summary or t.text or "").strip()
            if not text:
                continue
            actor_val = t.actor.value if hasattr(t.actor, "value") else str(t.actor)
            intent_val = t.intent.value if hasattr(t.intent, "value") else str(t.intent)
            activity_lines.append(f"- [{actor_val}/{intent_val}] {text[:200]}")

        if activity_lines:
            turn_activity = "\n".join(activity_lines)
            return build_prompt(
                "command_completion_from_activity",
                instruction=instruction,
                turn_activity=turn_activity,
            )

        # No turn activity — fall back to instruction-only prompt
        if instruction and instruction != "No instruction recorded":
            return build_prompt(
                "command_completion_from_instruction",
                instruction=instruction,
            )

        return None

    @staticmethod
    def _resolve_frustration_prompt(turn) -> str:
        """Build the frustration-aware summarisation prompt for a user turn.

        For COMMAND turns where the current command has no instruction yet,
        includes prior command context to help the LLM understand implicit
        references in the user's message.
        """
        instruction_context = ""
        if hasattr(turn, "command") and turn.command:
            instruction = getattr(turn.command, "instruction", None)
            if instruction:
                instruction_context = f"Command instruction: {instruction}\n\n"
            else:
                # No instruction yet — use prior command for context
                instruction_context = SummarisationService._get_prior_command_context(turn)

        return build_prompt(
            "turn_frustration",
            text=turn.text,
            instruction_context=instruction_context,
        )

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Strip markdown code fences from LLM responses.

        Some models (e.g. Claude Haiku 4.5) wrap JSON output in ```json ... ```
        even when instructed to return only valid JSON.  The closing fence may
        not be at the very end of the string (trailing explanation text, extra
        newlines, etc.), so we use a non-greedy match that doesn't require ``$``.
        """
        stripped = text.strip()
        # Match opening ```json / ``` then content then closing ``` (not anchored to end)
        fence_re = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
        m = fence_re.match(stripped)
        if m:
            return m.group(1).strip()
        return stripped

    @classmethod
    def _parse_frustration_response(cls, text: str) -> tuple[str, int | None]:
        """Parse a frustration-aware LLM response.

        Attempts to parse JSON with summary and frustration_score.
        Strips markdown code fences before parsing since some models
        wrap JSON output in ```json ... ``` blocks.
        Falls back to extracting the summary field via regex, then to
        treating the entire response as plain text.

        Returns:
            Tuple of (summary, frustration_score). frustration_score is None on parse failure.
        """
        cleaned_text = cls._strip_markdown_fences(text)
        try:
            data = json.loads(cleaned_text)
            summary = cls._clean_response(str(data.get("summary", cleaned_text)))
            score = data.get("frustration_score")
            if isinstance(score, (int, float)) and 0 <= score <= 10:
                return summary, int(score)
            return summary, None
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # json.loads failed — try to find a JSON object in the text and parse it
        obj_match = re.search(r"\{[^{}]*\}", cleaned_text)
        if obj_match:
            try:
                data = json.loads(obj_match.group())
                summary = cls._clean_response(str(data.get("summary", "")))
                if summary:
                    score = data.get("frustration_score")
                    if isinstance(score, (int, float)) and 0 <= score <= 10:
                        return summary, int(score)
                    return summary, None
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Last resort: extract the "summary" value with regex
        summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned_text)
        if summary_match:
            return cls._clean_response(summary_match.group(1)), None

        # Nothing worked — return cleaned text (strip any remaining JSON artifacts)
        fallback = cls._clean_response(cleaned_text)
        # If it still looks like JSON, don't return it
        if fallback.lstrip().startswith("{"):
            return "Summary unavailable", None
        return fallback, None

    def _trigger_headspace_recalculation(self, turn) -> None:
        """Trigger headspace monitor recalculation after frustration extraction."""
        try:
            from flask import current_app
            monitor = current_app.extensions.get("headspace_monitor")
            if monitor:
                monitor.recalculate(turn)
        except Exception as e:
            logger.warning(f"Headspace recalculation failed (non-fatal): {e}")
