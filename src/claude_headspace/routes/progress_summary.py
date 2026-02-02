"""Progress summary API routes."""

from flask import Blueprint, current_app, jsonify, request

progress_summary_bp = Blueprint(
    "progress_summary", __name__, url_prefix="/api/projects"
)


def _get_service():
    """Get the progress summary service from app extensions."""
    return current_app.extensions.get("progress_summary_service")


@progress_summary_bp.route("/<int:project_id>/progress-summary", methods=["POST"])
def generate_summary(project_id):
    """Trigger progress summary generation for a project.

    Optional JSON body:
        scope: Override scope ('since_last', 'last_n', 'time_based')

    Returns:
        200: Summary generated successfully
        404: Project not found
        409: Generation already in progress
        422: Project is not a git repository
        503: Inference service unavailable
    """
    service = _get_service()
    if not service:
        return jsonify({"error": "Progress summary service not available"}), 503

    inference = current_app.extensions.get("inference_service")
    if not inference or not inference.is_available:
        return jsonify({"error": "Inference service not available"}), 503

    # Get project from database
    from ..database import db
    from ..models.project import Project

    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Check for concurrent generation
    if service.is_generating(project_id):
        return jsonify({"error": "Generation already in progress for this project"}), 409

    # Get optional scope override
    scope = None
    body = request.get_json(silent=True)
    if body:
        scope = body.get("scope")

    result = service.generate(project, scope=scope)

    if result.get("status") == "in_progress":
        return jsonify({"error": result["error"]}), 409

    if result.get("status") == "error":
        error_msg = result.get("error", "")
        if "Not a git repository" in error_msg:
            return jsonify({"error": error_msg}), 422
        return jsonify({"error": error_msg}), 500

    return jsonify(result)


@progress_summary_bp.route("/<int:project_id>/progress-summary", methods=["GET"])
def get_summary(project_id):
    """Get the current progress summary for a project.

    Returns:
        200: Summary content and metadata
        404: Project not found or no summary exists
    """
    service = _get_service()
    if not service:
        return jsonify({"error": "Progress summary service not available"}), 503

    from ..database import db
    from ..models.project import Project

    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = service.get_current_summary(project)

    if result.get("status") == "not_found":
        return jsonify({"error": "No progress summary found"}), 404

    if result.get("status") == "error":
        return jsonify({"error": result["error"]}), 500

    return jsonify(result)
