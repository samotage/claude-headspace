"""Logging API endpoints and page route."""

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from ..database import db
from ..models.agent import Agent
from ..models.event import Event, EventType
from ..models.project import Project

logging_bp = Blueprint("logging", __name__)


@logging_bp.route("/logging")
def logging_page():
    """
    Logging tab page.

    Returns:
        Rendered logging template
    """
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("logging.html", status_counts=status_counts)


@logging_bp.route("/api/events", methods=["GET"])
def get_events():
    """
    Get paginated events with optional filtering.

    Query parameters:
        - project_id (optional): Filter by project ID
        - agent_id (optional): Filter by agent ID
        - event_type (optional): Filter by event type
        - page (optional, default=1): Page number
        - per_page (optional, default=50): Items per page (max 100)

    Returns:
        JSON with paginated events and metadata
    """
    try:
        # Parse query parameters
        project_id = request.args.get("project_id", type=int)
        agent_id = request.args.get("agent_id", type=int)
        event_type = request.args.get("event_type", type=str)
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 50
        if per_page > 100:
            per_page = 100

        # Build base query
        query = db.session.query(Event)

        # Apply filters
        if project_id is not None:
            query = query.filter(Event.project_id == project_id)
        if agent_id is not None:
            query = query.filter(Event.agent_id == agent_id)
        if event_type:
            query = query.filter(Event.event_type == event_type)

        # Get total count for pagination
        total = query.count()

        # Calculate offset and apply pagination
        offset = (page - 1) * per_page

        # Get events with ordering
        events = (
            query.order_by(Event.timestamp.desc()).offset(offset).limit(per_page).all()
        )

        # Resolve project and agent names
        # Get all unique project IDs and agent IDs from results
        project_ids = {e.project_id for e in events if e.project_id is not None}
        agent_ids = {e.agent_id for e in events if e.agent_id is not None}

        # Fetch project names
        project_names = {}
        if project_ids:
            projects = (
                db.session.query(Project.id, Project.name)
                .filter(Project.id.in_(project_ids))
                .all()
            )
            project_names = {p.id: p.name for p in projects}

        # Fetch agent session UUIDs
        agent_sessions = {}
        if agent_ids:
            agents = (
                db.session.query(Agent.id, Agent.session_uuid)
                .filter(Agent.id.in_(agent_ids))
                .all()
            )
            agent_sessions = {a.id: str(a.session_uuid) for a in agents}

        # Calculate total pages
        pages = (total + per_page - 1) // per_page if total > 0 else 0

        return jsonify(
            {
                "events": [
                    {
                        "id": event.id,
                        "timestamp": (
                            event.timestamp.isoformat() if event.timestamp else None
                        ),
                        "project_id": event.project_id,
                        "project_name": project_names.get(event.project_id),
                        "agent_id": event.agent_id,
                        "agent_session": agent_sessions.get(event.agent_id),
                        "event_type": event.event_type,
                        "payload": event.payload,
                    }
                    for event in events
                ],
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
                "has_next": page < pages,
                "has_previous": page > 1,
            }
        )

    except Exception as e:
        return jsonify({"error": "Failed to fetch events"}), 500


@logging_bp.route("/api/events/filters", methods=["GET"])
def get_event_filters():
    """
    Get available filter options.

    Returns only items that have associated events.

    Returns:
        JSON with available projects, agents, and event types
    """
    try:
        # Get projects that have events
        projects_with_events = (
            db.session.query(Project.id, Project.name)
            .join(Event, Event.project_id == Project.id)
            .distinct()
            .order_by(Project.name)
            .all()
        )

        # Get agents that have events
        agents_with_events = (
            db.session.query(Agent.id, Agent.session_uuid)
            .join(Event, Event.agent_id == Agent.id)
            .distinct()
            .order_by(Agent.id)
            .all()
        )

        # Get distinct event types
        event_types = (
            db.session.query(Event.event_type)
            .distinct()
            .order_by(Event.event_type)
            .all()
        )

        return jsonify(
            {
                "projects": [
                    {"id": p.id, "name": p.name} for p in projects_with_events
                ],
                "agents": [
                    {"id": a.id, "session_uuid": str(a.session_uuid)}
                    for a in agents_with_events
                ],
                "event_types": [et[0] for et in event_types],
            }
        )

    except Exception as e:
        return jsonify({"error": "Failed to fetch filter options"}), 500
