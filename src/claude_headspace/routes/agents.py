"""Agent lifecycle API endpoints for creating, shutting down, and monitoring agents."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..database import db
from ..models.agent import Agent
from ..services.agent_lifecycle import (
    create_agent,
    get_agent_info,
    get_context_usage,
    shutdown_agent,
)
from ..services.card_state import broadcast_card_refresh

logger = logging.getLogger(__name__)

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("/api/agents", methods=["POST"])
def create_agent_endpoint():
    """Create a new idle agent for a project.

    Request body:
        project_id (int): ID of the project

    Returns:
        201: Agent creation initiated
        400: Missing project_id
        422: Creation failed (project not found, path invalid, etc.)
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")

    if not project_id:
        return jsonify({"error": "project_id is required"}), 400

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return jsonify({"error": "project_id must be an integer"}), 400

    result = create_agent(project_id)

    if not result.success:
        return jsonify({"error": result.message}), 422

    return jsonify({
        "message": result.message,
        "tmux_session_name": result.tmux_session_name,
    }), 201


@agents_bp.route("/api/agents/<int:agent_id>", methods=["DELETE"])
def shutdown_agent_endpoint(agent_id: int):
    """Gracefully shut down an agent.

    Sends /exit to the agent's tmux pane. Hooks will handle state cleanup.

    Returns:
        200: Shutdown initiated
        404: Agent not found
        422: Shutdown failed (no pane, already ended, etc.)
    """
    result = shutdown_agent(agent_id)

    if not result.success:
        status = 404 if "not found" in result.message.lower() else 422
        return jsonify({"error": result.message}), status

    return jsonify({"message": result.message}), 200


@agents_bp.route("/api/agents/<int:agent_id>/info", methods=["GET"])
def agent_info_endpoint(agent_id: int):
    """Get comprehensive debug info for an agent.

    Returns:
        200: Agent info payload
        404: Agent not found
    """
    info = get_agent_info(agent_id)
    if info is None:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify(info), 200


@agents_bp.route("/api/agents/<int:agent_id>/context", methods=["GET"])
def agent_context_endpoint(agent_id: int):
    """Get context window usage for an agent (on-demand).

    Persists the result to the Agent record and broadcasts a card refresh
    so the persistent footer display updates immediately.

    Returns:
        200: Context data (available or unavailable with reason)
        404: Agent not found
    """
    result = get_context_usage(agent_id)

    if result.reason == "agent_not_found":
        return jsonify({"available": False, "reason": result.reason}), 404

    if not result.available:
        return jsonify({"available": False, "reason": result.reason}), 200

    # Persist to Agent record so the card footer shows the latest data
    agent = db.session.get(Agent, agent_id)
    if agent:
        agent.context_percent_used = result.percent_used
        agent.context_remaining_tokens = result.remaining_tokens
        agent.context_updated_at = datetime.now(timezone.utc)
        db.session.commit()
        broadcast_card_refresh(agent, "context_fetched")

    return jsonify({
        "available": True,
        "percent_used": result.percent_used,
        "remaining_tokens": result.remaining_tokens,
        "raw": result.raw,
    }), 200


@agents_bp.route("/api/agents/<int:agent_id>/reconcile", methods=["POST"])
def reconcile_agent_endpoint(agent_id: int):
    """Manually trigger transcript reconciliation for an agent.

    Forces the reconciler to re-scan the agent's JSONL transcript and create
    Turn records for any entries not already captured by hooks.

    Returns:
        200: Reconciliation result with created count
        404: Agent not found
    """
    from ..services.transcript_reconciler import (
        broadcast_reconciliation,
        get_reconcile_lock,
        reconcile_agent_session,
    )

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    # Per-agent lock prevents concurrent reconciliation (endpoint + watchdog)
    lock = get_reconcile_lock(agent_id)
    if not lock.acquire(blocking=False):
        return jsonify({
            "status": "busy",
            "created": 0,
            "message": "Reconciliation already in progress",
        }), 409

    try:
        result = reconcile_agent_session(agent)
        try:
            broadcast_reconciliation(agent, result)
        except Exception as e:
            logger.warning(f"Reconcile broadcast failed for agent {agent_id}: {e}")
        db.session.commit()
    finally:
        lock.release()

    return jsonify({
        "status": "ok",
        "created": len(result["created"]),
    })
