"""Focus API endpoint for iTerm2 pane focusing and agent dismissal."""

import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from ..database import db
from ..models.agent import Agent
from ..services.iterm_focus import FocusErrorType, FocusResult, focus_iterm_pane

logger = logging.getLogger(__name__)

focus_bp = Blueprint("focus", __name__)


def _get_fallback_path(agent: Agent) -> str | None:
    """
    Get fallback path for an agent (project path or working directory).

    Args:
        agent: The Agent model instance

    Returns:
        Path string or None if not available
    """
    if agent.project and agent.project.path:
        return agent.project.path
    return None


def _log_focus_event(
    agent_id: int,
    pane_id: str | None,
    success: bool,
    error_type: str | None,
    latency_ms: int,
) -> None:
    """
    Log a focus attempt event.

    Args:
        agent_id: The agent ID
        pane_id: The iTerm pane ID (if available)
        success: Whether focus succeeded
        error_type: Error type if failed
        latency_ms: Operation latency in milliseconds
    """
    outcome = "success" if success else "failure"
    logger.info(
        f"focus_attempted: agent_id={agent_id}, pane_id={pane_id}, "
        f"outcome={outcome}, error_type={error_type}, latency_ms={latency_ms}"
    )


@focus_bp.route("/api/focus/<int:agent_id>", methods=["POST"])
def focus_agent(agent_id: int):
    """
    Trigger iTerm2 focus for a specific agent's terminal session.

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Focus succeeded
        404: Agent not found
        500: Focus failed (with error details)
    """
    start_time = time.time()

    # Lookup agent
    agent = db.session.get(Agent, agent_id)

    if agent is None:
        _log_focus_event(
            agent_id=agent_id,
            pane_id=None,
            success=False,
            error_type="agent_not_found",
            latency_ms=int((time.time() - start_time) * 1000),
        )
        return jsonify({
            "status": "error",
            "error_type": "agent_not_found",
            "message": f"Agent with ID {agent_id} not found.",
        }), 404

    fallback_path = _get_fallback_path(agent)
    pane_id = agent.iterm_pane_id

    # Check if agent has a pane ID
    if not pane_id:
        latency_ms = int((time.time() - start_time) * 1000)
        _log_focus_event(
            agent_id=agent_id,
            pane_id=None,
            success=False,
            error_type="pane_not_found",
            latency_ms=latency_ms,
        )
        return jsonify({
            "status": "error",
            "error_type": "pane_not_found",
            "message": "This agent does not have an iTerm pane ID. "
            "It may have been created before the launcher script was used.",
            "fallback_path": fallback_path,
        }), 500

    # Attempt to focus the pane
    result: FocusResult = focus_iterm_pane(pane_id)

    # Log the event
    _log_focus_event(
        agent_id=agent_id,
        pane_id=pane_id,
        success=result.success,
        error_type=result.error_type.value if result.error_type else None,
        latency_ms=result.latency_ms,
    )

    if result.success:
        return jsonify({
            "status": "ok",
            "agent_id": agent_id,
            "pane_id": pane_id,
        }), 200
    else:
        # Map error types to appropriate HTTP status codes
        status_code = 500
        if result.error_type == FocusErrorType.PANE_NOT_FOUND:
            status_code = 500  # Still a server-side issue, not client error

        return jsonify({
            "status": "error",
            "error_type": result.error_type.value if result.error_type else "unknown",
            "message": result.error_message,
            "fallback_path": fallback_path,
        }), status_code


@focus_bp.route("/api/agents/<int:agent_id>/dismiss", methods=["POST"])
def dismiss_agent(agent_id: int):
    """
    Dismiss an agent by marking it as ended.

    Used from the dashboard when an agent's terminal window is no longer
    reachable (closed externally, no pane ID, etc.).

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Agent dismissed
        404: Agent not found
        409: Agent already ended
    """
    agent = db.session.get(Agent, agent_id)

    if agent is None:
        return jsonify({
            "status": "error",
            "message": f"Agent {agent_id} not found",
        }), 404

    if agent.ended_at is not None:
        return jsonify({
            "status": "error",
            "message": "Agent already ended",
        }), 409

    now = datetime.now(timezone.utc)
    agent.ended_at = now
    agent.last_seen_at = now
    db.session.commit()

    logger.info(f"Agent {agent_id} dismissed from dashboard")

    # Broadcast so other dashboard clients also remove the card
    try:
        from ..services.broadcaster import get_broadcaster
        get_broadcaster().broadcast("session_ended", {
            "agent_id": agent_id,
            "reason": "dismissed",
            "timestamp": now.isoformat(),
        })
    except Exception:
        pass

    return jsonify({
        "status": "ok",
        "agent_id": agent_id,
    }), 200
