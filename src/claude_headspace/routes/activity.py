"""Activity monitoring page and API endpoints."""

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request

from ..database import db
from ..models.activity_metric import ActivityMetric

logger = logging.getLogger(__name__)

activity_bp = Blueprint("activity", __name__)

WINDOW_HOURS = {
    "day": 24,
    "week": 24 * 7,
    "month": 24 * 30,
}


def _get_window() -> tuple[str, int]:
    """Parse and validate the ?window= query parameter.

    Returns:
        (window_name, hours) tuple.
    """
    window = request.args.get("window", "day")
    if window not in WINDOW_HOURS:
        window = "day"
    return window, WINDOW_HOURS[window]


def _metric_to_dict(m: ActivityMetric) -> dict:
    """Convert an ActivityMetric to a JSON-serialisable dict."""
    return {
        "id": m.id,
        "bucket_start": m.bucket_start.isoformat(),
        "turn_count": m.turn_count,
        "avg_turn_time_seconds": m.avg_turn_time_seconds,
        "active_agents": m.active_agents,
        "total_frustration": m.total_frustration,
    }


@activity_bp.route("/activity")
def activity_page():
    """Activity monitoring page."""
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("activity.html", status_counts=status_counts)


@activity_bp.route("/api/metrics/agents/<int:agent_id>")
def agent_metrics(agent_id: int):
    """Get current and historical metrics for a specific agent."""
    from ..models.agent import Agent

    try:
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        window, hours = _get_window()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        history = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.agent_id == agent_id,
                ActivityMetric.bucket_start >= cutoff,
            )
            .order_by(ActivityMetric.bucket_start.asc())
            .all()
        )

        current = history[-1] if history else None

        return jsonify({
            "agent_id": agent_id,
            "window": window,
            "current": _metric_to_dict(current) if current else None,
            "history": [_metric_to_dict(m) for m in history],
        }), 200

    except Exception:
        logger.exception("Failed to get agent metrics for %s", agent_id)
        return jsonify({"error": "Failed to get agent metrics"}), 500


@activity_bp.route("/api/metrics/projects/<int:project_id>")
def project_metrics(project_id: int):
    """Get current and historical aggregated metrics for a project."""
    from ..models.project import Project

    try:
        project = db.session.get(Project, project_id)
        if not project:
            return jsonify({"error": "Project not found"}), 404

        window, hours = _get_window()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        history = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.project_id == project_id,
                ActivityMetric.bucket_start >= cutoff,
            )
            .order_by(ActivityMetric.bucket_start.asc())
            .all()
        )

        current = history[-1] if history else None

        return jsonify({
            "project_id": project_id,
            "window": window,
            "current": _metric_to_dict(current) if current else None,
            "history": [_metric_to_dict(m) for m in history],
        }), 200

    except Exception:
        logger.exception("Failed to get project metrics for %s", project_id)
        return jsonify({"error": "Failed to get project metrics"}), 500


@activity_bp.route("/api/metrics/overall")
def overall_metrics():
    """Get current and historical system-wide aggregated metrics."""
    try:
        window, hours = _get_window()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        history = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.is_overall == True,
                ActivityMetric.bucket_start >= cutoff,
            )
            .order_by(ActivityMetric.bucket_start.asc())
            .all()
        )

        current = history[-1] if history else None

        return jsonify({
            "window": window,
            "current": _metric_to_dict(current) if current else None,
            "history": [_metric_to_dict(m) for m in history],
        }), 200

    except Exception:
        logger.exception("Failed to get overall metrics")
        return jsonify({"error": "Failed to get overall metrics"}), 500
