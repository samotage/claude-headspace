"""Project management API and page endpoints."""

import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template, request

from ..database import db
from ..models.project import Project, generate_slug

logger = logging.getLogger(__name__)

projects_bp = Blueprint("projects", __name__)


def _unique_slug(name: str, exclude_id: int | None = None) -> str:
    """Generate a unique slug, appending numeric suffix on collision."""
    base = generate_slug(name)
    slug = base
    counter = 2
    while True:
        query = Project.query.filter_by(slug=slug)
        if exclude_id is not None:
            query = query.filter(Project.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base}-{counter}"
        counter += 1


@projects_bp.route("/projects")
def projects_page():
    """Projects management page."""
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("projects.html", status_counts=status_counts)


@projects_bp.route("/projects/<slug>")
def project_show(slug: str):
    """Project detail show page."""
    project = Project.query.filter_by(slug=slug).first()
    if not project:
        return render_template("404.html", message=f"Project not found: {slug}"), 404

    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template(
        "project_show.html",
        project=project,
        status_counts=status_counts,
    )


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
                "slug": p.slug,
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
            slug=_unique_slug(name),
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
            "slug": project.slug,
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
            "slug": project.slug,
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
            if name and name != project.name:
                project.name = name
                project.slug = _unique_slug(name, exclude_id=project.id)

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
            "slug": project.slug,
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


# --- Metadata detection ---


@projects_bp.route("/api/projects/<int:project_id>/detect-metadata", methods=["POST"])
def detect_metadata(project_id: int):
    """Detect project metadata from git remote and CLAUDE.md.

    Detects values for empty fields, persists them to the database,
    and returns what was detected.  Inference calls are logged via
    the standard InferenceService pipeline.

    Returns:
        200: Detected metadata (null for anything not detected)
        404: Project not found
    """
    try:
        project = db.session.get(Project, project_id)

        if not project:
            return jsonify({"error": "Project not found"}), 404

        result = {"github_repo": None, "description": None}
        dirty = False

        # Detect github_repo from git remote
        if not project.github_repo and project.path:
            try:
                from ..services.git_metadata import GitMetadata
                git_metadata = current_app.extensions.get("git_metadata")
                if git_metadata:
                    git_metadata.invalidate_cache(project.path)
                    git_info = git_metadata.get_git_info(project.path)
                    if git_info.repo_url:
                        owner_repo = GitMetadata.parse_owner_repo(git_info.repo_url)
                        if owner_repo:
                            result["github_repo"] = owner_repo
                            project.github_repo = owner_repo
                            dirty = True
            except Exception as e:
                logger.debug(f"Git metadata detection failed for project {project_id}: {e}")

        # Detect description from CLAUDE.md via LLM
        if not project.description and project.path:
            try:
                claude_md_path = os.path.join(project.path, "CLAUDE.md")
                if os.path.isfile(claude_md_path):
                    with open(claude_md_path, "r", encoding="utf-8") as f:
                        claude_md_content = f.read(8000)

                    if claude_md_content.strip():
                        inference_service = current_app.extensions.get("inference_service")
                        if inference_service and inference_service.is_available:
                            from ..services.prompt_registry import build_prompt
                            from ..services.summarisation_service import SummarisationService

                            prompt = build_prompt(
                                "project_description",
                                claude_md_content=claude_md_content,
                            )
                            inference_result = inference_service.infer(
                                level="project",
                                purpose="project_description",
                                input_text=prompt,
                                project_id=project_id,
                            )
                            if inference_result.text:
                                cleaned = SummarisationService._clean_response(inference_result.text)
                                result["description"] = cleaned
                                project.description = cleaned
                                dirty = True
            except Exception as e:
                logger.debug(f"Description detection failed for project {project_id}: {e}")

        if dirty:
            try:
                db.session.commit()
                _broadcast_project_event("project_changed", {
                    "action": "updated",
                    "project_id": project.id,
                })
            except Exception as e:
                logger.warning(f"Failed to persist detected metadata for project {project_id}: {e}")
                db.session.rollback()

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to detect metadata for project %s", project_id)
        return jsonify({"error": "Failed to detect metadata"}), 500
