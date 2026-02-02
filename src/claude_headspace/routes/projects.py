"""Project management API and page endpoints."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request

from ..database import db
from ..models.project import Project

logger = logging.getLogger(__name__)

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/projects")
def projects_page():
    """Projects management page."""
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("projects.html", status_counts=status_counts)


def _broadcast_project_event(event_type: str, data: dict) -> None:
    """Broadcast project-related SSE event."""
    try:
        from ..services.broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        broadcaster.broadcast(event_type, data)
    except Exception as e:
        logger.debug(f"Broadcast {event_type} failed (non-fatal): {e}")


@projects_bp.route("/api/projects", methods=["GET"])
def list_projects():
    """List all registered projects with agent counts."""
    try:
        projects = db.session.query(Project).order_by(Project.created_at.desc()).all()

        result = []
        for p in projects:
            agent_count = len([a for a in p.agents if a.ended_at is None])
            result.append({
                "id": p.id,
                "name": p.name,
                "path": p.path,
                "github_repo": p.github_repo,
                "description": p.description,
                "current_branch": p.current_branch,
                "inference_paused": p.inference_paused,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "agent_count": agent_count,
            })

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to list projects")
        return jsonify({"error": "Failed to list projects"}), 500


@projects_bp.route("/api/projects", methods=["POST"])
def create_project():
    """Create a new project.

    Accepts JSON body with:
        - name (required): Project display name
        - path (required): Absolute filesystem path
        - github_repo (optional): GitHub repository URL
        - description (optional): Project description

    Returns:
        201: Project created
        400: Missing required fields
        409: Duplicate path
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = (data.get("name") or "").strip()
    path = (data.get("path") or "").strip()

    if not name or not path:
        return jsonify({"error": "Both 'name' and 'path' are required"}), 400

    try:
        existing = Project.query.filter_by(path=path).first()
        if existing:
            return jsonify({
                "error": f"A project with path '{path}' already exists",
                "existing_id": existing.id,
            }), 409

        project = Project(
            name=name,
            path=path,
            github_repo=(data.get("github_repo") or "").strip() or None,
            description=(data.get("description") or "").strip() or None,
        )
        db.session.add(project)
        db.session.commit()

        _broadcast_project_event("project_changed", {
            "action": "created",
            "project_id": project.id,
        })

        return jsonify({
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "github_repo": project.github_repo,
            "description": project.description,
            "inference_paused": project.inference_paused,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }), 201

    except Exception:
        logger.exception("Failed to create project")
        db.session.rollback()
        return jsonify({"error": "Failed to create project"}), 500


@projects_bp.route("/api/projects/<int:project_id>", methods=["GET"])
def get_project(project_id: int):
    """Get project detail with agents list."""
    try:
        project = db.session.get(Project, project_id)

        if not project:
            return jsonify({"error": "Project not found"}), 404

        agents_data = []
        for a in project.agents:
            agents_data.append({
                "id": a.id,
                "session_uuid": str(a.session_uuid) if a.session_uuid else None,
                "state": a.state.value if hasattr(a.state, "value") else str(a.state),
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "ended_at": a.ended_at.isoformat() if a.ended_at else None,
            })

        return jsonify({
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "github_repo": project.github_repo,
            "description": project.description,
            "current_branch": project.current_branch,
            "inference_paused": project.inference_paused,
            "inference_paused_at": project.inference_paused_at.isoformat() if project.inference_paused_at else None,
            "inference_paused_reason": project.inference_paused_reason,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "agents": agents_data,
        }), 200

    except Exception:
        logger.exception("Failed to get project %s", project_id)
        return jsonify({"error": "Failed to get project"}), 500


@projects_bp.route("/api/projects/<int:project_id>", methods=["PUT"])
def update_project(project_id: int):
    """Update project metadata.

    Accepts JSON body with any of:
        - name: Project display name
        - path: Filesystem path (checked for conflicts)
        - github_repo: GitHub repository URL
        - description: Project description

    Returns:
        200: Updated
        404: Not found
        409: Path conflict
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        project = db.session.get(Project, project_id)

        if not project:
            return jsonify({"error": "Project not found"}), 404

        # Check path conflict if path is being updated
        new_path = data.get("path")
        if new_path is not None:
            new_path = new_path.strip()
            if new_path and new_path != project.path:
                conflict = Project.query.filter_by(path=new_path).first()
                if conflict:
                    return jsonify({
                        "error": f"A project with path '{new_path}' already exists",
                        "existing_id": conflict.id,
                    }), 409
                project.path = new_path

        if "name" in data:
            name = (data["name"] or "").strip()
            if name:
                project.name = name

        if "github_repo" in data:
            project.github_repo = (data["github_repo"] or "").strip() or None

        if "description" in data:
            project.description = (data["description"] or "").strip() or None

        db.session.commit()

        _broadcast_project_event("project_changed", {
            "action": "updated",
            "project_id": project.id,
        })

        return jsonify({
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "github_repo": project.github_repo,
            "description": project.description,
            "inference_paused": project.inference_paused,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }), 200

    except Exception:
        logger.exception("Failed to update project %s", project_id)
        db.session.rollback()
        return jsonify({"error": "Failed to update project"}), 500


@projects_bp.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id: int):
    """Delete project and cascade delete all agents.

    Returns:
        200: Deleted
        404: Not found
    """
    try:
        project = db.session.get(Project, project_id)

        if not project:
            return jsonify({"error": "Project not found"}), 404

        project_name = project.name
        db.session.delete(project)
        db.session.commit()

        _broadcast_project_event("project_changed", {
            "action": "deleted",
            "project_id": project_id,
        })

        return jsonify({
            "deleted": True,
            "id": project_id,
            "name": project_name,
        }), 200

    except Exception:
        logger.exception("Failed to delete project %s", project_id)
        db.session.rollback()
        return jsonify({"error": "Failed to delete project"}), 500


# --- Settings endpoints ---


@projects_bp.route("/api/projects/<int:project_id>/settings", methods=["GET"])
def get_project_settings(project_id: int):
    """Get project inference settings."""
    try:
        project = db.session.get(Project, project_id)

        if not project:
            return jsonify({"error": "Project not found"}), 404

        return jsonify({
            "inference_paused": project.inference_paused,
            "inference_paused_at": project.inference_paused_at.isoformat() if project.inference_paused_at else None,
            "inference_paused_reason": project.inference_paused_reason,
        }), 200

    except Exception:
        logger.exception("Failed to get settings for project %s", project_id)
        return jsonify({"error": "Failed to get project settings"}), 500


@projects_bp.route("/api/projects/<int:project_id>/settings", methods=["PUT"])
def update_project_settings(project_id: int):
    """Update project inference settings.

    Accepts JSON body with:
        - inference_paused (required): Boolean
        - inference_paused_reason (optional): Reason string (only used when pausing)

    Returns:
        200: Updated
        400: Missing required fields
        404: Not found
    """
    data = request.get_json(silent=True)

    if not data or "inference_paused" not in data:
        return jsonify({"error": "'inference_paused' field is required"}), 400

    try:
        project = db.session.get(Project, project_id)

        if not project:
            return jsonify({"error": "Project not found"}), 404

        paused = bool(data["inference_paused"])

        if paused:
            project.inference_paused = True
            project.inference_paused_at = datetime.now(timezone.utc)
            project.inference_paused_reason = (data.get("inference_paused_reason") or "").strip() or None
        else:
            project.inference_paused = False
            project.inference_paused_at = None
            project.inference_paused_reason = None

        db.session.commit()

        _broadcast_project_event("project_settings_changed", {
            "project_id": project.id,
            "inference_paused": project.inference_paused,
            "inference_paused_at": project.inference_paused_at.isoformat() if project.inference_paused_at else None,
        })

        return jsonify({
            "inference_paused": project.inference_paused,
            "inference_paused_at": project.inference_paused_at.isoformat() if project.inference_paused_at else None,
            "inference_paused_reason": project.inference_paused_reason,
        }), 200

    except Exception:
        logger.exception("Failed to update settings for project %s", project_id)
        db.session.rollback()
        return jsonify({"error": "Failed to update project settings"}), 500
