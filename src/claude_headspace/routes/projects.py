"""Project management API and page endpoints."""

import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..database import db
from ..models.agent import Agent
from .hooks import rate_limited
from ..models.inference_call import InferenceCall
from ..models.project import Project, generate_slug
from ..models.command import Command
from ..models.turn import Turn

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
        projects = (
            db.session.query(Project)
            .options(selectinload(Project.agents))
            .order_by(db.func.lower(Project.name).asc())
            .all()
        )

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
@rate_limited
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

    if not os.path.isabs(path):
        return jsonify({"error": "Project path must be an absolute path"}), 400

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

        # Paginated agents, ordered by last_seen_at descending
        page = request.args.get("agents_page", 1, type=int)
        per_page = request.args.get("agents_per_page", 10, type=int)
        per_page = max(1, min(per_page, 100))
        include_ended = request.args.get("include_ended", "false").lower() == "true"

        agents_query = (
            db.session.query(Agent)
            .filter(Agent.project_id == project.id)
        )
        if not include_ended:
            agents_query = agents_query.filter(Agent.ended_at.is_(None))
        agents_query = agents_query.order_by(Agent.last_seen_at.desc().nullslast())

        total_agents = agents_query.count()
        agents_page = agents_query.offset((page - 1) * per_page).limit(per_page).all()

        # Always compute active agent count (ended_at IS NULL)
        active_agent_count = (
            db.session.query(Agent)
            .filter(Agent.project_id == project.id, Agent.ended_at.is_(None))
            .count()
        )

        # Batch-compute per-agent metrics for the current page
        agent_ids = [a.id for a in agents_page]
        agent_metrics = {}
        if agent_ids:
            # Turn counts and frustration averages per agent
            turn_stats = (
                db.session.query(
                    Command.agent_id,
                    func.count(Turn.id).label("turn_count"),
                    func.avg(Turn.frustration_score).label("frustration_avg"),
                )
                .join(Turn, Turn.command_id == Command.id)
                .filter(Command.agent_id.in_(agent_ids))
                .group_by(Command.agent_id)
                .all()
            )
            for row in turn_stats:
                agent_metrics[row.agent_id] = {
                    "turn_count": row.turn_count or 0,
                    "frustration_avg": round(float(row.frustration_avg), 1) if row.frustration_avg is not None else None,
                }

            # Approximate avg turn time per agent:
            # For each command, compute (max_timestamp - min_timestamp) / (count - 1)
            # then average across commands
            from sqlalchemy import case
            avg_turn_time_stats = (
                db.session.query(
                    Command.agent_id,
                    case(
                        (func.count(Turn.id) > 1,
                         func.extract("epoch", func.max(Turn.timestamp) - func.min(Turn.timestamp))
                         / (func.count(Turn.id) - 1)),
                        else_=None,
                    ).label("avg_turn_time"),
                )
                .join(Turn, Turn.command_id == Command.id)
                .filter(Command.agent_id.in_(agent_ids))
                .group_by(Command.agent_id, Command.id)
            ).subquery()

            avg_per_agent = (
                db.session.query(
                    avg_turn_time_stats.c.agent_id,
                    func.avg(avg_turn_time_stats.c.avg_turn_time).label("avg_turn_time"),
                )
                .group_by(avg_turn_time_stats.c.agent_id)
                .all()
            )
            for row in avg_per_agent:
                if row.agent_id in agent_metrics:
                    agent_metrics[row.agent_id]["avg_turn_time"] = (
                        round(float(row.avg_turn_time), 1) if row.avg_turn_time is not None else None
                    )
                else:
                    agent_metrics[row.agent_id] = {
                        "turn_count": 0,
                        "frustration_avg": None,
                        "avg_turn_time": round(float(row.avg_turn_time), 1) if row.avg_turn_time is not None else None,
                    }

        agents_data = []
        for a in agents_page:
            metrics = agent_metrics.get(a.id, {})
            state_value = a.state.value if hasattr(a.state, "value") else str(a.state)
            if a.ended_at is not None:
                state_value = "ended"
            agent_dict = {
                "id": a.id,
                "session_uuid": str(a.session_uuid) if a.session_uuid else None,
                "state": state_value,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
                "priority_score": a.priority_score,
                "turn_count": metrics.get("turn_count", 0),
                "frustration_avg": metrics.get("frustration_avg"),
                "avg_turn_time": metrics.get("avg_turn_time"),
            }
            if getattr(a, "persona_id", None) is not None:
                persona = a.persona
                if persona is not None:
                    role = getattr(persona, "role", None)
                    agent_dict["persona_name"] = persona.name
                    agent_dict["persona_role"] = role.name if role else None
            agents_data.append(agent_dict)

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
            "active_agent_count": active_agent_count,
            "agents": agents_data,
            "agents_pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_agents,
                "total_pages": (total_agents + per_page - 1) // per_page,
            },
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

        # Delete inference_calls before the project to avoid violating
        # ck_inference_calls_has_parent.  The project cascade (Project →
        # Agent → Command → Turn) would SET NULL every FK on inference_calls,
        # leaving rows with no parent at all.
        agent_subq = db.session.query(Agent.id).filter(Agent.project_id == project_id)
        command_subq = db.session.query(Command.id).filter(Command.agent_id.in_(agent_subq))
        turn_subq = db.session.query(Turn.id).filter(Turn.command_id.in_(command_subq))

        InferenceCall.query.filter(
            db.or_(
                InferenceCall.project_id == project_id,
                InferenceCall.agent_id.in_(agent_subq),
                InferenceCall.command_id.in_(command_subq),
                InferenceCall.turn_id.in_(turn_subq),
            )
        ).delete(synchronize_session=False)

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


# --- Drill-down endpoints ---


@projects_bp.route("/api/agents/<int:agent_id>/commands", methods=["GET"])
def get_agent_commands(agent_id: int):
    """Get all commands for a specific agent."""
    try:
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        commands = (
            db.session.query(Command)
            .filter(Command.agent_id == agent_id)
            .order_by(Command.started_at.asc())
            .all()
        )

        # Batch turn counts in a single query
        command_ids = [c.id for c in commands]
        turn_counts = {}
        if command_ids:
            rows = (
                db.session.query(Turn.command_id, func.count(Turn.id))
                .filter(Turn.command_id.in_(command_ids))
                .group_by(Turn.command_id)
                .all()
            )
            turn_counts = {row[0]: row[1] for row in rows}

        result = []
        for c in commands:
            result.append({
                "id": c.id,
                "state": c.state.value if hasattr(c.state, "value") else str(c.state),
                "instruction": c.instruction,
                "completion_summary": c.completion_summary,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "turn_count": turn_counts.get(c.id, 0),
            })

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to get commands for agent %s", agent_id)
        return jsonify({"error": "Failed to get agent commands"}), 500


@projects_bp.route("/api/commands/<int:command_id>/turns", methods=["GET"])
def get_command_turns(command_id: int):
    """Get all turns for a specific command."""
    try:
        command = db.session.get(Command, command_id)
        if not command:
            return jsonify({"error": "Command not found"}), 404

        turns = (
            db.session.query(Turn)
            .filter(Turn.command_id == command_id)
            .filter(Turn.is_internal == False)  # noqa: E712
            .order_by(Turn.timestamp.asc())
            .all()
        )

        result = []
        for turn in turns:
            text = turn.text or ""
            text_truncated = len(text) > 500
            result.append({
                "id": turn.id,
                "actor": turn.actor.value if hasattr(turn.actor, "value") else str(turn.actor),
                "intent": turn.intent.value if hasattr(turn.intent, "value") else str(turn.intent),
                "text": text[:500] if text_truncated else text,
                "text_truncated": text_truncated,
                "summary": turn.summary,
                "frustration_score": turn.frustration_score,
                "created_at": turn.timestamp.isoformat() if turn.timestamp else None,
            })

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to get turns for command %s", command_id)
        return jsonify({"error": "Failed to get command turns"}), 500


@projects_bp.route("/api/commands/<int:command_id>/full-text", methods=["GET"])
def get_command_full_text(command_id: int):
    """Get full command and full output text for a command (on-demand)."""
    try:
        command = db.session.get(Command, command_id)
        if not command:
            return jsonify({"error": "Command not found"}), 404

        return jsonify({
            "full_command": command.full_command,
            "full_output": command.full_output,
            "plan_content": command.plan_content,
            "plan_file_path": command.plan_file_path,
        }), 200

    except Exception:
        logger.exception("Failed to get full text for command %s", command_id)
        return jsonify({"error": "Failed to get command full text"}), 500


@projects_bp.route("/api/projects/<int:project_id>/inference-summary", methods=["GET"])
def get_project_inference_summary(project_id: int):
    """Get aggregate inference metrics for a project."""
    try:
        project = db.session.get(Project, project_id)
        if not project:
            return jsonify({"error": "Project not found"}), 404

        # Aggregate inference calls scoped to this project
        # Join through agents that belong to this project
        row = (
            db.session.query(
                func.count(InferenceCall.id).label("total_calls"),
                func.coalesce(func.sum(InferenceCall.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(InferenceCall.output_tokens), 0).label("total_output_tokens"),
                func.coalesce(func.sum(InferenceCall.cost), 0).label("total_cost"),
            )
            .filter(InferenceCall.project_id == project_id)
            .one()
        )

        return jsonify({
            "project_id": project_id,
            "total_calls": row.total_calls,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_cost": float(row.total_cost) if row.total_cost else 0.0,
        }), 200

    except Exception:
        logger.exception("Failed to get inference summary for project %s", project_id)
        return jsonify({"error": "Failed to get inference summary"}), 500
