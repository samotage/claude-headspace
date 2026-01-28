"""Health check endpoint."""

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON response with status and version
    """
    version = current_app.config.get("APP_VERSION", "unknown")
    return jsonify({
        "status": "healthy",
        "version": version,
    })
