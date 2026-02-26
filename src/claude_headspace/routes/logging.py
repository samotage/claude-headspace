"""Logging API endpoints and page route."""

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import func, or_

from ..database import db
from ..models.agent import Agent
from ..models.api_call_log import ApiCallLog
from ..models.event import Event, EventType
from ..models.inference_call import InferenceCall
from ..models.project import Project
from ..models.turn import Turn

logger = logging.getLogger(__name__)

_DEFAULT_ACTIVE_TIMEOUT_MINUTES = 5

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
        per_page = max(1, min(per_page, 100))

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

        # Fetch turn data for events that reference turns
        turn_ids = {e.turn_id for e in events if e.turn_id is not None}
        turn_data = {}
        if turn_ids:
            turns = (
                db.session.query(Turn.id, Turn.actor, Turn.text, Turn.summary)
                .filter(Turn.id.in_(turn_ids))
                .all()
            )
            turn_data = {
                t.id: {
                    "actor": t.actor.value,
                    "text": t.summary if t.summary else (t.text[:200] if t.text else None),
                }
                for t in turns
            }

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
                        "message": _extract_message(event, turn_data),
                        "message_actor": _extract_message_actor(event, turn_data),
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
        logger.exception("Failed to fetch events")
        return jsonify({"error": "Failed to fetch events"}), 500


@logging_bp.route("/api/events", methods=["DELETE"])
def clear_events():
    """
    Delete all events.

    Requires X-Confirm-Destructive: true header to prevent accidental calls.

    Returns:
        JSON with count of deleted events
    """
    if request.headers.get("X-Confirm-Destructive") != "true":
        return jsonify({"error": "Destructive operation requires X-Confirm-Destructive header"}), 403

    try:
        count = db.session.query(Event).count()
        db.session.query(Event).delete()
        db.session.commit()
        return jsonify({"deleted": count})
    except Exception as e:
        logger.exception("Failed to clear events")
        db.session.rollback()
        return jsonify({"error": "Failed to clear events"}), 500


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

        # Get agents that have events (ordered by most recently active)
        agents_with_events = (
            db.session.query(
                Agent.id, Agent.session_uuid, Agent.ended_at, Agent.last_seen_at
            )
            .join(Event, Event.agent_id == Agent.id)
            .distinct()
            .order_by(Agent.last_seen_at.desc())
            .all()
        )

        # Determine active status for each agent
        dashboard_config = current_app.config.get("DASHBOARD", {})
        timeout_minutes = dashboard_config.get(
            "active_timeout_minutes", _DEFAULT_ACTIVE_TIMEOUT_MINUTES
        )
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

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
                    {
                        "id": a.id,
                        "session_uuid": str(a.session_uuid),
                        "is_active": a.ended_at is None and a.last_seen_at >= cutoff,
                        "last_seen_at": (
                            a.last_seen_at.isoformat() if a.last_seen_at else None
                        ),
                    }
                    for a in agents_with_events
                ],
                "event_types": [et[0] for et in event_types],
            }
        )

    except Exception as e:
        logger.exception("Failed to fetch event filter options")
        return jsonify({"error": "Failed to fetch filter options"}), 500


def _extract_message(event, turn_data):
    """Extract a display message from turn data or event payload."""
    # Try turn data first
    if event.turn_id and event.turn_id in turn_data:
        return turn_data[event.turn_id]["text"]

    # Fall back to payload text field (e.g. TURN_DETECTED events)
    if event.payload and isinstance(event.payload, dict):
        text = event.payload.get("text")
        if text:
            return text[:200] if len(text) > 200 else text

    return None


def _extract_message_actor(event, turn_data):
    """Extract the actor (user/agent) from turn data or event payload."""
    if event.turn_id and event.turn_id in turn_data:
        return turn_data[event.turn_id]["actor"]

    if event.payload and isinstance(event.payload, dict):
        actor = event.payload.get("actor")
        if actor:
            return actor

    return None


@logging_bp.route("/logging/inference")
def inference_log_page():
    """
    Inference log sub-tab page.

    Returns:
        Rendered inference log template
    """
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("logging_inference.html", status_counts=status_counts)


@logging_bp.route("/api/inference/calls", methods=["GET"])
def get_inference_calls():
    """
    Get paginated inference calls with optional filtering.

    Query parameters:
        - search (optional): Case-insensitive text search across input_text, result_text, purpose
        - level (optional): Filter by inference level
        - model (optional): Filter by model name
        - project_id (optional): Filter by project ID
        - cached (optional): Filter by cached status ("true"/"false")
        - page (optional, default=1): Page number
        - per_page (optional, default=50): Items per page (max 100)

    Returns:
        JSON with paginated inference calls and metadata
    """
    try:
        search = request.args.get("search", type=str)
        level = request.args.get("level", type=str)
        model = request.args.get("model", type=str)
        project_id = request.args.get("project_id", type=int)
        agent_id = request.args.get("agent_id", type=int)
        cached = request.args.get("cached", type=str)
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        if page < 1:
            page = 1
        per_page = max(1, min(per_page, 100))

        query = db.session.query(InferenceCall)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    InferenceCall.input_text.ilike(search_pattern),
                    InferenceCall.result_text.ilike(search_pattern),
                    InferenceCall.purpose.ilike(search_pattern),
                )
            )
        if level:
            query = query.filter(InferenceCall.level == level)
        if model:
            query = query.filter(InferenceCall.model == model)
        if project_id is not None:
            query = query.filter(InferenceCall.project_id == project_id)
        if agent_id is not None:
            query = query.filter(InferenceCall.agent_id == agent_id)
        if cached is not None:
            query = query.filter(InferenceCall.cached == (cached.lower() == "true"))

        total = query.count()
        offset = (page - 1) * per_page

        calls = (
            query.order_by(InferenceCall.timestamp.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        # Resolve project names
        call_project_ids = {c.project_id for c in calls if c.project_id is not None}
        project_names = {}
        if call_project_ids:
            projects = (
                db.session.query(Project.id, Project.name)
                .filter(Project.id.in_(call_project_ids))
                .all()
            )
            project_names = {p.id: p.name for p in projects}

        # Resolve agent session UUIDs
        call_agent_ids = {c.agent_id for c in calls if c.agent_id is not None}
        agent_sessions = {}
        if call_agent_ids:
            agents = (
                db.session.query(Agent.id, Agent.session_uuid)
                .filter(Agent.id.in_(call_agent_ids))
                .all()
            )
            agent_sessions = {a.id: str(a.session_uuid) for a in agents}

        pages = (total + per_page - 1) // per_page if total > 0 else 0

        return jsonify(
            {
                "calls": [
                    {
                        "id": call.id,
                        "timestamp": (
                            call.timestamp.isoformat() if call.timestamp else None
                        ),
                        "level": call.level,
                        "purpose": call.purpose,
                        "model": call.model,
                        "input_tokens": call.input_tokens,
                        "output_tokens": call.output_tokens,
                        "latency_ms": call.latency_ms,
                        "cost": call.cost,
                        "cached": call.cached,
                        "error_message": call.error_message,
                        "input_text": call.input_text,
                        "result_text": call.result_text,
                        "project_id": call.project_id,
                        "project_name": project_names.get(call.project_id),
                        "agent_id": call.agent_id,
                        "agent_session": agent_sessions.get(call.agent_id),
                    }
                    for call in calls
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
        logger.exception("Failed to fetch inference calls")
        return jsonify({"error": "Failed to fetch inference calls"}), 500


@logging_bp.route("/api/inference/calls/filters", methods=["GET"])
def get_inference_call_filters():
    """
    Get available filter options for inference calls.

    Returns:
        JSON with distinct levels, models, and projects that have inference calls
    """
    try:
        levels = (
            db.session.query(InferenceCall.level)
            .distinct()
            .order_by(InferenceCall.level)
            .all()
        )

        models = (
            db.session.query(InferenceCall.model)
            .distinct()
            .order_by(InferenceCall.model)
            .all()
        )

        projects_with_calls = (
            db.session.query(Project.id, Project.name)
            .join(InferenceCall, InferenceCall.project_id == Project.id)
            .distinct()
            .order_by(Project.name)
            .all()
        )

        # Get agents that have inference calls
        dashboard_config = current_app.config.get("DASHBOARD", {})
        timeout_minutes = dashboard_config.get(
            "active_timeout_minutes", _DEFAULT_ACTIVE_TIMEOUT_MINUTES
        )
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        agents_with_calls = (
            db.session.query(
                Agent.id, Agent.session_uuid, Agent.ended_at, Agent.last_seen_at
            )
            .join(InferenceCall, InferenceCall.agent_id == Agent.id)
            .distinct()
            .order_by(Agent.last_seen_at.desc())
            .all()
        )

        return jsonify(
            {
                "levels": [lvl[0] for lvl in levels],
                "models": [m[0] for m in models],
                "projects": [
                    {"id": p.id, "name": p.name} for p in projects_with_calls
                ],
                "agents": [
                    {
                        "id": a.id,
                        "session_uuid": str(a.session_uuid),
                        "is_active": a.ended_at is None and a.last_seen_at is not None and a.last_seen_at >= cutoff,
                    }
                    for a in agents_with_calls
                ],
            }
        )

    except Exception as e:
        logger.exception("Failed to fetch inference filter options")
        return jsonify({"error": "Failed to fetch filter options"}), 500


@logging_bp.route("/api/inference/calls", methods=["DELETE"])
def clear_inference_calls():
    """
    Delete all inference call records.

    Requires X-Confirm-Destructive: true header to prevent accidental calls.

    Returns:
        JSON with count of deleted records
    """
    if request.headers.get("X-Confirm-Destructive") != "true":
        return jsonify({"error": "Destructive operation requires X-Confirm-Destructive header"}), 403

    try:
        count = db.session.query(InferenceCall).count()
        db.session.query(InferenceCall).delete()
        db.session.commit()
        return jsonify({"deleted": count})
    except Exception as e:
        logger.exception("Failed to clear inference calls")
        db.session.rollback()
        return jsonify({"error": "Failed to clear inference calls"}), 500


# ---------------------------------------------------------------------------
# API Call Log endpoints
# ---------------------------------------------------------------------------


@logging_bp.route("/logging/api")
def api_log_page():
    """
    API call log sub-tab page.

    Returns:
        Rendered API log template
    """
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("logging_api.html", status_counts=status_counts)


@logging_bp.route("/api/logging/api-calls", methods=["GET"])
def get_api_calls():
    """
    Get paginated API call logs with optional filtering.

    Query parameters:
        - endpoint_path (optional): Filter by endpoint path
        - http_method (optional): Filter by HTTP method
        - status_category (optional): Filter by status category (2xx/4xx/5xx)
        - auth_status (optional): Filter by auth status
        - search (optional): Text search across request_body and response_body
        - page (optional, default=1): Page number
        - per_page (optional, default=50): Items per page (max 100)

    Returns:
        JSON with paginated API call logs and metadata
    """
    try:
        endpoint_path = request.args.get("endpoint_path", type=str)
        http_method = request.args.get("http_method", type=str)
        status_category = request.args.get("status_category", type=str)
        auth_status = request.args.get("auth_status", type=str)
        search = request.args.get("search", type=str)
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        if page < 1:
            page = 1
        per_page = max(1, min(per_page, 100))

        query = db.session.query(ApiCallLog)

        if endpoint_path:
            query = query.filter(ApiCallLog.endpoint_path == endpoint_path)
        if http_method:
            query = query.filter(ApiCallLog.http_method == http_method)
        if status_category:
            if status_category == "2xx":
                query = query.filter(
                    ApiCallLog.response_status_code >= 200,
                    ApiCallLog.response_status_code < 300,
                )
            elif status_category == "4xx":
                query = query.filter(
                    ApiCallLog.response_status_code >= 400,
                    ApiCallLog.response_status_code < 500,
                )
            elif status_category == "5xx":
                query = query.filter(
                    ApiCallLog.response_status_code >= 500,
                    ApiCallLog.response_status_code < 600,
                )
        if auth_status:
            query = query.filter(ApiCallLog.auth_status == auth_status)
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    ApiCallLog.request_body.ilike(search_pattern),
                    ApiCallLog.response_body.ilike(search_pattern),
                )
            )

        total = query.count()
        offset = (page - 1) * per_page

        calls = (
            query.order_by(ApiCallLog.timestamp.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        # Resolve project names
        call_project_ids = {c.project_id for c in calls if c.project_id is not None}
        project_names = {}
        if call_project_ids:
            projects = (
                db.session.query(Project.id, Project.name)
                .filter(Project.id.in_(call_project_ids))
                .all()
            )
            project_names = {p.id: p.name for p in projects}

        # Resolve agent session UUIDs
        call_agent_ids = {c.agent_id for c in calls if c.agent_id is not None}
        agent_sessions = {}
        if call_agent_ids:
            agents = (
                db.session.query(Agent.id, Agent.session_uuid)
                .filter(Agent.id.in_(call_agent_ids))
                .all()
            )
            agent_sessions = {a.id: str(a.session_uuid) for a in agents}

        pages = (total + per_page - 1) // per_page if total > 0 else 0

        return jsonify(
            {
                "calls": [
                    {
                        "id": call.id,
                        "timestamp": (
                            call.timestamp.isoformat() if call.timestamp else None
                        ),
                        "http_method": call.http_method,
                        "endpoint_path": call.endpoint_path,
                        "query_string": call.query_string,
                        "request_content_type": call.request_content_type,
                        "request_headers": call.request_headers,
                        "request_body": call.request_body,
                        "response_status_code": call.response_status_code,
                        "response_content_type": call.response_content_type,
                        "response_body": call.response_body,
                        "latency_ms": call.latency_ms,
                        "source_ip": call.source_ip,
                        "auth_status": call.auth_status,
                        "project_id": call.project_id,
                        "project_name": project_names.get(call.project_id),
                        "agent_id": call.agent_id,
                        "agent_session": agent_sessions.get(call.agent_id),
                    }
                    for call in calls
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
        logger.exception("Failed to fetch API call logs")
        return jsonify({"error": "Failed to fetch API call logs"}), 500


@logging_bp.route("/api/logging/api-calls/filters", methods=["GET"])
def get_api_call_filters():
    """
    Get available filter options for API call logs.

    Returns:
        JSON with distinct endpoint paths, HTTP methods, status categories,
        and auth statuses from existing records
    """
    try:
        endpoints = (
            db.session.query(ApiCallLog.endpoint_path)
            .distinct()
            .order_by(ApiCallLog.endpoint_path)
            .all()
        )

        methods = (
            db.session.query(ApiCallLog.http_method)
            .distinct()
            .order_by(ApiCallLog.http_method)
            .all()
        )

        auth_statuses = (
            db.session.query(ApiCallLog.auth_status)
            .distinct()
            .order_by(ApiCallLog.auth_status)
            .all()
        )

        # Determine which status categories exist
        status_categories = []
        has_2xx = db.session.query(ApiCallLog.id).filter(
            ApiCallLog.response_status_code >= 200,
            ApiCallLog.response_status_code < 300,
        ).first() is not None
        has_4xx = db.session.query(ApiCallLog.id).filter(
            ApiCallLog.response_status_code >= 400,
            ApiCallLog.response_status_code < 500,
        ).first() is not None
        has_5xx = db.session.query(ApiCallLog.id).filter(
            ApiCallLog.response_status_code >= 500,
            ApiCallLog.response_status_code < 600,
        ).first() is not None

        if has_2xx:
            status_categories.append("2xx")
        if has_4xx:
            status_categories.append("4xx")
        if has_5xx:
            status_categories.append("5xx")

        return jsonify(
            {
                "endpoints": [ep[0] for ep in endpoints],
                "methods": [m[0] for m in methods],
                "status_categories": status_categories,
                "auth_statuses": [a[0] for a in auth_statuses],
            }
        )

    except Exception as e:
        logger.exception("Failed to fetch API call filter options")
        return jsonify({"error": "Failed to fetch filter options"}), 500


@logging_bp.route("/api/logging/api-calls", methods=["DELETE"])
def clear_api_calls():
    """
    Delete all API call log records.

    Requires X-Confirm-Destructive: true header to prevent accidental calls.

    Returns:
        JSON with count of deleted records
    """
    if request.headers.get("X-Confirm-Destructive") != "true":
        return jsonify({"error": "Destructive operation requires X-Confirm-Destructive header"}), 403

    try:
        count = db.session.query(ApiCallLog).count()
        db.session.query(ApiCallLog).delete()
        db.session.commit()
        return jsonify({"deleted": count})
    except Exception as e:
        logger.exception("Failed to clear API call logs")
        db.session.rollback()
        return jsonify({"error": "Failed to clear API call logs"}), 500
