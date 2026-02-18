"""Priority scoring service for cross-project agent prioritisation via LLM inference."""

import json
import logging
import re
import threading
from datetime import datetime, timezone

from .inference_service import InferenceService, InferenceServiceError
from .prompt_registry import build_prompt

logger = logging.getLogger(__name__)


class PriorityScoringService:
    """Scores all active agents 0-100 using LLM inference with objective/waypoint context."""

    def __init__(self, inference_service: InferenceService, app=None, config: dict | None = None):
        self._inference = inference_service
        self._app = app
        self._debounce_timer: threading.Timer | None = None
        self._debounce_lock = threading.Lock()
        self._scoring_lock = threading.Lock()

        ps_config = (config or {}).get("openrouter", {}).get("priority_scoring", {})
        self._debounce_seconds = ps_config.get("debounce_seconds", 5.0)

    def score_all_agents(self, db_session) -> dict:
        """Score all active agents in a single batch inference call.

        Uses _scoring_lock to prevent concurrent scoring runs from
        overlapping and overwriting each other's results.

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Dict with scored agents list, count, and context_type
        """
        if not self._scoring_lock.acquire(blocking=False):
            logger.debug("Scoring already in progress, skipping")
            return {"scored": 0, "agents": [], "context_type": "skipped"}
        try:
            return self._score_all_agents_impl(db_session)
        finally:
            self._scoring_lock.release()

    def _score_all_agents_impl(self, db_session) -> dict:
        """Internal implementation of score_all_agents."""
        from ..models.agent import Agent
        from ..models.objective import Objective
        from ..models.project import Project

        # Check if priority scoring is disabled
        objective = db_session.query(Objective).first()
        if objective and not objective.priority_enabled:
            return {"scored": 0, "agents": [], "context_type": "disabled"}

        # Gather active agents (not ended), excluding agents from paused projects
        agents = (
            db_session.query(Agent)
            .join(Agent.project)
            .filter(Agent.ended_at.is_(None))
            .filter(Project.inference_paused == False)  # noqa: E712
            .all()
        )

        if not agents:
            return {"scored": 0, "agents": [], "context_type": "none"}

        # Get scoring context (objective → waypoint → default)
        context = self._get_scoring_context(db_session, agents)

        if context["context_type"] == "default":
            # No inference call needed — assign default scores
            now = datetime.now(timezone.utc)
            scored = []
            for agent in agents:
                agent.priority_score = 50
                agent.priority_reason = "No scoring context available"
                agent.priority_updated_at = now
                scored.append({
                    "agent_id": agent.id,
                    "score": 50,
                    "reason": "No scoring context available",
                    "scored_at": now.isoformat(),
                })
            db_session.commit()
            self._broadcast_score_update(scored)
            self._broadcast_card_refreshes(agents, "priority_scored")
            return {"scored": len(scored), "agents": scored, "context_type": "default"}

        # Build prompt and call inference
        prompt = self._build_scoring_prompt(context, agents)

        try:
            result = self._inference.infer(
                level="objective",
                purpose="priority_scoring",
                input_text=prompt,
            )

            agent_ids = [a.id for a in agents]
            parsed = self._parse_scoring_response(result.text, agent_ids)

            # Persist scores
            now = datetime.now(timezone.utc)
            agent_map = {a.id: a for a in agents}
            scored = []
            for entry in parsed:
                agent = agent_map.get(entry["agent_id"])
                if agent:
                    agent.priority_score = entry["score"]
                    agent.priority_reason = entry["reason"]
                    agent.priority_updated_at = now
                    scored.append({
                        "agent_id": agent.id,
                        "score": entry["score"],
                        "reason": entry["reason"],
                        "scored_at": now.isoformat(),
                    })

            db_session.commit()
            self._broadcast_score_update(scored)
            self._broadcast_card_refreshes(agents, "priority_scored")
            return {"scored": len(scored), "agents": scored, "context_type": context["context_type"]}

        except (InferenceServiceError, Exception) as e:
            logger.error(f"Priority scoring failed: {e}")
            return {"scored": 0, "agents": [], "context_type": context["context_type"], "error": str(e)}

    def score_all_agents_async(self) -> None:
        """Trigger scoring asynchronously in a background thread."""
        if not self._inference.is_available:
            return

        if not self._app:
            logger.warning("No Flask app available for async priority scoring")
            return

        thread = threading.Thread(
            target=self._async_score,
            daemon=True,
            name="priority-scoring",
        )
        thread.start()

    def trigger_scoring(self) -> None:
        """Rate-limited trigger with debounce. Thread-safe."""
        if not self._inference.is_available:
            return

        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self._debounce_seconds,
                self.score_all_agents_async,
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def trigger_scoring_immediate(self) -> None:
        """Bypass debounce for objective changes. Cancels pending timer."""
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        self.score_all_agents_async()

    def _async_score(self) -> None:
        """Background thread handler for scoring."""
        try:
            with self._app.app_context():
                from ..database import db as flask_db
                self.score_all_agents(flask_db.session)
        except Exception as e:
            logger.error(f"Async priority scoring failed: {e}")

    def _get_scoring_context(self, db_session, agents) -> dict:
        """Get scoring context via fallback chain: objective → waypoint → default."""
        from ..models.objective import Objective

        # Try objective first
        objective = (
            db_session.query(Objective)
            .order_by(Objective.set_at.desc())
            .first()
        )
        if objective:
            return {
                "context_type": "objective",
                "text": objective.current_text,
                "constraints": objective.constraints or "",
            }

        # Try waypoints from agent projects
        from ..services.waypoint_editor import load_waypoint

        waypoint_data = {}
        for agent in agents:
            if agent.project and agent.project.path:
                if agent.project.path not in waypoint_data:
                    try:
                        wp = load_waypoint(agent.project.path)
                        if wp.exists:
                            waypoint_data[agent.project.path] = wp.content
                    except Exception as e:
                        logger.debug(f"Failed to load waypoint for {agent.project.path}: {e}")

        if waypoint_data:
            # Parse Next Up and Upcoming sections from waypoint content
            sections = []
            for path, content in waypoint_data.items():
                next_up = self._extract_section(content, "Next Up")
                upcoming = self._extract_section(content, "Upcoming")
                if next_up or upcoming:
                    sections.append(f"Project ({path}):\n  Next Up: {next_up}\n  Upcoming: {upcoming}")

            if sections:
                return {
                    "context_type": "waypoint",
                    "text": "\n".join(sections),
                    "constraints": "",
                }

        return {"context_type": "default", "text": "", "constraints": ""}

    @staticmethod
    def _extract_section(content: str, section_name: str) -> str:
        """Extract content under a markdown section heading."""
        pattern = rf"##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##\s|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            text = match.group(1).strip()
            # Remove HTML comments
            text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
            return text if text else "None"
        return "None"

    def _build_scoring_prompt(self, context: dict, agents) -> str:
        """Build the batch scoring prompt with context and agent metadata."""
        if context["context_type"] == "objective":
            context_section = (
                f"Current Objective: {context['text']}\n"
                f"Constraints: {context['constraints']}"
            )
        else:
            context_section = f"Project Priorities:\n{context['text']}"

        agent_lines = []
        for agent in agents:
            project_name = agent.project.name if agent.project else "Unknown"
            state = agent.state.value if hasattr(agent.state, "value") else str(agent.state)

            # Get command summary
            command_summary = "None"
            current_command = agent.get_current_command()
            if current_command and current_command.turns:
                recent_turn = current_command.turns[-1]
                if hasattr(recent_turn, "summary") and recent_turn.summary:
                    command_summary = recent_turn.summary
                elif recent_turn.text:
                    command_summary = recent_turn.text[:200]

            # Command duration
            command_duration = "N/A"
            if current_command and current_command.started_at:
                delta = datetime.now(timezone.utc) - current_command.started_at
                minutes = int(delta.total_seconds() // 60)
                if minutes >= 60:
                    command_duration = f"{minutes // 60}h {minutes % 60}m"
                else:
                    command_duration = f"{minutes}m"

            # Waypoint next up
            waypoint_next = "None"
            if agent.project and agent.project.path:
                try:
                    from ..services.waypoint_editor import load_waypoint
                    wp = load_waypoint(agent.project.path)
                    if wp.exists:
                        waypoint_next = self._extract_section(wp.content, "Next Up")
                except Exception as e:
                    logger.warning(f"Waypoint section extraction failed: {e}")

            agent_lines.append(
                f"- Agent ID: {agent.id}\n"
                f"  Project: {project_name}\n"
                f"  State: {state}\n"
                f"  Current Command: {command_summary}\n"
                f"  Command Duration: {command_duration}\n"
                f"  Waypoint Next Up: {waypoint_next}"
            )

        agents_text = "\n".join(agent_lines)

        return build_prompt(
            "priority_scoring",
            context_section=context_section,
            agents_text=agents_text,
        )

    @staticmethod
    def _parse_scoring_response(response_text: str, agent_ids: list[int]) -> list[dict]:
        """Parse structured JSON response from LLM.

        Handles malformed responses gracefully by logging errors
        and returning an empty list.
        """
        try:
            # Try to extract JSON array from response
            text = response_text.strip()
            # Find JSON array in response
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1:
                logger.error(f"No JSON array found in scoring response: {text[:200]}")
                return []

            json_text = text[start:end + 1]
            parsed = json.loads(json_text)

            if not isinstance(parsed, list):
                logger.error(f"Scoring response is not a list: {type(parsed)}")
                return []

            results = []
            valid_ids = set(agent_ids)
            for entry in parsed:
                if not isinstance(entry, dict):
                    continue
                agent_id = entry.get("agent_id")
                score = entry.get("score")
                reason = entry.get("reason", "")

                if agent_id not in valid_ids:
                    continue

                # Clamp score to valid range
                if isinstance(score, (int, float)):
                    score = max(0, min(100, int(score)))
                else:
                    score = 50  # Default if invalid

                results.append({
                    "agent_id": agent_id,
                    "score": score,
                    "reason": str(reason),
                })

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scoring JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing scoring response: {e}")
            return []

    @staticmethod
    def _broadcast_card_refreshes(agents, reason: str) -> None:
        """Broadcast card_refresh for each scored agent."""
        try:
            from .card_state import broadcast_card_refresh

            for agent in agents:
                broadcast_card_refresh(agent, reason)
        except Exception as e:
            logger.debug(f"card_refresh broadcast after scoring failed (non-fatal): {e}")

    def _broadcast_score_update(self, scored: list[dict]) -> None:
        """Broadcast priority_update SSE event."""
        try:
            from .broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            broadcaster.broadcast("priority_update", {"agents": scored})
            logger.debug(f"Broadcast priority_update for {len(scored)} agents")
        except Exception as e:
            logger.debug(f"Failed to broadcast priority update (non-fatal): {e}")
