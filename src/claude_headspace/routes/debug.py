"""Debug and monitoring API endpoints."""

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__)


@debug_bp.route("/api/advisory-locks", methods=["GET"])
def get_advisory_locks():
    """Query currently held PostgreSQL advisory locks.

    Returns all advisory locks visible in pg_locks joined with
    pg_stat_activity for session context.

    Returns:
        200: JSON with locks list and total count
    """
    from ..services.advisory_lock import get_held_advisory_locks

    try:
        locks = get_held_advisory_locks()
        return jsonify({
            "status": "ok",
            "total": len(locks),
            "locks": locks,
        }), 200
    except Exception as e:
        logger.warning(f"Failed to query advisory locks: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to query advisory locks",
        }), 500
