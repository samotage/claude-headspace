"""Waypoint API routes for editing project waypoints."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..database import db
from ..models.project import Project
from ..services.waypoint_editor import (
    load_waypoint,
    save_waypoint,
    validate_project_path,
)

logger = logging.getLogger(__name__)

waypoint_bp = Blueprint("waypoint", __name__)


@waypoint_bp.route("/api/projects/<int:project_id>/waypoint", methods=["GET"])
def get_waypoint(project_id: int):
    """
    Get waypoint content for a project.

    Returns:
        200: Waypoint content (exists=true) or template (exists=false)
        404: Project not found
        500: File system error
    """
    # Get project from database
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({
            "error": "not_found",
            "message": f"Project {project_id} not found",
        }), 404

    # Validate project path
    valid, error = validate_project_path(project.path)
    if not valid:
        return jsonify({
            "error": "path_error",
            "message": error,
            "path": project.path,
        }), 500

    try:
        result = load_waypoint(project.path)

        response = {
            "project_id": project.id,
            "project_name": project.name,
            "exists": result.exists,
            "content": result.content,
            "path": result.path,
        }

        if result.template:
            response["template"] = True
        if result.last_modified:
            response["last_modified"] = result.last_modified.isoformat()

        return jsonify(response), 200

    except PermissionError:
        return jsonify({
            "error": "permission_denied",
            "message": f"Permission denied reading waypoint. Check permissions for: {project.path}",
            "path": project.path,
        }), 403
    except Exception as e:
        logger.exception(f"Error loading waypoint for project {project_id}")
        return jsonify({
            "error": "read_error",
            "message": f"Failed to load waypoint: {type(e).__name__}",
        }), 500


@waypoint_bp.route("/api/projects/<int:project_id>/waypoint", methods=["POST"])
def post_waypoint(project_id: int):
    """
    Save waypoint content for a project.

    Expected payload:
    {
        "content": "# Waypoint...",
        "expected_mtime": "2026-01-29T10:30:00Z" (optional)
    }

    Returns:
        200: Waypoint saved successfully
        400: Invalid request
        403: Permission denied
        404: Project not found
        409: Conflict (file modified externally)
        500: Save failed
    """
    # Get project from database
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({
            "error": "not_found",
            "message": f"Project {project_id} not found",
        }), 404

    # Validate project path
    valid, error = validate_project_path(project.path)
    if not valid:
        return jsonify({
            "error": "path_error",
            "message": error,
            "path": project.path,
        }), 500

    # Parse request
    if not request.is_json:
        return jsonify({
            "error": "invalid_request",
            "message": "Content-Type must be application/json",
        }), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "error": "invalid_request",
            "message": "Invalid JSON payload",
        }), 400

    content = data.get("content")
    if content is None:
        return jsonify({
            "error": "invalid_request",
            "message": "Missing required field: content",
        }), 400

    # Parse expected_mtime if provided
    expected_mtime = None
    if "expected_mtime" in data and data["expected_mtime"]:
        try:
            mtime_str = data["expected_mtime"]
            # Handle both ISO format with and without timezone
            if mtime_str.endswith("Z"):
                mtime_str = mtime_str[:-1] + "+00:00"
            expected_mtime = datetime.fromisoformat(mtime_str)
            if expected_mtime.tzinfo is None:
                expected_mtime = expected_mtime.replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify({
                "error": "invalid_request",
                "message": "Invalid expected_mtime format. Use ISO 8601.",
            }), 400

    try:
        archive_service = current_app.extensions.get("archive_service")
        result = save_waypoint(project.path, content, expected_mtime, archive_service=archive_service)

        if not result.success:
            if result.error == "conflict":
                return jsonify({
                    "error": "conflict",
                    "message": "File was modified externally",
                    "current_mtime": result.last_modified.isoformat() if result.last_modified else None,
                    "expected_mtime": expected_mtime.isoformat() if expected_mtime else None,
                }), 409

            if "Permission denied" in (result.error or ""):
                return jsonify({
                    "error": "permission_denied",
                    "message": f"Save failed: {result.error}. Check directory permissions.",
                    "path": project.path,
                }), 403

            return jsonify({
                "error": "save_error",
                "message": result.error or "Failed to save waypoint",
            }), 500

        response = {
            "success": True,
            "archived": result.archived,
        }

        if result.archive_path:
            response["archive_path"] = result.archive_path
        if result.last_modified:
            response["last_modified"] = result.last_modified.isoformat()

        return jsonify(response), 200

    except Exception as e:
        logger.exception(f"Error saving waypoint for project {project_id}")
        return jsonify({
            "error": "save_error",
            "message": f"Failed to save waypoint: {type(e).__name__}",
        }), 500


@waypoint_bp.route("/api/waypoint/projects", methods=["GET"])
def list_projects_for_waypoint():
    """
    List all projects for the waypoint editor dropdown.

    Returns:
        200: List of projects with id and name
    """
    projects = db.session.query(Project).order_by(Project.name).all()

    return jsonify({
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "path": p.path,
            }
            for p in projects
        ]
    }), 200
