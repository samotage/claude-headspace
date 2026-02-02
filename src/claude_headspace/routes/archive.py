"""Archive API routes for listing and retrieving archived brain_reboot artifacts."""

import logging
import re

from flask import Blueprint, current_app, jsonify

from ..database import db
from ..models.project import Project
from ..services.archive_service import VALID_ARTIFACT_TYPES

logger = logging.getLogger(__name__)

archive_bp = Blueprint("archive", __name__, url_prefix="/api/projects")

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")


def _get_project(project_id: int):
    """Look up a project by ID. Returns (project, error_response)."""
    project = db.session.get(Project, project_id)
    if project is None:
        return None, (jsonify({"error": "Project not found"}), 404)
    return project, None


def _get_service():
    """Get the archive service. Returns (service, error_response)."""
    service = current_app.extensions.get("archive_service")
    if service is None:
        return None, (jsonify({"error": "Archive service not available"}), 503)
    return service, None


@archive_bp.route("/<int:project_id>/archives", methods=["GET"])
def list_archives(project_id: int):
    """List all archived versions for a project, grouped by artifact type."""
    service, err = _get_service()
    if err:
        return err

    project, err = _get_project(project_id)
    if err:
        return err

    archives = service.list_archives(project.path)

    return jsonify({
        "project_id": project.id,
        "archives": archives,
    }), 200


@archive_bp.route(
    "/<int:project_id>/archives/<artifact>/<timestamp>", methods=["GET"]
)
def get_archive(project_id: int, artifact: str, timestamp: str):
    """Retrieve a specific archived version's content."""
    service, err = _get_service()
    if err:
        return err

    project, err = _get_project(project_id)
    if err:
        return err

    if artifact not in VALID_ARTIFACT_TYPES:
        return jsonify({
            "error": "invalid_artifact",
            "message": f"Invalid artifact type: {artifact}. Must be one of: {', '.join(VALID_ARTIFACT_TYPES)}",
        }), 400

    if not TIMESTAMP_RE.match(timestamp):
        return jsonify({
            "error": "invalid_timestamp",
            "message": f"Invalid timestamp format: {timestamp}. Expected YYYY-MM-DD_HH-MM-SS",
        }), 400

    result = service.get_archive(project.path, artifact, timestamp)
    if result is None:
        return jsonify({
            "error": "not_found",
            "message": f"Archive not found: {artifact}/{timestamp}",
        }), 404

    return jsonify(result), 200
