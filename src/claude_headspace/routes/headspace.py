"""Headspace monitoring API routes."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..database import db
from ..models.headspace_snapshot import HeadspaceSnapshot

headspace_bp = Blueprint("headspace", __name__)


@headspace_bp.route("/api/headspace/current")
def headspace_current():
    """Return the current headspace state."""
    monitor = current_app.extensions.get("headspace_monitor")
    if not monitor or not monitor.enabled:
        return jsonify({"enabled": False, "current": None}), 200

    state = monitor.get_current_state()
    return jsonify({"enabled": True, "current": state}), 200


@headspace_bp.route("/api/headspace/history")
def headspace_history():
    """Return time-series of headspace snapshots."""
    monitor = current_app.extensions.get("headspace_monitor")
    if not monitor or not monitor.enabled:
        return jsonify({"enabled": False, "history": []}), 200

    since = request.args.get("since")
    limit = request.args.get("limit", 100, type=int)

    query = db.session.query(HeadspaceSnapshot)

    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(HeadspaceSnapshot.timestamp >= since_dt)
        except (ValueError, TypeError):
            pass

    snapshots = (
        query.order_by(HeadspaceSnapshot.timestamp.desc())
        .limit(min(limit, 1000))
        .all()
    )

    history = []
    for s in reversed(snapshots):
        history.append({
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "state": s.state,
            "frustration_rolling_10": s.frustration_rolling_10,
            "frustration_rolling_30min": s.frustration_rolling_30min,
            "frustration_rolling_3hr": s.frustration_rolling_3hr,
            "turn_rate_per_hour": s.turn_rate_per_hour,
            "is_flow_state": s.is_flow_state,
            "flow_duration_minutes": s.flow_duration_minutes,
            "alert_count_today": s.alert_count_today,
        })

    return jsonify({"enabled": True, "history": history}), 200


@headspace_bp.route("/api/headspace/suppress", methods=["POST"])
def headspace_suppress():
    """Suppress alerts for 1 hour ('I'm fine' button)."""
    monitor = current_app.extensions.get("headspace_monitor")
    if not monitor or not monitor.enabled:
        return jsonify({"ok": False, "reason": "disabled"}), 200

    hours = request.json.get("hours", 1) if request.is_json else 1
    monitor.suppress_alerts(hours=hours)
    return jsonify({"ok": True, "suppressed_hours": hours}), 200
