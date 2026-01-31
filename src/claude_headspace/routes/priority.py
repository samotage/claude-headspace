"""Priority scoring API routes."""

from flask import Blueprint, current_app, jsonify

priority_bp = Blueprint("priority", __name__, url_prefix="/api/priority")


def _get_service():
    """Get the priority scoring service from app extensions."""
    return current_app.extensions.get("priority_scoring_service")


@priority_bp.route("/score", methods=["POST"])
def trigger_scoring():
    """Trigger batch priority scoring of all active agents.

    Returns scores, reasons, and context type used.
    Returns 503 if inference service unavailable.
    """
    service = _get_service()
    if not service:
        return jsonify({"error": "Priority scoring service not available"}), 503

    inference = current_app.extensions.get("inference_service")
    if not inference or not inference.is_available:
        return jsonify({"error": "Inference service not available"}), 503

    from ..database import db

    result = service.score_all_agents(db.session)

    if "error" in result:
        return jsonify({"error": result["error"]}), 500

    return jsonify(result)


@priority_bp.route("/rankings", methods=["GET"])
def get_rankings():
    """Get current priority rankings from database.

    Returns all agents ordered by priority score descending.
    No new inference call is made.
    """
    service = _get_service()
    if not service:
        return jsonify({"error": "Priority scoring service not available"}), 503

    from ..database import db
    from ..models.agent import Agent

    agents = (
        db.session.query(Agent)
        .filter(Agent.ended_at.is_(None))
        .order_by(Agent.priority_score.desc().nullslast())
        .all()
    )

    rankings = []
    for agent in agents:
        rankings.append({
            "agent_id": agent.id,
            "project_name": agent.project.name if agent.project else "Unknown",
            "state": agent.state.value if hasattr(agent.state, "value") else str(agent.state),
            "score": agent.priority_score,
            "reason": agent.priority_reason,
            "scored_at": agent.priority_updated_at.isoformat() if agent.priority_updated_at else None,
        })

    return jsonify({"agents": rankings})
