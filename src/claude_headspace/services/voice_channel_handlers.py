"""Voice channel action handlers. Uses Flask + DB."""

import logging

from flask import current_app, jsonify

from ..database import db
from ..models.agent import Agent
from ..models.channel import Channel
from ..models.persona import Persona
from ..services.channel_service import ChannelError
from .voice_channel_helpers import (
    _get_auth_id,
    _match_persona_for_channel,
    _resolve_channel_ref,
    _set_channel_context,
)
from .voice_matchers import _match_channel

logger = logging.getLogger(__name__)


def _voice_channel_error(error_type: str, suggestion: str, status_code: int = 400):
    """Build a voice-friendly error response for channel handlers.

    Local error helper to avoid circular import with route's _voice_error.
    """
    formatter = current_app.extensions.get("voice_formatter")
    if formatter:
        body = {"voice": formatter.format_error(error_type, suggestion)}
    else:
        body = {
            "voice": {
                "status_line": error_type,
                "results": [],
                "next_action": suggestion,
            }
        }
    body["error"] = error_type
    return jsonify(body), status_code


def _resolve_and_match_channel(channel_ref: str, auth_id: str) -> tuple:
    """Resolve a channel reference and fuzzy-match it against active channels.

    Combines the common resolve -> query -> match pipeline used by most
    channel handlers.

    Returns:
        (channel, None) on success
        (None, (response, status_code)) on error (no_match / ambiguous / bad ref)
    """
    try:
        resolved_ref = _resolve_channel_ref(channel_ref, auth_id)
    except ValueError as e:
        return None, _voice_channel_error(str(e), "Specify the channel name.", 400)

    channels = Channel.query.filter(Channel.status.in_(["pending", "active"])).all()
    result = _match_channel(resolved_ref, channels)

    if "no_match" in result:
        return None, _voice_channel_error(
            f"No channel found matching '{channel_ref}'.",
            "Check channel names or say 'list channels'.",
            404,
        )
    if "ambiguous" in result:
        slugs = [f"#{ch.slug}" for ch in result["ambiguous"]]
        voice = {
            "status_line": f"Multiple channels match '{channel_ref}'.",
            "results": slugs,
            "next_action": "Say the full channel name.",
        }
        return None, (jsonify({"voice": voice}), 409)

    return result["match"], None


def _handle_channel_intent(intent: dict, text: str, formatter) -> tuple:
    """Route a channel-targeted voice command to ChannelService."""
    channel_service = current_app.extensions.get("channel_service")
    if not channel_service:
        return _voice_channel_error(
            "Channels not available.", "Channel service not configured.", 503
        )

    # Resolve the operator's Persona
    operator_persona = Persona.get_operator()
    if not operator_persona:
        return _voice_channel_error(
            "Operator identity not configured.",
            "Register an operator persona first.",
            503,
        )

    action = intent["action"]
    auth_id = _get_auth_id()

    if action == "send":
        return _handle_channel_send(
            intent, channel_service, formatter, auth_id, operator_persona
        )
    elif action == "history":
        return _handle_channel_history(
            intent, channel_service, formatter, auth_id, operator_persona
        )
    elif action == "list":
        return _handle_channel_list(channel_service, operator_persona, formatter)
    elif action == "create":
        return _handle_channel_create(
            intent, channel_service, formatter, auth_id, operator_persona
        )
    elif action == "add_member":
        return _handle_channel_add_member(
            intent, channel_service, formatter, auth_id, operator_persona
        )
    elif action == "complete":
        return _handle_channel_complete(
            intent, channel_service, formatter, auth_id, operator_persona
        )
    else:
        return _voice_channel_error(
            "Unknown channel action.",
            "Try 'send to [channel]: [message]'.",
            400,
        )


def _handle_channel_send(intent, channel_service, formatter, auth_id, operator_persona):
    """Handle sending a message to a channel."""
    channel_ref = intent.get("channel_ref", "")
    content = intent.get("content", "")

    channel, err = _resolve_and_match_channel(channel_ref, auth_id)
    if err:
        return err

    try:
        channel_service.send_message(
            slug=channel.slug,
            content=content,
            persona=operator_persona,
        )
    except ChannelError as e:
        return _voice_channel_error(str(e), "Check channel status.", 400)

    _set_channel_context(auth_id, channel.slug)
    voice = formatter.format_channel_message_sent(channel.slug)
    return jsonify({"voice": voice}), 200


def _handle_channel_history(
    intent, channel_service, formatter, auth_id, operator_persona
):
    """Handle channel history retrieval."""
    channel_ref = intent.get("channel_ref", "")

    channel, err = _resolve_and_match_channel(channel_ref, auth_id)
    if err:
        return err

    try:
        messages = channel_service.get_history(
            slug=channel.slug,
            persona=operator_persona,
            limit=10,
        )
    except ChannelError as e:
        return _voice_channel_error(str(e), "Check channel membership.", 400)

    message_dicts = [
        {
            "persona_name": msg.persona.name if msg.persona else "Unknown",
            "content": msg.content or "",
        }
        for msg in messages
    ]

    _set_channel_context(auth_id, channel.slug)
    voice = formatter.format_channel_history(channel.slug, message_dicts)
    return jsonify({"voice": voice}), 200


def _handle_channel_list(channel_service, operator_persona, formatter):
    """Handle listing channels visible to the operator."""
    try:
        channels = channel_service.list_channels(
            persona=operator_persona,
            all_visible=True,
        )
    except ChannelError as e:
        return _voice_channel_error(str(e), "Check operator persona.", 400)

    # Filter to pending/active only
    active_channels = [ch for ch in channels if ch.status in ("pending", "active")]

    channel_dicts = [
        {
            "slug": ch.slug,
            "channel_type": ch.channel_type.value,
            "status": ch.status,
        }
        for ch in active_channels
    ]

    voice = formatter.format_channel_list(channel_dicts)
    return jsonify({"voice": voice}), 200


def _handle_channel_create(
    intent, channel_service, formatter, auth_id, operator_persona
):
    """Handle channel creation via voice."""
    name = intent.get("name", "")
    channel_type = intent.get("channel_type", "workshop")
    member_refs = intent.get("member_refs", [])

    try:
        channel = channel_service.create_channel(
            creator_persona=operator_persona,
            name=name,
            channel_type=channel_type,
        )
    except ChannelError as e:
        return _voice_channel_error(str(e), "Check channel creation permissions.", 400)

    # Add members if specified
    member_results = []
    for ref in member_refs:
        persona_result = _match_persona_for_channel(ref)
        if "match" in persona_result:
            persona = persona_result["match"]
            try:
                channel_service.add_member(
                    slug=channel.slug,
                    persona_slug=persona.slug,
                    caller_persona=operator_persona,
                )
                # Check if agent is spinning up
                agent = (
                    db.session.query(Agent)
                    .filter_by(persona_id=persona.id, ended_at=None)
                    .first()
                )
                spinning_up = agent is None
                if spinning_up:
                    member_results.append(f"{persona.name} -- agent spinning up.")
                else:
                    member_results.append(f"{persona.name} joined.")
            except ChannelError as e:
                member_results.append(f"{persona.name}: {e}")
        elif "ambiguous" in persona_result:
            names = [p.name for p in persona_result["ambiguous"]]
            member_results.append(f"'{ref}' is ambiguous: {', '.join(names)}")
        else:
            member_results.append(f"'{ref}' not found.")

    _set_channel_context(auth_id, channel.slug)
    voice = formatter.format_channel_created(channel.slug, channel_type, member_results)
    return jsonify({"voice": voice}), 200


def _handle_channel_add_member(
    intent, channel_service, formatter, auth_id, operator_persona
):
    """Handle adding a member to a channel."""
    member_ref = intent.get("member_ref", "")
    channel_ref = intent.get("channel_ref", "")

    # Resolve persona
    persona_result = _match_persona_for_channel(member_ref)
    if "no_match" in persona_result:
        return _voice_channel_error(
            f"No persona found matching '{member_ref}'.",
            "Check persona names or say 'list personas'.",
            404,
        )
    if "ambiguous" in persona_result:
        names = [p.name for p in persona_result["ambiguous"]]
        voice = {
            "status_line": f"Multiple personas match '{member_ref}'.",
            "results": names,
            "next_action": "Say the full persona name.",
        }
        return jsonify({"voice": voice}), 409

    persona = persona_result["match"]

    # Resolve channel
    channel, err = _resolve_and_match_channel(channel_ref, auth_id)
    if err:
        return err
    try:
        channel_service.add_member(
            slug=channel.slug,
            persona_slug=persona.slug,
            caller_persona=operator_persona,
        )
    except ChannelError as e:
        return _voice_channel_error(str(e), "Check membership requirements.", 400)

    # Check if agent is spinning up
    agent = (
        db.session.query(Agent).filter_by(persona_id=persona.id, ended_at=None).first()
    )
    spinning_up = agent is None

    _set_channel_context(auth_id, channel.slug)
    voice = formatter.format_channel_member_added(
        persona.name, channel.slug, spinning_up
    )
    return jsonify({"voice": voice}), 200


def _handle_channel_complete(
    intent, channel_service, formatter, auth_id, operator_persona
):
    """Handle channel completion."""
    channel_ref = intent.get("channel_ref", "")

    channel, err = _resolve_and_match_channel(channel_ref, auth_id)
    if err:
        return err

    try:
        channel_service.complete_channel(
            slug=channel.slug,
            persona=operator_persona,
        )
    except ChannelError as e:
        return _voice_channel_error(str(e), "Check channel status.", 400)

    _set_channel_context(auth_id, channel.slug)
    voice = formatter.format_channel_completed(channel.slug)
    return jsonify({"voice": voice}), 200
