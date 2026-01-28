"""Health check endpoint."""

from flask import Blueprint, current_app, jsonify

from ..database import check_database_health

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON response with status, version, and database connectivity
    """
    version = current_app.config.get("APP_VERSION", "unknown")

    # Check database health
    db_connected, db_error = check_database_health()

    if db_connected:
        return jsonify({
            "status": "healthy",
            "version": version,
            "database": "connected",
        })
    else:
        response = {
            "status": "degraded",
            "version": version,
            "database": "disconnected",
        }
        if db_error:
            response["database_error"] = db_error
        return jsonify(response)
