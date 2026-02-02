"""Respond API endpoint for sending text input to Claude Code sessions."""

import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..database import db
from ..models.agent import Agent
from ..models.task import TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from ..services.card_state import broadcast_card_refresh
from ..services.commander_service import CommanderErrorType, send_text

logger = logging.getLogger(__name__)

respond_bp = Blueprint("respond", __name__)


def _get_commander_availability():
    """Get the commander availability service from app extensions."""
    return current_app.extensions.get("commander_availability")


@respond_bp.route("/api/respond/<int:agent_id>", methods=["POST"])
def respond_to_agent(agent_id: int):
    """Send a text response to a Claude Code session via commander socket.

    Validates that the agent exists, is in AWAITING_INPUT state, and has a
    reachable commander socket. On success, creates a Turn record and triggers
    the AWAITING_INPUT -> PROCESSING state transition.

    Args:
        agent_id: Database ID of the agent

    Request body:
        {"text": "response text"}

    Returns:
        200: Response sent successfully
        400: Missing text or no session ID
        404: Agent not found
        409: Agent not in AWAITING_INPUT state
        502: Commander send failed
        503: Commander socket unavailable
    """
    start_time = time.time()

    # Parse request body
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({
            "status": "error",
            "error_type": "missing_text",
            "message": "Response text is required.",
        }), 400

    # Lookup agent
    agent = db.session.get(Agent, agent_id)
    if agent is None:
        return jsonify({
            "status": "error",
            "error_type": "agent_not_found",
            "message": f"Agent with ID {agent_id} not found.",
        }), 404

    # Check agent has a session ID (needed for socket path)
    if not agent.claude_session_id:
        return jsonify({
            "status": "error",
            "error_type": "no_session_id",
            "message": "Agent has no session ID — cannot derive commander socket path.",
        }), 400

    # Check agent is in AWAITING_INPUT state
    current_task = agent.get_current_task()
    if current_task is None or current_task.state != TaskState.AWAITING_INPUT:
        actual_state = current_task.state.value if current_task else "no_task"
        return jsonify({
            "status": "error",
            "error_type": "wrong_state",
            "message": f"Agent is not awaiting input (current state: {actual_state}).",
        }), 409

    # Get commander config
    config = current_app.config.get("APP_CONFIG", {})
    commander_config = config.get("commander", {})
    socket_prefix = commander_config.get("socket_path_prefix", "/tmp/claudec-")
    socket_timeout = commander_config.get("socket_timeout", 2)

    # Send text via commander socket
    result = send_text(
        session_id=agent.claude_session_id,
        text=text,
        prefix=socket_prefix,
        timeout=socket_timeout,
    )

    if not result.success:
        # Map error types to HTTP status codes
        if result.error_type == CommanderErrorType.SOCKET_NOT_FOUND:
            status_code = 503
        elif result.error_type == CommanderErrorType.CONNECTION_REFUSED:
            status_code = 503
        elif result.error_type == CommanderErrorType.PROCESS_DEAD:
            status_code = 503
        elif result.error_type == CommanderErrorType.TIMEOUT:
            status_code = 502
        else:
            status_code = 502

        logger.warning(
            f"respond_failed: agent_id={agent_id}, error={result.error_type}, "
            f"message={result.error_message}, latency_ms={result.latency_ms}"
        )

        return jsonify({
            "status": "error",
            "error_type": result.error_type.value if result.error_type else "unknown",
            "message": result.error_message,
            "latency_ms": result.latency_ms,
        }), status_code

    # Success: create Turn record and transition state
    try:
        # Create USER ANSWER turn
        turn = Turn(
            task_id=current_task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text=text,
        )
        db.session.add(turn)

        # Transition state: AWAITING_INPUT -> PROCESSING
        current_task.state = TaskState.PROCESSING
        agent.last_seen_at = datetime.now(timezone.utc)

        db.session.commit()

        # Broadcast state change
        broadcast_card_refresh(agent, "respond")
        _broadcast_state_change(agent, text)

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"respond_success: agent_id={agent_id}, text_length={len(text)}, "
            f"latency_ms={latency_ms}"
        )

        return jsonify({
            "status": "ok",
            "agent_id": agent_id,
            "new_state": TaskState.PROCESSING.value,
            "latency_ms": latency_ms,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error recording response for agent {agent_id}: {e}")
        return jsonify({
            "status": "error",
            "error_type": "internal_error",
            "message": "Response was sent but recording failed. State will self-correct.",
        }), 500


@respond_bp.route("/api/respond/<int:agent_id>/availability", methods=["GET"])
def check_availability(agent_id: int):
    """Check commander socket availability for an agent.

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Availability status
        404: Agent not found
    """
    agent = db.session.get(Agent, agent_id)
    if agent is None:
        return jsonify({
            "status": "error",
            "error_type": "agent_not_found",
            "message": f"Agent with ID {agent_id} not found.",
        }), 404

    availability = _get_commander_availability()
    if availability and agent.claude_session_id:
        available = availability.check_agent(agent_id, agent.claude_session_id)
    else:
        available = False

    return jsonify({
        "status": "ok",
        "agent_id": agent_id,
        "commander_available": available,
    }), 200


def _broadcast_state_change(agent: Agent, response_text: str) -> None:
    """Broadcast state change and turn creation after response."""
    try:
        from ..services.broadcaster import get_broadcaster

        broadcaster = get_broadcaster()
        broadcaster.broadcast("state_changed", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "event_type": "respond",
            "new_state": "PROCESSING",
            "message": f"User responded via dashboard",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        broadcaster.broadcast("turn_created", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": response_text,
            "actor": "user",
            "intent": "answer",
            "task_id": agent.get_current_task().id if agent.get_current_task() else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
