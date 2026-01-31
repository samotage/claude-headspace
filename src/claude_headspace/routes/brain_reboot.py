"""Brain reboot API endpoints."""

import logging

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

brain_reboot_bp = Blueprint(
    "brain_reboot", __name__, url_prefix="/api/projects"
)


def _get_project(project_id: int):
    """Look up a project by ID. Returns (project, error_response)."""
    from ..database import db
    from ..models import Project

    project = db.session.get(Project, project_id)
    if project is None:
        return None, (jsonify({"error": "Project not found"}), 404)
    return project, None


def _get_service():
    """Get the brain reboot service. Returns (service, error_response)."""
    service = current_app.extensions.get("brain_reboot_service")
    if service is None:
        return None, (
            jsonify({"error": "Brain reboot service not available"}),
            503,
        )
    return service, None


@brain_reboot_bp.route("/<int:project_id>/brain-reboot", methods=["POST"])
def generate_brain_reboot(project_id: int):
    """
    Generate a brain reboot for a project.

    Combines the project's waypoint and progress summary into
    a formatted context restoration document.
    """
    service, err = _get_service()
    if err:
        return err

    project, err = _get_project(project_id)
    if err:
        return err

    try:
        result = service.generate(project)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Brain reboot generation failed for project {project_id}: {e}")
        return jsonify({"error": f"Generation failed: {str(e)}"}), 500


@brain_reboot_bp.route("/<int:project_id>/brain-reboot", methods=["GET"])
def get_brain_reboot(project_id: int):
    """
    Get the most recently generated brain reboot for a project.

    Returns cached content from the last generate call, or 404 if
    no brain reboot has been generated yet.
    """
    service, err = _get_service()
    if err:
        return err

    project, err = _get_project(project_id)
    if err:
        return err

    result = service.get_last_generated(project_id)
    if result is None:
        return jsonify({
            "status": "not_found",
            "message": "No brain reboot has been generated yet for this project.",
        }), 404

    return jsonify(result), 200


@brain_reboot_bp.route(
    "/<int:project_id>/brain-reboot/export", methods=["POST"]
)
def export_brain_reboot(project_id: int):
    """
    Export a brain reboot to the target project's filesystem.

    Uses the last generated brain reboot content. If no brain reboot
    has been generated, returns 404.
    """
    service, err = _get_service()
    if err:
        return err

    project, err = _get_project(project_id)
    if err:
        return err

    cached = service.get_last_generated(project_id)
    if cached is None:
        return jsonify({
            "error": "No brain reboot has been generated yet. Generate one first.",
        }), 404

    result = service.export(project, cached["content"])

    if result["success"]:
        return jsonify({
            "status": "exported",
            "path": result["path"],
        }), 200
    else:
        return jsonify({
            "error": result["error"],
        }), 500
