"""Health check endpoint."""

import logging

from flask import Blueprint, current_app, jsonify

from ..database import check_database_health

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)


def get_sse_health() -> dict:
    """
    Get SSE broadcaster health status.

    Returns:
        Dictionary with SSE health information
    """
    try:
        from ..services.broadcaster import get_broadcaster

        broadcaster = get_broadcaster()
        return broadcaster.get_health_status()
    except RuntimeError:
        # Broadcaster not initialized
        return {
            "status": "not_initialized",
            "active_connections": 0,
            "max_connections": 0,
            "running": False,
        }
    except Exception as e:
        logger.error(f"Error getting SSE health: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@health_bp.route("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON response with status, version, database, and SSE connectivity
    """
    version = current_app.config.get("APP_VERSION", "unknown")

    # Check database health
    db_connected, db_error = check_database_health()

    # Check SSE health
    sse_health = get_sse_health()

    # Determine overall status
    if db_connected and sse_health.get("status") in ("healthy", "not_initialized"):
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    response = {
        "status": overall_status,
        "version": version,
        "database": "connected" if db_connected else "disconnected",
        "sse": sse_health,
    }

    if db_error:
        response["database_error"] = db_error

    return jsonify(response)
