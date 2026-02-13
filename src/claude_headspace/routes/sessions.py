"""Session management API routes for CLI launcher integration."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request

from ..database import db
from ..models.agent import Agent
from ..models.project import Project


def _broadcast_session_event(agent: Agent, event_type: str) -> None:
    """Broadcast session lifecycle event to SSE clients."""
    try:
        from ..services.broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        broadcaster.broadcast(event_type, {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "session_uuid": str(agent.session_uuid),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"Broadcast failed (non-fatal): {e}")

logger = logging.getLogger(__name__)

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/api/sessions", methods=["POST"])
def create_session():
    """
    Register a new Claude Code session.

    Accepts JSON payload:
        - session_uuid: UUID identifying this session
        - project_path: Absolute path to the project directory
        - working_directory: Current working directory (usually same as project_path)
        - iterm_pane_id: Optional iTerm2 pane identifier
        - tmux_pane_id: Optional tmux pane identifier for input bridge
        - project_name: Optional project name (defaults to directory name)
        - current_branch: Optional git branch name

    Returns:
        201: Session created successfully
        400: Invalid request (missing required fields)
        500: Server error
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # Validate required fields
    required_fields = ["session_uuid", "project_path"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        session_uuid = UUID(data["session_uuid"])
    except ValueError:
        return jsonify({"error": "Invalid session_uuid format"}), 400

    project_path = data["project_path"]
    working_directory = data.get("working_directory", project_path)
    iterm_pane_id = data.get("iterm_pane_id")
    tmux_pane_id = data.get("tmux_pane_id")
    project_name = data.get("project_name")
    current_branch = data.get("current_branch")

    # Default project name to directory name if not provided
    if not project_name:
        project_name = project_path.rstrip("/").split("/")[-1]

    try:
        # Find or auto-create project
        project = Project.query.filter_by(path=project_path).first()
        if project is None:
            # Auto-create project from session info
            from ..models.project import generate_slug
            slug = generate_slug(project_name)
            # Ensure slug uniqueness by appending a suffix if needed
            base_slug = slug
            counter = 1
            while Project.query.filter_by(slug=slug).first() is not None:
                slug = f"{base_slug}-{counter}"
                counter += 1
            project = Project(
                name=project_name,
                slug=slug,
                path=project_path,
                current_branch=current_branch,
            )
            db.session.add(project)
            db.session.flush()  # Get the ID before creating the agent
            logger.info(f"Auto-created project: {project.name} (id={project.id}, path={project_path})")
        else:
            # Update branch if provided
            if current_branch:
                project.current_branch = current_branch
            logger.info(f"Using existing project: {project.name} (id={project.id})")

        # Check if agent with this session_uuid already exists
        existing_agent = Agent.query.filter_by(session_uuid=session_uuid).first()
        if existing_agent:
            return jsonify({
                "error": f"Session {session_uuid} already exists",
                "agent_id": existing_agent.id,
            }), 409

        # Create agent
        agent = Agent(
            session_uuid=session_uuid,
            project_id=project.id,
            iterm_pane_id=iterm_pane_id,
            tmux_pane_id=tmux_pane_id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.session.add(agent)
        db.session.commit()

        logger.info(
            f"Created session {session_uuid} for project {project.name} "
            f"(agent_id={agent.id}, iterm_pane_id={iterm_pane_id}, "
            f"tmux_pane_id={tmux_pane_id})"
        )

        # Register with availability tracker if tmux pane is provided
        if tmux_pane_id:
            commander_availability = current_app.extensions.get("commander_availability")
            if commander_availability:
                commander_availability.register_agent(agent.id, tmux_pane_id)

        # Broadcast to SSE clients so dashboard updates in real-time
        _broadcast_session_event(agent, "session_created")

        return jsonify({
            "status": "created",
            "agent_id": agent.id,
            "session_uuid": str(session_uuid),
            "project_id": project.id,
            "project_name": project.name,
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating session: {e}")
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/api/sessions/<uuid:session_uuid>", methods=["DELETE"])
def delete_session(session_uuid: UUID):
    """
    Mark a session as ended.

    Args:
        session_uuid: UUID of the session to end

    Returns:
        200: Session marked as ended
        404: Session not found
        500: Server error
    """
    try:
        agent = Agent.query.filter_by(session_uuid=session_uuid).first()

        if agent is None:
            return jsonify({
                "error": f"Session {session_uuid} not found",
            }), 404

        # Mark agent as ended
        # The agent remains in database for historical tracking
        now = datetime.now(timezone.utc)
        agent.last_seen_at = now
        agent.ended_at = now
        db.session.commit()

        logger.info(f"Marked session {session_uuid} as ended (agent_id={agent.id})")

        # Broadcast to SSE clients so dashboard removes the card
        _broadcast_session_event(agent, "session_ended")

        return jsonify({
            "status": "ended",
            "session_uuid": str(session_uuid),
            "agent_id": agent.id,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error ending session: {e}")
        return jsonify({"error": str(e)}), 500


@sessions_bp.route("/api/sessions/<uuid:session_uuid>", methods=["GET"])
def get_session(session_uuid: UUID):
    """
    Get session information.

    Args:
        session_uuid: UUID of the session

    Returns:
        200: Session found
        404: Session not found
    """
    agent = Agent.query.filter_by(session_uuid=session_uuid).first()

    if agent is None:
        return jsonify({
            "error": f"Session {session_uuid} not found",
        }), 404

    return jsonify({
        "session_uuid": str(agent.session_uuid),
        "agent_id": agent.id,
        "project_id": agent.project_id,
        "project_name": agent.project.name,
        "iterm_pane_id": agent.iterm_pane_id,
        "started_at": agent.started_at.isoformat(),
        "last_seen_at": agent.last_seen_at.isoformat(),
        "state": agent.state.value,
    }), 200
