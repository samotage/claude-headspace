"""Channels API endpoints for inter-agent communication.

Provides REST endpoints for channel CRUD, membership management, and messaging.
All business logic is delegated to ChannelService -- route handlers are thin
wrappers that handle request parsing, auth resolution, and response formatting.

Supports dual authentication:
- Flask session cookie (dashboard/operator)
- Authorization: Bearer <token> (remote agents/embed widgets)
"""

import logging
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from ..database import db
from ..services.channel_service import (
    AgentChannelConflictError,
    AlreadyMemberError,
    ChannelClosedError,
    ChannelError,
    ChannelNotFoundError,
    ContentTooLongError,
    NoCreationCapabilityError,
    NotAMemberError,
    NotChairError,
    PersonaNotFoundError,
)

logger = logging.getLogger(__name__)

channels_api_bp = Blueprint("channels_api", __name__)


# ──────────────────────────────────────────────────────────────
# Error envelope helper
# ──────────────────────────────────────────────────────────────


def _error_response(status_code: int, error_code: str, message: str):
    """Build a standardised JSON error response.

    Returns a nested error envelope:
    ``{"error": {"code": "...", "message": "...", "status": N}}``
    """
    body = {
        "error": {
            "code": error_code,
            "message": message,
            "status": status_code,
        }
    }
    return jsonify(body), status_code


# ──────────────────────────────────────────────────────────────
# Exception-to-HTTP mapping
# ──────────────────────────────────────────────────────────────

_ERROR_MAP = {
    ChannelNotFoundError: (404, "channel_not_found"),
    NotAMemberError: (403, "not_a_member"),
    NotChairError: (403, "not_chair"),
    ChannelClosedError: (409, "channel_not_active"),
    AlreadyMemberError: (409, "already_a_member"),
    NoCreationCapabilityError: (403, "no_creation_capability"),
    AgentChannelConflictError: (409, "agent_already_in_channel"),
    PersonaNotFoundError: (404, "persona_not_found"),
    ContentTooLongError: (413, "content_too_long"),
}


def _handle_service_error(e):
    """Map ChannelService exceptions to HTTP error responses."""
    for exc_type, (status, code) in _ERROR_MAP.items():
        if isinstance(e, exc_type):
            return _error_response(status, code, str(e))

    # Unknown ChannelError -- treat as 500
    logger.exception(f"Unexpected channel error: {e}")
    return _error_response(500, "server_error", "Internal server error")


# ──────────────────────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────────────────────


class AuthError(Exception):
    """Raised when caller authentication fails."""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


def _get_token_from_request() -> str | None:
    """Extract session token from Authorization header or query param."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.args.get("token")


def _resolve_caller():
    """Resolve the calling persona from session cookie or Bearer token.

    Returns (persona, agent) tuple. persona is always set;
    agent is set for token-authenticated callers, None for dashboard session.

    Raises:
        AuthError: If neither auth mechanism provides a valid identity.
    """
    from ..models.agent import Agent
    from ..models.persona import Persona

    # Check Bearer token first
    token = _get_token_from_request()
    if token:
        token_service = current_app.extensions.get("session_token_service")
        if token_service:
            token_info = token_service.validate(token)
            if token_info:
                agent = db.session.get(Agent, token_info.agent_id)
                if agent and agent.persona:
                    return agent.persona, agent
        raise AuthError("invalid_session_token", "Invalid or expired session token")

    # Fallback: dashboard session (operator)
    operator = Persona.get_operator()
    if operator:
        return operator, None

    raise AuthError("unauthorized", "Authentication required")


def _get_channel_service():
    """Get the ChannelService from app extensions, or None."""
    return current_app.extensions.get("channel_service")


# ──────────────────────────────────────────────────────────────
# Route decorator: auth + service resolution + error handling
# ──────────────────────────────────────────────────────────────


def _channel_route(f):
    """Decorator that handles auth, service lookup, and exception mapping.

    Injects ``persona``, ``agent``, and ``service`` as keyword arguments
    into the wrapped view function.  Catches AuthError and ChannelError
    and returns the appropriate JSON error envelope.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            persona, agent = _resolve_caller()
        except AuthError as e:
            return _error_response(401, e.error_code, e.message)

        service = _get_channel_service()
        if not service:
            return _error_response(
                503, "service_unavailable", "Channel service not available"
            )

        kwargs["persona"] = persona
        kwargs["agent"] = agent
        kwargs["service"] = service

        try:
            return f(*args, **kwargs)
        except ChannelError as e:
            return _handle_service_error(e)
        except ValueError as e:
            return _error_response(400, "invalid_field", str(e))
        except Exception as e:
            logger.exception(f"Unexpected error in {f.__name__}: {e}")
            return _error_response(500, "server_error", "Internal server error")

    return decorated


# ──────────────────────────────────────────────────────────────
# Response serializers
# ──────────────────────────────────────────────────────────────


def _channel_to_dict(channel) -> dict:
    """Serialize a Channel to a JSON-safe dict.

    Uses the channel's loaded relationships (memberships) to compute
    member count and chair persona slug without additional DB queries.
    """
    # Use loaded relationship if available, else empty
    memberships = getattr(channel, "memberships", None) or []

    member_count = sum(1 for m in memberships if m.status in ("active", "muted"))

    chair_persona_slug = None
    for m in memberships:
        if m.is_chair and m.persona:
            chair_persona_slug = m.persona.slug
            break

    return {
        "id": channel.id,
        "slug": channel.slug,
        "name": channel.name,
        "channel_type": channel.channel_type.value,
        "status": channel.status,
        "description": channel.description,
        "intent_override": channel.intent_override,
        "organisation_id": channel.organisation_id,
        "project_id": channel.project_id,
        "chair_persona_slug": chair_persona_slug,
        "member_count": member_count,
        "created_at": channel.created_at.isoformat() if channel.created_at else None,
        "completed_at": channel.completed_at.isoformat()
        if channel.completed_at
        else None,
        "archived_at": channel.archived_at.isoformat() if channel.archived_at else None,
    }


def _membership_to_dict(membership) -> dict:
    """Serialize a ChannelMembership to a JSON-safe dict."""
    return {
        "id": membership.id,
        "persona_slug": membership.persona.slug if membership.persona else None,
        "persona_name": membership.persona.name if membership.persona else None,
        "agent_id": membership.agent_id,
        "is_chair": membership.is_chair,
        "status": membership.status,
        "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
        "left_at": membership.left_at.isoformat() if membership.left_at else None,
    }


def _message_to_dict(message, channel_slug: str) -> dict:
    """Serialize a Message to a JSON-safe dict."""
    return {
        "id": message.id,
        "channel_slug": channel_slug,
        "persona_slug": message.persona.slug if message.persona else None,
        "persona_name": message.persona.name if message.persona else None,
        "agent_id": message.agent_id,
        "content": message.content,
        "message_type": message.message_type.value,
        "metadata": message.metadata_,
        "attachment_path": message.attachment_path,
        "source_turn_id": message.source_turn_id,
        "source_command_id": message.source_command_id,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
    }


# ──────────────────────────────────────────────────────────────
# Channel Endpoints
# ──────────────────────────────────────────────────────────────


@channels_api_bp.route("/api/channels", methods=["POST"])
@_channel_route
def create_channel(*, persona, agent, service):
    """Create a new channel (FR1)."""
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip() if isinstance(data.get("name"), str) else ""
    channel_type = (
        data.get("channel_type", "").strip()
        if isinstance(data.get("channel_type"), str)
        else ""
    )

    missing = []
    if not name:
        missing.append("name")
    if not channel_type:
        missing.append("channel_type")

    if missing:
        return _error_response(
            400, "missing_fields", f"Missing required fields: {', '.join(missing)}"
        )

    # Validate channel_type
    from ..models.channel import ChannelType

    try:
        ChannelType(channel_type)
    except ValueError:
        valid_types = [ct.value for ct in ChannelType]
        return _error_response(
            400,
            "invalid_field",
            f"Invalid channel_type '{channel_type}'. Must be one of: {', '.join(valid_types)}",
        )

    channel = service.create_channel(
        creator_persona=persona,
        name=name,
        channel_type=channel_type,
        description=data.get("description"),
        intent_override=data.get("intent_override"),
        member_slugs=data.get("members"),
    )

    return jsonify(_channel_to_dict(channel)), 201


@channels_api_bp.route("/api/channels", methods=["GET"])
@_channel_route
def list_channels(*, persona, agent, service):
    """List channels for the calling persona (FR2)."""
    status_filter = request.args.get("status")
    type_filter = request.args.get("type")
    all_flag = request.args.get("all", "").lower() == "true"

    # Only operator can use ?all=true -- silent fallback for non-operators
    from ..models.persona import Persona

    if all_flag:
        operator = Persona.get_operator()
        if not operator or operator.id != persona.id:
            all_flag = False

    channels = service.list_channels(
        persona=persona,
        status=status_filter,
        channel_type=type_filter,
        all_visible=all_flag,
    )

    return jsonify([_channel_to_dict(ch) for ch in channels]), 200


@channels_api_bp.route("/api/channels/<slug>", methods=["GET"])
@_channel_route
def get_channel(slug: str, *, persona, agent, service):
    """Get channel detail (FR3).

    No membership check — any authenticated caller can view channel
    metadata. This is intentional: it supports observer/supervisor
    patterns where operators or monitoring tools inspect channels
    without being members.
    """
    channel = service.get_channel(slug)
    return jsonify(_channel_to_dict(channel)), 200


@channels_api_bp.route("/api/channels/<slug>", methods=["PATCH"])
@_channel_route
def update_channel(slug: str, *, persona, agent, service):
    """Update channel fields (FR4)."""
    data = request.get_json(silent=True) or {}

    channel = service.update_channel(
        slug=slug,
        persona=persona,
        description=data.get("description"),
        intent_override=data.get("intent_override"),
    )

    return jsonify(_channel_to_dict(channel)), 200


@channels_api_bp.route("/api/channels/<slug>/complete", methods=["POST"])
@_channel_route
def complete_channel(slug: str, *, persona, agent, service):
    """Complete a channel (FR5)."""
    channel = service.complete_channel(slug=slug, persona=persona)
    return jsonify(_channel_to_dict(channel)), 200


@channels_api_bp.route("/api/channels/<slug>/archive", methods=["POST"])
@_channel_route
def archive_channel(slug: str, *, persona, agent, service):
    """Archive a channel (FR5a)."""
    channel = service.archive_channel(slug=slug, persona=persona)
    return jsonify(_channel_to_dict(channel)), 200


# ──────────────────────────────────────────────────────────────
# Membership Endpoints
# ──────────────────────────────────────────────────────────────


@channels_api_bp.route("/api/channels/<slug>/members", methods=["GET"])
@_channel_route
def list_members(slug: str, *, persona, agent, service):
    """List channel members (FR6).

    No membership check — any authenticated caller can view a
    channel's member list. This supports observer/supervisor patterns
    (e.g. operator reviewing composition, monitoring service auditing).
    """
    members = service.list_members(slug)
    return jsonify([_membership_to_dict(m) for m in members]), 200


@channels_api_bp.route("/api/channels/<slug>/members", methods=["POST"])
@_channel_route
def add_member(slug: str, *, persona, agent, service):
    """Add a member to a channel (FR7)."""
    data = request.get_json(silent=True) or {}
    persona_slug = (
        data.get("persona_slug", "").strip()
        if isinstance(data.get("persona_slug"), str)
        else ""
    )

    if not persona_slug:
        return _error_response(
            400, "missing_fields", "Missing required field: persona_slug"
        )

    membership = service.add_member(
        slug=slug,
        persona_slug=persona_slug,
        caller_persona=persona,
    )

    return jsonify(_membership_to_dict(membership)), 201


@channels_api_bp.route("/api/channels/<slug>/leave", methods=["POST"])
@_channel_route
def leave_channel(slug: str, *, persona, agent, service):
    """Leave a channel (FR8)."""
    service.leave_channel(slug=slug, persona=persona)
    return jsonify({"status": "ok", "message": "Left channel"}), 200


@channels_api_bp.route("/api/channels/<slug>/mute", methods=["POST"])
@_channel_route
def mute_channel(slug: str, *, persona, agent, service):
    """Mute a channel (FR9)."""
    service.mute_channel(slug=slug, persona=persona)
    return jsonify({"status": "ok", "message": "Channel muted"}), 200


@channels_api_bp.route("/api/channels/<slug>/unmute", methods=["POST"])
@_channel_route
def unmute_channel(slug: str, *, persona, agent, service):
    """Unmute a channel (FR10)."""
    service.unmute_channel(slug=slug, persona=persona)
    return jsonify({"status": "ok", "message": "Channel unmuted"}), 200


@channels_api_bp.route("/api/channels/<slug>/transfer-chair", methods=["POST"])
@_channel_route
def transfer_chair(slug: str, *, persona, agent, service):
    """Transfer chair role (FR11)."""
    data = request.get_json(silent=True) or {}
    target_slug = (
        data.get("persona_slug", "").strip()
        if isinstance(data.get("persona_slug"), str)
        else ""
    )

    if not target_slug:
        return _error_response(
            400, "missing_fields", "Missing required field: persona_slug"
        )

    service.transfer_chair(
        slug=slug,
        target_persona_slug=target_slug,
        caller_persona=persona,
    )

    return jsonify({"status": "ok", "message": "Chair transferred"}), 200


# ──────────────────────────────────────────────────────────────
# Message Endpoints
# ──────────────────────────────────────────────────────────────


@channels_api_bp.route("/api/channels/<slug>/messages", methods=["GET"])
@_channel_route
def get_messages(slug: str, *, persona, agent, service):
    """Get message history with cursor pagination (FR12)."""
    # Parse pagination params
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except (ValueError, TypeError):
        limit = 50

    since = request.args.get("since")
    before = request.args.get("before")

    messages = service.get_history(
        slug=slug,
        persona=persona,
        limit=limit,
        since=since,
        before=before,
    )

    return jsonify([_message_to_dict(m, slug) for m in messages]), 200


@channels_api_bp.route("/api/channels/<slug>/messages", methods=["POST"])
@_channel_route
def send_message(slug: str, *, persona, agent, service):
    """Send a message to a channel (FR13)."""
    data = request.get_json(silent=True) or {}

    content = (
        data.get("content", "").strip() if isinstance(data.get("content"), str) else ""
    )
    if not content:
        return _error_response(400, "missing_fields", "Missing required field: content")

    # Early content length check (service also validates, but fail fast at API layer)
    max_len = (
        current_app.config.get("APP_CONFIG", {})
        .get("channels", {})
        .get("max_message_content_length", 50000)
    )
    if len(content) > max_len:
        return _error_response(
            413,
            "content_too_long",
            f"Message content exceeds maximum length "
            f"({len(content):,} > {max_len:,} characters).",
        )

    message_type = data.get("message_type", "message")
    if message_type == "system":
        return _error_response(
            400,
            "invalid_message_type",
            "The 'system' message type is service-generated only and cannot be sent via the API",
        )

    # Validate message_type
    valid_types = ["message", "delegation", "escalation"]
    if message_type not in valid_types:
        return _error_response(
            400,
            "invalid_message_type",
            f"Invalid message_type '{message_type}'. Must be one of: {', '.join(valid_types)}",
        )

    # Validate attachment_path
    attachment_path = data.get("attachment_path")
    if attachment_path is not None:
        if not isinstance(attachment_path, str):
            return _error_response(
                400, "invalid_field", "attachment_path must be a string."
            )
        if ".." in attachment_path:
            return _error_response(
                400,
                "invalid_field",
                "Invalid attachment_path: path traversal ('..') is not allowed.",
            )
        if attachment_path.startswith("/") or attachment_path.startswith("\\"):
            return _error_response(
                400,
                "invalid_field",
                "Invalid attachment_path: absolute paths are not allowed.",
            )
        if any(c < " " or c == "\x7f" for c in attachment_path):
            return _error_response(
                400,
                "invalid_field",
                "Invalid attachment_path: control characters are not allowed.",
            )

    message = service.send_message(
        slug=slug,
        content=content,
        persona=persona,
        agent=agent,
        message_type=message_type,
        attachment_path=attachment_path,
    )

    return jsonify(_message_to_dict(message, slug)), 201
