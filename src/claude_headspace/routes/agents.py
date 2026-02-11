"""Agent lifecycle API endpoints for creating, shutting down, and monitoring agents."""

import logging

from flask import Blueprint, jsonify, request

from ..services.agent_lifecycle import (
    create_agent,
    get_context_usage,
    shutdown_agent,
)

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


@agents_bp.route("/api/agents/<int:agent_id>/context", methods=["GET"])
def agent_context_endpoint(agent_id: int):
    """Get context window usage for an agent (on-demand).

    Returns:
        200: Context data (available or unavailable with reason)
        404: Agent not found
    """
    result = get_context_usage(agent_id)

    if result.reason == "agent_not_found":
        return jsonify({"available": False, "reason": result.reason}), 404

    if not result.available:
        return jsonify({"available": False, "reason": result.reason}), 200

    return jsonify({
        "available": True,
        "percent_used": result.percent_used,
        "remaining_tokens": result.remaining_tokens,
        "raw": result.raw,
    }), 200
