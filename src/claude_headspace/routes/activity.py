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


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 string into a timezone-aware datetime, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _get_window() -> tuple[str, datetime, datetime | None]:
    """Parse ?window=, ?since=, and ?until= query parameters.

    ``since`` and ``until`` are ISO 8601 timestamps that define the exact
    period boundaries (computed by the frontend in the user's local timezone).
    ``until`` is exclusive — records with ``bucket_start < until`` are included.

    Returns:
        (window_name, cutoff_start, cutoff_end_or_None) tuple.
    """
    window = request.args.get("window", "day")
    if window not in WINDOW_HOURS:
        window = "day"

    since = _parse_iso(request.args.get("since"))
    until = _parse_iso(request.args.get("until"))

    if since is None:
        hours = WINDOW_HOURS[window]
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

    return window, since, until


def _metric_to_dict(m: ActivityMetric) -> dict:
    """Convert an ActivityMetric to a JSON-serialisable dict."""
    frustration_avg = None
    if m.total_frustration and m.frustration_turn_count and m.frustration_turn_count > 0:
        frustration_avg = round(m.total_frustration / m.frustration_turn_count, 1)
    return {
        "id": m.id,
        "bucket_start": m.bucket_start.isoformat(),
        "turn_count": m.turn_count,
        "avg_turn_time_seconds": m.avg_turn_time_seconds,
        "active_agents": m.active_agents,
        "total_frustration": m.total_frustration,
        "frustration_turn_count": m.frustration_turn_count,
        "frustration_avg": frustration_avg,
        "max_frustration": m.max_frustration,
    }


@activity_bp.route("/activity")
def activity_page():
    """Activity monitoring page."""
    from flask import current_app

    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    headspace = current_app.extensions.get("headspace_monitor")
    headspace_enabled = bool(headspace and headspace.enabled)
    frustration_thresholds = {
        "yellow": getattr(headspace, "_yellow_threshold", 4),
        "red": getattr(headspace, "_red_threshold", 7),
    }
    session_rolling_window_minutes = getattr(
        headspace, "_session_rolling_window_minutes", 180
    )
    return render_template(
        "activity.html",
        status_counts=status_counts,
        frustration_thresholds=frustration_thresholds,
        session_rolling_window_minutes=session_rolling_window_minutes,
        headspace_enabled=headspace_enabled,
    )


@activity_bp.route("/api/metrics/agents/<int:agent_id>")
def agent_metrics(agent_id: int):
    """Get current and historical metrics for a specific agent."""
    from ..models.agent import Agent

    try:
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        window, cutoff, cutoff_end = _get_window()

        query = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.agent_id == agent_id,
                ActivityMetric.bucket_start >= cutoff,
            )
        )
        if cutoff_end:
            query = query.filter(ActivityMetric.bucket_start < cutoff_end)
        history = query.order_by(ActivityMetric.bucket_start.asc()).all()

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

        window, cutoff, cutoff_end = _get_window()

        query = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.project_id == project_id,
                ActivityMetric.bucket_start >= cutoff,
            )
        )
        if cutoff_end:
            query = query.filter(ActivityMetric.bucket_start < cutoff_end)
        history = query.order_by(ActivityMetric.bucket_start.asc()).all()

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
        window, cutoff, cutoff_end = _get_window()

        query = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.is_overall == True,
                ActivityMetric.bucket_start >= cutoff,
            )
        )
        if cutoff_end:
            query = query.filter(ActivityMetric.bucket_start < cutoff_end)
        history = query.order_by(ActivityMetric.bucket_start.asc()).all()

        current = history[-1] if history else None

        # Compute daily totals aggregated across all buckets in the window
        daily_totals = _compute_daily_totals(history, cutoff)

        return jsonify({
            "window": window,
            "current": _metric_to_dict(current) if current else None,
            "history": [_metric_to_dict(m) for m in history],
            "daily_totals": daily_totals,
        }), 200

    except Exception:
        logger.exception("Failed to get overall metrics")
        return jsonify({"error": "Failed to get overall metrics"}), 500


def _compute_daily_totals(metrics: list[ActivityMetric], cutoff: datetime) -> dict:
    """Aggregate metrics across all hourly buckets into daily totals."""
    if not metrics:
        return {
            "total_turns": 0,
            "turn_rate": 0,
            "avg_turn_time_seconds": None,
            "active_agents": 0,
            "frustration_avg": None,
        }

    total_turns = sum(m.turn_count or 0 for m in metrics)

    # Weighted average turn time
    weighted_time_sum = 0.0
    weighted_time_count = 0
    for m in metrics:
        if m.avg_turn_time_seconds is not None and m.turn_count and m.turn_count >= 2:
            weight = m.turn_count - 1
            weighted_time_sum += m.avg_turn_time_seconds * weight
            weighted_time_count += weight
    avg_turn_time = (weighted_time_sum / weighted_time_count) if weighted_time_count > 0 else None

    # Count distinct agents active in the window from agent-level metrics
    distinct_agents = (
        db.session.query(db.func.count(db.func.distinct(ActivityMetric.agent_id)))
        .filter(
            ActivityMetric.agent_id.isnot(None),
            ActivityMetric.bucket_start >= cutoff,
        )
        .scalar()
    ) or 0

    # Turn rate: total turns / hours elapsed
    now = datetime.now(timezone.utc)
    hours_elapsed = max((now - cutoff).total_seconds() / 3600, 1.0)
    turn_rate = round(total_turns / hours_elapsed, 1)

    # Frustration average
    total_frustration = sum(m.total_frustration or 0 for m in metrics)
    total_frust_turns = sum(m.frustration_turn_count or 0 for m in metrics)
    frustration_avg = round(total_frustration / total_frust_turns, 1) if total_frust_turns > 0 else None

    return {
        "total_turns": total_turns,
        "turn_rate": turn_rate,
        "avg_turn_time_seconds": round(avg_turn_time, 1) if avg_turn_time else None,
        "active_agents": distinct_agents,
        "frustration_avg": frustration_avg,
    }
