"""Remote agents API endpoints for external application integration.

Provides a completely independent API namespace (/api/remote_agents/) for
creating, monitoring, and shutting down agents from external applications.
Uses session token authentication instead of CSRF tokens.
"""

import logging
from functools import wraps
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request

logger = logging.getLogger(__name__)

remote_agents_bp = Blueprint("remote_agents", __name__)


# ──────────────────────────────────────────────────────────────
# Error envelope helper (Task 2.2.5)
# ──────────────────────────────────────────────────────────────

def _error_response(
    status_code: int,
    error_code: str,
    message: str,
    retryable: bool = False,
    retry_after_seconds: int | None = None,
):
    """Build a standardised JSON error response.

    Returns a nested error envelope matching the cross-system contract (S5 FR5):
    ``{"error": {"code": "...", "message": "...", "status": N, ...}}``

    Args:
        status_code: HTTP status code.
        error_code: Machine-readable error code.
        message: Human-readable error message.
        retryable: Whether the client should retry.
        retry_after_seconds: Optional retry delay hint.

    Returns:
        Flask response tuple (body, status_code).
    """
    body = {
        "error": {
            "code": error_code,
            "message": message,
            "status": status_code,
            "retryable": retryable,
            "retry_after_seconds": retry_after_seconds,
        }
    }
    return jsonify(body), status_code


# ──────────────────────────────────────────────────────────────
# Session token auth decorator (Task 2.2.1)
# ──────────────────────────────────────────────────────────────

def _get_token_from_request() -> str | None:
    """Extract session token from Authorization header or query param."""
    # Check Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # Fallback: query parameter (for embed view iframe)
    return request.args.get("token")


def _get_session_token_service():
    """Get the session token service from app extensions."""
    return current_app.extensions.get("session_token_service")


def require_session_token(f):
    """Decorator that requires a valid session token for the target agent.

    The decorated function receives a `token_info` keyword argument with
    the validated TokenInfo object.

    For routes with an <agent_id> parameter, the token must be scoped to
    that specific agent. For routes without, any valid token is accepted.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token_from_request()
        if not token:
            return _error_response(401, "invalid_session_token", "Session token is required")

        token_service = _get_session_token_service()
        if not token_service:
            return _error_response(503, "service_unavailable", "Token service not available")

        agent_id = kwargs.get("agent_id")
        if agent_id is not None:
            # Validate token is scoped to this specific agent
            token_info = token_service.validate_for_agent(token, agent_id)
        else:
            token_info = token_service.validate(token)

        if not token_info:
            return _error_response(401, "invalid_session_token", "Invalid or expired session token")

        kwargs["token_info"] = token_info
        return f(*args, **kwargs)

    return decorated


# ──────────────────────────────────────────────────────────────
# CORS handling (Task 2.4.2)
# ──────────────────────────────────────────────────────────────

@remote_agents_bp.after_request
def _apply_cors_headers(response):
    """Apply CORS headers based on configured allowed origins."""
    origin = request.headers.get("Origin")
    if not origin:
        return response

    config = current_app.config.get("APP_CONFIG", {})
    remote_config = config.get("remote_agents", {})
    allowed_origins = remote_config.get("allowed_origins", [])

    if origin in allowed_origins or "*" in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Max-Age"] = "3600"

    return response


@remote_agents_bp.route("/api/remote_agents/create", methods=["OPTIONS"])
@remote_agents_bp.route("/api/remote_agents/<int:agent_id>/alive", methods=["OPTIONS"])
@remote_agents_bp.route("/api/remote_agents/<int:agent_id>/shutdown", methods=["OPTIONS"])
def _cors_preflight(**kwargs):
    """Handle CORS preflight requests."""
    return "", 204


# ──────────────────────────────────────────────────────────────
# OpenAPI spec (served as text/plain for browser rendering)
# ──────────────────────────────────────────────────────────────

@remote_agents_bp.route("/api/remote_agents/openapi.yaml", methods=["GET"])
def openapi_spec():
    """Serve the OpenAPI 3.1 spec as plain text."""
    project_root = Path(current_app.root_path).parent.parent
    spec_path = project_root / "static" / "api" / "remote-agents.yaml"
    if not spec_path.exists():
        return _error_response(404, "not_found", "OpenAPI spec not found")
    content = spec_path.read_text(encoding="utf-8")
    return Response(content, mimetype="text/plain")


# ──────────────────────────────────────────────────────────────
# Routes (Tasks 2.2.2 - 2.2.4, 2.3.6)
# ──────────────────────────────────────────────────────────────

@remote_agents_bp.route("/api/remote_agents/create", methods=["POST"])
def create_remote_agent():
    """Create a new remote agent (Task 2.2.2).

    Request body:
        project_slug: Project slug (required, e.g. "may-belle")
        persona_slug: Persona slug (required)
        initial_prompt: First prompt to send (required)
        feature_flags: Optional dict of feature flags

    Returns:
        201: Agent created with agent_id, embed_url, session_token, metadata
        400: Missing required fields
        404: Project or persona not found
        408: Agent creation timeout
        500: Server error
    """
    data = request.get_json(silent=True) or {}

    project_slug = data.get("project_slug", "").strip()
    persona_slug = data.get("persona_slug", "").strip()
    initial_prompt = data.get("initial_prompt", "").strip()
    feature_flags = data.get("feature_flags")

    # Validate required fields
    missing = []
    if not project_slug:
        missing.append("project_slug")
    if not persona_slug:
        missing.append("persona_slug")
    if not initial_prompt:
        missing.append("initial_prompt")

    if missing:
        return _error_response(
            400,
            "missing_fields",
            f"Missing required fields: {', '.join(missing)}",
        )

    # Validate feature_flags if provided
    if feature_flags is not None and not isinstance(feature_flags, dict):
        return _error_response(
            400,
            "invalid_feature_flags",
            "feature_flags must be a JSON object",
        )

    remote_service = current_app.extensions.get("remote_agent_service")
    if not remote_service:
        return _error_response(503, "service_unavailable", "Remote agent service not available")

    try:
        result = remote_service.create_blocking(
            project_slug=project_slug,
            persona_slug=persona_slug,
            initial_prompt=initial_prompt,
            feature_flags=feature_flags,
        )
    except Exception as e:
        logger.exception(f"Remote agent creation failed: {e}")
        return _error_response(500, "server_error", "Internal server error during agent creation")

    if not result.success:
        # Map error codes to HTTP status codes
        status_map = {
            "project_not_found": 404,
            "persona_not_found": 404,
            "agent_creation_timeout": 408,
        }
        status = status_map.get(result.error_code, 500)
        retryable = result.error_code == "agent_creation_timeout"
        return _error_response(
            status,
            result.error_code,
            result.error_message,
            retryable=retryable,
            retry_after_seconds=5 if retryable else None,
        )

    return jsonify({
        "agent_id": result.agent_id,
        "embed_url": result.embed_url,
        "session_token": result.session_token,
        "project_slug": result.project_slug,
        "persona_slug": result.persona_slug,
        "tmux_session_name": result.tmux_session_name,
        "status": result.status,
    }), 201


@remote_agents_bp.route("/api/remote_agents/<int:agent_id>/alive", methods=["GET"])
@require_session_token
def check_alive(agent_id: int, token_info=None):
    """Check if an agent is alive (Task 2.2.3).

    Requires session token scoped to this agent.

    Returns:
        200: Alive status with agent state
        401: Invalid or missing token
    """
    remote_service = current_app.extensions.get("remote_agent_service")
    if not remote_service:
        return _error_response(503, "service_unavailable", "Remote agent service not available")

    result = remote_service.check_alive(agent_id)
    return jsonify(result), 200


@remote_agents_bp.route("/api/remote_agents/<int:agent_id>/shutdown", methods=["POST"])
@require_session_token
def shutdown_remote_agent(agent_id: int, token_info=None):
    """Shut down an agent (Task 2.2.4).

    Requires session token scoped to this agent.  Non-blocking — initiates
    termination and returns immediately.  The tmux session cleanup happens
    asynchronously.

    Response shapes (S5 FR3 contract):
        200: {"status": "ok", "agent_id": N, "message": "Agent shutdown initiated"}
        200: {"status": "ok", "agent_id": N, "message": "Agent already terminated"}
        401: Standard error envelope (invalid_session_token)
        404: Standard error envelope (agent_not_found)
    """
    remote_service = current_app.extensions.get("remote_agent_service")
    if not remote_service:
        return _error_response(503, "service_unavailable", "Remote agent service not available")

    result = remote_service.shutdown(agent_id)

    if result["result"] == "not_found":
        return _error_response(404, "agent_not_found", f"Agent {agent_id} not found")

    if result["result"] == "already_terminated":
        return jsonify({
            "status": "ok",
            "agent_id": agent_id,
            "message": "Agent already terminated",
        }), 200

    return jsonify({
        "status": "ok",
        "agent_id": agent_id,
        "message": "Agent shutdown initiated",
    }), 200


@remote_agents_bp.route("/embed/<int:agent_id>", methods=["GET"])
def embed_view(agent_id: int):
    """Serve the embed chat view for an agent (Task 2.3.6).

    The session token is passed as a URL query parameter. This endpoint
    validates the token and renders the chrome-free chat template.

    Query params:
        token: Session token (required)
        file_upload: Feature flag override (0/1)
        context_usage: Feature flag override (0/1)
        voice_mic: Feature flag override (0/1)
    """
    from flask import render_template

    token = request.args.get("token")
    if not token:
        return _error_response(401, "invalid_session_token", "Session token is required")

    token_service = _get_session_token_service()
    if not token_service:
        return _error_response(503, "service_unavailable", "Token service not available")

    token_info = token_service.validate_for_agent(token, agent_id)
    if not token_info:
        return _error_response(401, "invalid_session_token", "Invalid or expired session token")

    # Resolve feature flags: URL params override token defaults
    config = current_app.config.get("APP_CONFIG", {})
    embed_defaults = config.get("remote_agents", {}).get("embed_defaults", {})

    # Merge: config defaults < token feature_flags < URL params
    feature_flags = {
        "file_upload": embed_defaults.get("file_upload", False),
        "context_usage": embed_defaults.get("context_usage", False),
        "voice_mic": embed_defaults.get("voice_mic", False),
    }
    # Override with token flags
    for key in feature_flags:
        if key in token_info.feature_flags:
            feature_flags[key] = bool(token_info.feature_flags[key])
    # Override with URL params
    for key in feature_flags:
        param = request.args.get(key)
        if param is not None:
            feature_flags[key] = param in ("1", "true", "True")

    # Get application URL for SSE endpoint
    application_url = config.get("server", {}).get(
        "application_url", "https://localhost:5055"
    )

    return render_template(
        "embed/chat.html",
        agent_id=agent_id,
        session_token=token,
        feature_flags=feature_flags,
        application_url=application_url,
    )
