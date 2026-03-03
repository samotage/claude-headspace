"""Channels API endpoints for inter-agent communication.

Provides REST endpoints for channel CRUD, membership management, and messaging.
All business logic is delegated to ChannelService -- route handlers are thin
wrappers that handle request parsing, auth resolution, and response formatting.

Supports dual authentication:
- Flask session cookie (dashboard/operator)
- Authorization: Bearer <token> (remote agents/embed widgets)
"""

import logging

from flask import Blueprint, current_app, jsonify, request

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
                agent = Agent.query.get(token_info.agent_id)
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
# Response serializers
# ──────────────────────────────────────────────────────────────

def _channel_to_dict(channel) -> dict:
    """Serialize a Channel to a JSON-safe dict.

    Uses the channel's loaded relationships (memberships) to compute
    member count and chair persona slug without additional DB queries.
    """
    # Use loaded relationship if available, else empty
    memberships = getattr(channel, "memberships", None) or []

    member_count = sum(
        1 for m in memberships if m.status in ("active", "muted")
    )

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
        "completed_at": channel.completed_at.isoformat() if channel.completed_at else None,
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
# Exception-to-HTTP mapping
# ──────────────────────────────────────────────────────────────

def _handle_service_error(e):
    """Map ChannelService exceptions to HTTP error responses."""
    from ..services.channel_service import (
        AgentChannelConflictError,
        AlreadyMemberError,
        ChannelClosedError,
        ChannelNotFoundError,
        NoCreationCapabilityError,
        NotAMemberError,
        NotChairError,
    )

    error_map = {
        ChannelNotFoundError: (404, "channel_not_found"),
        NotAMemberError: (403, "not_a_member"),
        NotChairError: (403, "not_chair"),
        ChannelClosedError: (409, "channel_not_active"),
        AlreadyMemberError: (409, "already_a_member"),
        NoCreationCapabilityError: (403, "no_creation_capability"),
        AgentChannelConflictError: (409, "agent_already_in_channel"),
    }

    for exc_type, (status, code) in error_map.items():
        if isinstance(e, exc_type):
            return _error_response(status, code, str(e))

    # Unknown ChannelError -- treat as 500
    logger.exception(f"Unexpected channel error: {e}")
    return _error_response(500, "server_error", "Internal server error")


# ──────────────────────────────────────────────────────────────
# Channel Endpoints
# ──────────────────────────────────────────────────────────────

@channels_api_bp.route("/api/channels", methods=["POST"])
def create_channel():
    """Create a new channel (FR1)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip() if isinstance(data.get("name"), str) else ""
    channel_type = data.get("channel_type", "").strip() if isinstance(data.get("channel_type"), str) else ""

    missing = []
    if not name:
        missing.append("name")
    if not channel_type:
        missing.append("channel_type")

    if missing:
        return _error_response(400, "missing_fields", f"Missing required fields: {', '.join(missing)}")

    # Validate channel_type
    from ..models.channel import ChannelType
    try:
        ChannelType(channel_type)
    except ValueError:
        valid_types = [ct.value for ct in ChannelType]
        return _error_response(
            400, "invalid_field",
            f"Invalid channel_type '{channel_type}'. Must be one of: {', '.join(valid_types)}"
        )

    description = data.get("description")
    intent_override = data.get("intent_override")
    member_slugs = data.get("members")

    try:
        channel = service.create_channel(
            creator_persona=persona,
            name=name,
            channel_type=channel_type,
            description=description,
            intent_override=intent_override,
            member_slugs=member_slugs,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Channel creation failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_channel_to_dict(channel)), 201


@channels_api_bp.route("/api/channels", methods=["GET"])
def list_channels():
    """List channels for the calling persona (FR2)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    status_filter = request.args.get("status")
    type_filter = request.args.get("type")
    all_flag = request.args.get("all", "").lower() == "true"

    # Only operator can use ?all=true -- silent fallback for non-operators
    from ..models.persona import Persona
    if all_flag:
        operator = Persona.get_operator()
        if not operator or operator.id != persona.id:
            all_flag = False

    try:
        channels = service.list_channels(
            persona=persona,
            status=status_filter,
            channel_type=type_filter,
            all_visible=all_flag,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Channel listing failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify([_channel_to_dict(ch) for ch in channels]), 200


@channels_api_bp.route("/api/channels/<slug>", methods=["GET"])
def get_channel(slug: str):
    """Get channel detail (FR3)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        channel = service.get_channel(slug)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Channel detail failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_channel_to_dict(channel)), 200


@channels_api_bp.route("/api/channels/<slug>", methods=["PATCH"])
def update_channel(slug: str):
    """Update channel fields (FR4)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    data = request.get_json(silent=True) or {}
    description = data.get("description")
    intent_override = data.get("intent_override")

    try:
        channel = service.update_channel(
            slug=slug,
            persona=persona,
            description=description,
            intent_override=intent_override,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Channel update failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_channel_to_dict(channel)), 200


@channels_api_bp.route("/api/channels/<slug>/complete", methods=["POST"])
def complete_channel(slug: str):
    """Complete a channel (FR5)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        channel = service.complete_channel(slug=slug, persona=persona)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Channel complete failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_channel_to_dict(channel)), 200


@channels_api_bp.route("/api/channels/<slug>/archive", methods=["POST"])
def archive_channel(slug: str):
    """Archive a channel (FR5a)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        channel = service.archive_channel(slug=slug, persona=persona)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Channel archive failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_channel_to_dict(channel)), 200


# ──────────────────────────────────────────────────────────────
# Membership Endpoints
# ──────────────────────────────────────────────────────────────

@channels_api_bp.route("/api/channels/<slug>/members", methods=["GET"])
def list_members(slug: str):
    """List channel members (FR6)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        members = service.list_members(slug)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Member listing failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify([_membership_to_dict(m) for m in members]), 200


@channels_api_bp.route("/api/channels/<slug>/members", methods=["POST"])
def add_member(slug: str):
    """Add a member to a channel (FR7)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    data = request.get_json(silent=True) or {}
    persona_slug = data.get("persona_slug", "").strip() if isinstance(data.get("persona_slug"), str) else ""

    if not persona_slug:
        return _error_response(400, "missing_fields", "Missing required field: persona_slug")

    try:
        membership = service.add_member(
            slug=slug,
            persona_slug=persona_slug,
            caller_persona=persona,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Add member failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_membership_to_dict(membership)), 201


@channels_api_bp.route("/api/channels/<slug>/leave", methods=["POST"])
def leave_channel(slug: str):
    """Leave a channel (FR8)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        service.leave_channel(slug=slug, persona=persona)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Leave channel failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify({"status": "ok", "message": "Left channel"}), 200


@channels_api_bp.route("/api/channels/<slug>/mute", methods=["POST"])
def mute_channel(slug: str):
    """Mute a channel (FR9)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        service.mute_channel(slug=slug, persona=persona)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Mute channel failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify({"status": "ok", "message": "Channel muted"}), 200


@channels_api_bp.route("/api/channels/<slug>/unmute", methods=["POST"])
def unmute_channel(slug: str):
    """Unmute a channel (FR10)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    try:
        service.unmute_channel(slug=slug, persona=persona)
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Unmute channel failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify({"status": "ok", "message": "Channel unmuted"}), 200


@channels_api_bp.route("/api/channels/<slug>/transfer-chair", methods=["POST"])
def transfer_chair(slug: str):
    """Transfer chair role (FR11)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    data = request.get_json(silent=True) or {}
    target_slug = data.get("persona_slug", "").strip() if isinstance(data.get("persona_slug"), str) else ""

    if not target_slug:
        return _error_response(400, "missing_fields", "Missing required field: persona_slug")

    try:
        service.transfer_chair(
            slug=slug,
            target_persona_slug=target_slug,
            caller_persona=persona,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Transfer chair failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify({"status": "ok", "message": "Chair transferred"}), 200


# ──────────────────────────────────────────────────────────────
# Message Endpoints
# ──────────────────────────────────────────────────────────────

@channels_api_bp.route("/api/channels/<slug>/messages", methods=["GET"])
def get_messages(slug: str):
    """Get message history with cursor pagination (FR12)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    # Parse pagination params
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except (ValueError, TypeError):
        limit = 50

    since = request.args.get("since")
    before = request.args.get("before")

    try:
        messages = service.get_history(
            slug=slug,
            persona=persona,
            limit=limit,
            since=since,
            before=before,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        logger.exception(f"Get messages failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify([_message_to_dict(m, slug) for m in messages]), 200


@channels_api_bp.route("/api/channels/<slug>/messages", methods=["POST"])
def send_message(slug: str):
    """Send a message to a channel (FR13)."""
    try:
        persona, agent = _resolve_caller()
    except AuthError as e:
        return _error_response(401, e.error_code, e.message)

    service = _get_channel_service()
    if not service:
        return _error_response(503, "service_unavailable", "Channel service not available")

    data = request.get_json(silent=True) or {}

    content = data.get("content", "").strip() if isinstance(data.get("content"), str) else ""
    if not content:
        return _error_response(400, "missing_fields", "Missing required field: content")

    message_type = data.get("message_type", "message")
    if message_type == "system":
        return _error_response(
            400, "invalid_message_type",
            "The 'system' message type is service-generated only and cannot be sent via the API"
        )

    # Validate message_type
    valid_types = ["message", "delegation", "escalation"]
    if message_type not in valid_types:
        return _error_response(
            400, "invalid_message_type",
            f"Invalid message_type '{message_type}'. Must be one of: {', '.join(valid_types)}"
        )

    attachment_path = data.get("attachment_path")

    try:
        message = service.send_message(
            slug=slug,
            content=content,
            persona=persona,
            agent=agent,
            message_type=message_type,
            attachment_path=attachment_path,
        )
    except Exception as e:
        from ..services.channel_service import ChannelError
        if isinstance(e, ChannelError):
            return _handle_service_error(e)
        if isinstance(e, ValueError):
            return _error_response(400, "invalid_message_type", str(e))
        logger.exception(f"Send message failed: {e}")
        return _error_response(500, "server_error", "Internal server error")

    return jsonify(_message_to_dict(message, slug)), 201
