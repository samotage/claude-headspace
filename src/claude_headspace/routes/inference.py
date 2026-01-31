"""Inference API endpoints for status and usage."""

import logging

from flask import Blueprint, current_app, jsonify

logger = logging.getLogger(__name__)

inference_bp = Blueprint("inference", __name__)


def _get_inference_service():
    """Get the inference service from app extensions."""
    return current_app.extensions.get("inference_service")


@inference_bp.route("/api/inference/status")
def inference_status():
    """Return inference service status, connectivity, and configuration."""
    service = _get_inference_service()
    if not service:
        return jsonify({"error": "Inference service not initialized"}), 503

    status = service.get_status()
    return jsonify(status)


@inference_bp.route("/api/inference/usage")
def inference_usage():
    """Return inference usage statistics and cost breakdown."""
    service = _get_inference_service()
    if not service:
        return jsonify({"error": "Inference service not initialized"}), 503

    from ..database import db
    usage = service.get_usage(db_session=db.session)
    return jsonify(usage)
