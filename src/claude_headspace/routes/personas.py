"""REST API endpoints for persona management."""

import logging

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from ..database import db
from ..models.agent import Agent
from ..models.command import Command
from ..models.persona import Persona
from ..models.role import Role
from ..models.turn import Turn
from ..services.persona_assets import (
    check_assets,
    get_experience_mtime,
    read_experience_file,
    read_skill_file,
    write_skill_file,
)
from ..services.persona_registration import RegistrationError, register_persona

logger = logging.getLogger(__name__)

personas_bp = Blueprint("personas", __name__)


# --- Page route ---


@personas_bp.route("/personas")
def personas_page():
    """Personas management page."""
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("personas.html", status_counts=status_counts)


@personas_bp.route("/personas/<slug>")
def persona_detail_page(slug: str):
    """Persona detail page."""
    persona = (
        db.session.query(Persona)
        .options(selectinload(Persona.role))
        .filter_by(slug=slug)
        .first()
    )

    if not persona:
        return render_template("404.html"), 404

    return render_template("persona_detail.html", persona=persona)


# --- API endpoints ---


@personas_bp.route("/api/personas/register", methods=["POST"])
def api_register_persona():
    """Register a new persona via REST API.

    Accepts JSON:
        - name (required): Persona display name
        - role (required): Role name (lowercased on input)
        - description (optional): Persona description

    Returns:
        201: Persona created with {slug, id, path}
        400: Validation error
        500: Server error
    """
    data = request.get_json(silent=True) or {}

    name = data.get("name", "")
    role_name = data.get("role", "")
    description = data.get("description")

    try:
        result = register_persona(
            name=name, role_name=role_name, description=description
        )
    except RegistrationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error during persona registration")
        return jsonify({"error": f"Server error: {e}"}), 500

    return jsonify({
        "slug": result.slug,
        "id": result.id,
        "path": result.path,
    }), 201


@personas_bp.route("/api/personas/<slug>/validate", methods=["GET"])
def api_validate_persona(slug: str):
    """Validate that a persona slug exists and is active.

    Returns:
        200: Persona exists and is active {valid: true, slug, id, name}
        404: Persona not found or not active {valid: false, error}
    """
    persona = Persona.query.filter_by(slug=slug, status="active").first()
    if not persona:
        return jsonify({
            "valid": False,
            "error": f"Persona '{slug}' not found or not active. "
            "Register the persona first with: flask persona register --name <name> --role <role>",
        }), 404

    return jsonify({
        "valid": True,
        "slug": persona.slug,
        "id": persona.id,
        "name": persona.name,
    }), 200


@personas_bp.route("/api/personas/active", methods=["GET"])
def api_list_active_personas():
    """List active personas grouped by role for the agent creation selector.

    Returns JSON array of active personas with role info, ordered by role name
    then persona name. Designed for the dashboard "New Agent" persona selector.

    Returns:
        200: Array of active persona objects with role grouping info
    """
    try:
        personas = (
            db.session.query(Persona)
            .options(selectinload(Persona.role))
            .filter(Persona.status == "active")
            .join(Persona.role)
            .order_by(Role.name.asc(), Persona.name.asc())
            .all()
        )

        result = []
        for p in personas:
            result.append({
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "role": p.role.name if p.role else None,
                "description": p.description,
            })

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to list active personas")
        return jsonify({"error": "Failed to list active personas"}), 500


@personas_bp.route("/api/personas", methods=["GET"])
def api_list_personas():
    """List all personas with role name, status, agent count, created_at.

    Returns JSON array ordered by created_at descending.
    """
    try:
        # Use a subquery for agent count instead of eagerly loading all agents
        agent_count_subq = (
            db.session.query(func.count(Agent.id))
            .filter(Agent.persona_id == Persona.id)
            .correlate(Persona)
            .scalar_subquery()
        )

        rows = (
            db.session.query(Persona, agent_count_subq.label("agent_count"))
            .options(selectinload(Persona.role))
            .order_by(Persona.created_at.desc())
            .all()
        )

        result = []
        for p, agent_count in rows:
            result.append({
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "role": p.role.name if p.role else None,
                "description": p.description,
                "status": p.status,
                "agent_count": agent_count or 0,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to list personas")
        return jsonify({"error": "Failed to list personas"}), 500


@personas_bp.route("/api/personas/<slug>", methods=["GET"])
def api_get_persona(slug: str):
    """Get single persona detail by slug.

    Returns:
        200: Persona detail
        404: Not found
    """
    try:
        persona = (
            db.session.query(Persona)
            .options(selectinload(Persona.role))
            .filter_by(slug=slug)
            .first()
        )

        if not persona:
            return jsonify({"error": f"Persona '{slug}' not found"}), 404

        agent_count = (
            db.session.query(func.count(Agent.id))
            .filter(Agent.persona_id == persona.id)
            .scalar()
        ) or 0

        return jsonify({
            "id": persona.id,
            "slug": persona.slug,
            "name": persona.name,
            "role": persona.role.name if persona.role else None,
            "description": persona.description,
            "status": persona.status,
            "agent_count": agent_count,
            "created_at": persona.created_at.isoformat() if persona.created_at else None,
        }), 200

    except Exception:
        logger.exception("Failed to get persona %s", slug)
        return jsonify({"error": "Failed to get persona"}), 500


@personas_bp.route("/api/personas/<slug>", methods=["PUT"])
def api_update_persona(slug: str):
    """Update persona fields.

    Accepts JSON with any of:
        - name: Display name (required, non-empty)
        - description: Persona description
        - status: Persona status (e.g. "active", "archived")

    Returns:
        200: Updated persona
        400: Validation error
        404: Not found
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        persona = (
            db.session.query(Persona)
            .options(selectinload(Persona.role))
            .filter_by(slug=slug)
            .first()
        )

        if not persona:
            return jsonify({"error": f"Persona '{slug}' not found"}), 404

        # Update name
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                return jsonify({"error": "Name is required and cannot be empty"}), 400
            persona.name = name

        # Update description
        if "description" in data:
            persona.description = (data["description"] or "").strip() or None

        # Update status
        if "status" in data:
            status = (data["status"] or "").strip().lower()
            if status not in ("active", "archived"):
                return jsonify({"error": "Status must be 'active' or 'archived'"}), 400
            persona.status = status

        db.session.commit()

        agent_count = (
            db.session.query(func.count(Agent.id))
            .filter(Agent.persona_id == persona.id)
            .scalar()
        ) or 0

        return jsonify({
            "id": persona.id,
            "slug": persona.slug,
            "name": persona.name,
            "role": persona.role.name if persona.role else None,
            "description": persona.description,
            "status": persona.status,
            "agent_count": agent_count,
            "created_at": persona.created_at.isoformat() if persona.created_at else None,
        }), 200

    except Exception:
        logger.exception("Failed to update persona %s", slug)
        db.session.rollback()
        return jsonify({"error": "Failed to update persona"}), 500


@personas_bp.route("/api/personas/<slug>", methods=["DELETE"])
def api_delete_persona(slug: str):
    """Delete a persona permanently.

    Linked agents are preserved — their persona_id FK is set to NULL
    (the DB column has ondelete=SET NULL, but we also null explicitly
    to keep the SQLAlchemy session consistent). Filesystem assets
    (skill.md, experience.md) are intentionally retained.

    Returns:
        200: Deleted (includes count of unlinked agents)
        404: Not found
    """
    try:
        persona = (
            db.session.query(Persona)
            .options(selectinload(Persona.agents))
            .filter_by(slug=slug)
            .first()
        )

        if not persona:
            return jsonify({"error": f"Persona '{slug}' not found"}), 404

        persona_name = persona.name
        persona_id = persona.id
        agent_count = len(persona.agents)

        # Unlink agents (null their persona FK) rather than deleting them
        for agent in list(persona.agents):
            agent.persona_id = None

        db.session.delete(persona)
        db.session.commit()

        logger.info(
            "Deleted persona %s (id=%d), unlinked %d agent(s)",
            persona_name, persona_id, agent_count,
        )

        return jsonify({
            "deleted": True,
            "id": persona_id,
            "name": persona_name,
            "agents_unlinked": agent_count,
        }), 200

    except Exception:
        logger.exception("Failed to delete persona %s", slug)
        db.session.rollback()
        return jsonify({"error": "Failed to delete persona"}), 500


# --- Persona asset endpoints ---


@personas_bp.route("/api/personas/<slug>/skill", methods=["GET"])
def api_persona_skill_read(slug: str):
    """Read a persona's skill.md content.

    Returns:
        200: {content, exists}
        404: Persona not found in DB
    """
    persona = Persona.query.filter_by(slug=slug).first()
    if not persona:
        return jsonify({"error": f"Persona '{slug}' not found"}), 404

    content = read_skill_file(slug)
    return jsonify({
        "content": content or "",
        "exists": content is not None,
    }), 200


@personas_bp.route("/api/personas/<slug>/skill", methods=["PUT"])
def api_persona_skill_write(slug: str):
    """Write a persona's skill.md content.

    Accepts JSON: {content: string}

    Returns:
        200: {saved: true}
        400: Missing content
        404: Persona not found in DB
    """
    persona = Persona.query.filter_by(slug=slug).first()
    if not persona:
        return jsonify({"error": f"Persona '{slug}' not found"}), 404

    data = request.get_json(silent=True)
    if not data or "content" not in data:
        return jsonify({"error": "Request body must include 'content' field"}), 400

    try:
        write_skill_file(slug, data["content"])
    except Exception:
        logger.exception("Failed to write skill file for %s", slug)
        return jsonify({"error": "Failed to write skill file"}), 500

    return jsonify({"saved": True}), 200


@personas_bp.route("/api/personas/<slug>/experience", methods=["GET"])
def api_persona_experience_read(slug: str):
    """Read a persona's experience.md content.

    Returns:
        200: {content, exists, last_modified}
        404: Persona not found in DB
    """
    persona = Persona.query.filter_by(slug=slug).first()
    if not persona:
        return jsonify({"error": f"Persona '{slug}' not found"}), 404

    content = read_experience_file(slug)
    mtime = get_experience_mtime(slug)
    return jsonify({
        "content": content or "",
        "exists": content is not None,
        "last_modified": mtime,
    }), 200


@personas_bp.route("/api/personas/<slug>/assets", methods=["GET"])
def api_persona_assets(slug: str):
    """Check persona asset file existence.

    Returns:
        200: {skill_exists, experience_exists, directory_exists}
        404: Persona not found in DB
    """
    persona = Persona.query.filter_by(slug=slug).first()
    if not persona:
        return jsonify({"error": f"Persona '{slug}' not found"}), 404

    status = check_assets(slug)
    return jsonify({
        "skill_exists": status.skill_exists,
        "experience_exists": status.experience_exists,
        "directory_exists": status.directory_exists,
    }), 200


@personas_bp.route("/api/personas/<slug>/agents", methods=["GET"])
def api_persona_linked_agents(slug: str):
    """List agents linked to a persona.

    Supports ``include_ended=true`` query param to include ended agents
    (default: only active agents).  Returns ``active_agent_count`` alongside
    the agents list so the frontend can display a count badge.

    Returns:
        200: ``{ agents: [...], active_agent_count: int }``
        404: Persona not found in DB
    """
    persona = (
        db.session.query(Persona)
        .filter_by(slug=slug)
        .first()
    )

    if not persona:
        return jsonify({"error": f"Persona '{slug}' not found"}), 404

    include_ended = request.args.get("include_ended", "false").lower() == "true"

    agents_query = (
        db.session.query(Agent)
        .options(selectinload(Agent.project))
        .filter(Agent.persona_id == persona.id)
    )
    if not include_ended:
        agents_query = agents_query.filter(Agent.ended_at.is_(None))
    agents_query = agents_query.order_by(Agent.last_seen_at.desc().nullslast())
    agents_list = agents_query.all()

    active_agent_count = (
        db.session.query(Agent)
        .filter(Agent.persona_id == persona.id, Agent.ended_at.is_(None))
        .count()
    )

    # Batch-compute per-agent metrics
    agent_ids = [a.id for a in agents_list]
    agent_metrics: dict = {}
    if agent_ids:
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
                "frustration_avg": (
                    round(float(row.frustration_avg), 1)
                    if row.frustration_avg is not None
                    else None
                ),
            }

        avg_turn_time_sub = (
            db.session.query(
                Command.agent_id,
                case(
                    (
                        func.count(Turn.id) > 1,
                        func.extract(
                            "epoch",
                            func.max(Turn.timestamp) - func.min(Turn.timestamp),
                        )
                        / (func.count(Turn.id) - 1),
                    ),
                    else_=None,
                ).label("avg_turn_time"),
            )
            .join(Turn, Turn.command_id == Command.id)
            .filter(Command.agent_id.in_(agent_ids))
            .group_by(Command.agent_id, Command.id)
        ).subquery()

        avg_per_agent = (
            db.session.query(
                avg_turn_time_sub.c.agent_id,
                func.avg(avg_turn_time_sub.c.avg_turn_time).label("avg_turn_time"),
            )
            .group_by(avg_turn_time_sub.c.agent_id)
            .all()
        )
        for row in avg_per_agent:
            entry = agent_metrics.setdefault(
                row.agent_id,
                {"turn_count": 0, "frustration_avg": None},
            )
            entry["avg_turn_time"] = (
                round(float(row.avg_turn_time), 1)
                if row.avg_turn_time is not None
                else None
            )

    agents_data = []
    for a in agents_list:
        metrics = agent_metrics.get(a.id, {})
        state_value = a.state.value if hasattr(a.state, "value") else str(a.state)
        if a.ended_at is not None:
            state_value = "ended"
        agents_data.append({
            "id": a.id,
            "session_uuid": str(a.session_uuid) if a.session_uuid else None,
            "project_name": a.project.name if a.project else None,
            "state": state_value,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "ended_at": a.ended_at.isoformat() if a.ended_at else None,
            "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
            "turn_count": metrics.get("turn_count", 0),
            "frustration_avg": metrics.get("frustration_avg"),
            "avg_turn_time": metrics.get("avg_turn_time"),
        })

    return jsonify({
        "agents": agents_data,
        "active_agent_count": active_agent_count,
    }), 200


@personas_bp.route("/api/roles", methods=["GET"])
def api_list_roles():
    """List all roles.

    Returns JSON array of roles with id, name, description, created_at.
    """
    try:
        roles = (
            db.session.query(Role)
            .order_by(Role.name.asc())
            .all()
        )

        result = []
        for r in roles:
            result.append({
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return jsonify(result), 200

    except Exception:
        logger.exception("Failed to list roles")
        return jsonify({"error": "Failed to list roles"}), 500
