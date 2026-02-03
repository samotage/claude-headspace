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


def _get_window() -> tuple[str, datetime]:
    """Parse ?window= and optional ?since= query parameters.

    If ``since`` is provided (ISO 8601 timestamp), it is used as the cutoff
    directly — this allows the frontend to send calendar-day boundaries in the
    user's local timezone.  Otherwise falls back to a rolling window.

    Returns:
        (window_name, cutoff_datetime) tuple.
    """
    window = request.args.get("window", "day")
    if window not in WINDOW_HOURS:
        window = "day"

    since = request.args.get("since")
    if since:
        try:
            cutoff = datetime.fromisoformat(since)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            return window, cutoff
        except (ValueError, TypeError):
            pass

    hours = WINDOW_HOURS[window]
    return window, datetime.now(timezone.utc) - timedelta(hours=hours)


def _metric_to_dict(m: ActivityMetric) -> dict:
    """Convert an ActivityMetric to a JSON-serialisable dict."""
    return {
        "id": m.id,
        "bucket_start": m.bucket_start.isoformat(),
        "turn_count": m.turn_count,
        "avg_turn_time_seconds": m.avg_turn_time_seconds,
        "active_agents": m.active_agents,
        "total_frustration": m.total_frustration,
        "frustration_turn_count": m.frustration_turn_count,
    }


@activity_bp.route("/activity")
def activity_page():
    """Activity monitoring page."""
    from flask import current_app

    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    headspace = current_app.extensions.get("headspace_monitor")
    frustration_thresholds = {
        "yellow": getattr(headspace, "_yellow_threshold", 4),
        "red": getattr(headspace, "_red_threshold", 7),
    }
    return render_template(
        "activity.html",
        status_counts=status_counts,
        frustration_thresholds=frustration_thresholds,
    )


@activity_bp.route("/api/metrics/agents/<int:agent_id>")
def agent_metrics(agent_id: int):
    """Get current and historical metrics for a specific agent."""
    from ..models.agent import Agent

    try:
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        window, cutoff = _get_window()

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

        window, cutoff = _get_window()

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
        window, cutoff = _get_window()

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
