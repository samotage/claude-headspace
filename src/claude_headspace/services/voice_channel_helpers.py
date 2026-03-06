"""Voice channel context state and helpers. Minimal Flask dependency."""

from flask import request

from .voice_matchers import _fuzzy_match

# Module-level channel context cache
# Key: auth identifier (token or "localhost"), Value: channel slug
_channel_context: dict[str, str] = {}


def _set_channel_context(auth_id: str, channel_slug: str) -> None:
    """Set the current channel context for this voice session."""
    _channel_context[auth_id] = channel_slug


def _get_channel_context(auth_id: str) -> str | None:
    """Get the current channel context for this voice session."""
    return _channel_context.get(auth_id)


def _get_auth_id() -> str:
    """Extract an auth identifier from the current request for context tracking.

    Returns the Bearer token string if present, or "localhost" for
    localhost-bypass authenticated requests (no token).
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return "localhost"


def _resolve_channel_ref(channel_ref: str, auth_id: str) -> str:
    """Resolve 'this channel' / 'the channel' to actual channel slug.

    Raises ValueError if context reference used but no context is set.
    """
    if channel_ref.strip().lower() in (
        "this channel",
        "the channel",
        "this",
        "current channel",
    ):
        ctx = _get_channel_context(auth_id)
        if ctx:
            return ctx
        raise ValueError("No current channel context. Specify the channel name.")
    return channel_ref


def _match_persona_for_channel(name_ref: str) -> dict:
    """Fuzzy match a persona name/slug reference against active personas."""
    from ..models.persona import Persona

    personas = Persona.query.filter_by(status="active").all()
    return _fuzzy_match(
        name_ref,
        personas,
        lambda p: [p.name.lower(), p.slug.lower()],
    )
