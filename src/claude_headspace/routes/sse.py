"""SSE (Server-Sent Events) endpoint for real-time updates."""

import logging
from typing import Generator, Optional

from flask import Blueprint, Response, request

from ..services.broadcaster import get_broadcaster

logger = logging.getLogger(__name__)

sse_bp = Blueprint("sse", __name__)


def parse_filter_types(types_param: Optional[str]) -> Optional[list[str]]:
    """
    Parse the types query parameter into a list of event types.

    Args:
        types_param: Comma-separated event types or None

    Returns:
        List of event types or None if not specified
    """
    if not types_param:
        return None
    return [t.strip() for t in types_param.split(",") if t.strip()]


def parse_int_param(value: Optional[str]) -> Optional[int]:
    """
    Parse an integer query parameter.

    Args:
        value: String value or None

    Returns:
        Integer value or None if not specified/invalid
    """
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def generate_events(
    client_id: str,
    last_event_id: int | None = None,
) -> Generator[str, None, None]:
    """
    Generator function that yields SSE events for a client.

    Args:
        client_id: The registered client ID
        last_event_id: If set, replay missed events from the replay buffer

    Yields:
        SSE-formatted event strings
    """
    broadcaster = get_broadcaster()

    # Yield an immediate heartbeat to flush HTTP headers to the client.
    # Without this, Flask buffers the response until the first real event,
    # causing EventSource.onopen to never fire.
    yield ": heartbeat\n\n"

    # Replay missed events if client is reconnecting with a Last-Event-ID
    if last_event_id is not None:
        client = broadcaster.get_client(client_id)
        filters = client.filters if client else {}
        replayed = broadcaster.get_replay_events(last_event_id, filters)
        if replayed:
            logger.info(
                f"Replaying {len(replayed)} events for client {client_id} "
                f"(after event_id={last_event_id})"
            )
            for event in replayed:
                yield event.format()

    try:
        while True:
            # Get next event with timeout (allows checking for shutdown)
            event = broadcaster.get_next_event(client_id, timeout=30.0)

            if event is None:
                # Timeout - send heartbeat
                yield ": heartbeat\n\n"
            else:
                # Send the event
                yield event.format()

            # Check if client is still active
            client = broadcaster.get_client(client_id)
            if client is None or not client.is_active:
                break

    except GeneratorExit:
        # Client disconnected
        logger.info(f"Client {client_id} disconnected (generator exit)")
    except Exception as e:
        logger.error(f"Error in SSE generator for client {client_id}: {e}")
    finally:
        # Always unregister on exit
        broadcaster.unregister_client(client_id)
        logger.debug(f"Client {client_id} unregistered from generator cleanup")


@sse_bp.route("/api/events/stream")
def events():
    """
    SSE endpoint for real-time event streaming.

    Query Parameters:
        types: Comma-separated list of event types to filter
        project_id: Filter events for a specific project
        agent_id: Filter events for a specific agent

    Headers:
        Last-Event-ID: Optional last event ID for reconnection logging

    Returns:
        SSE stream or HTTP 503 if connection limit reached
    """
    broadcaster = get_broadcaster()

    # Check connection limit
    if not broadcaster.can_accept_connection():
        logger.warning("SSE connection rejected: limit reached")
        response = Response(
            "Service temporarily unavailable - connection limit reached",
            status=503,
            mimetype="text/plain",
        )
        response.headers["Retry-After"] = str(broadcaster.retry_after)
        return response

    # Parse filter parameters
    types = parse_filter_types(request.args.get("types"))
    project_id = parse_int_param(request.args.get("project_id"))
    agent_id = parse_int_param(request.args.get("agent_id"))

    # Parse Last-Event-ID for replay on reconnect
    last_event_id_raw = request.headers.get("Last-Event-ID")
    last_event_id: int | None = None
    if last_event_id_raw:
        try:
            last_event_id = int(last_event_id_raw)
            logger.info(f"SSE client reconnecting from event ID: {last_event_id}")
        except ValueError:
            logger.warning(f"Invalid Last-Event-ID: {last_event_id_raw}")

    # Register client
    client_id = broadcaster.register_client(
        types=types,
        project_id=project_id,
        agent_id=agent_id,
    )

    if client_id is None:
        # Registration failed (shouldn't happen if can_accept_connection passed)
        logger.error("Failed to register SSE client after connection check passed")
        response = Response(
            "Service temporarily unavailable",
            status=503,
            mimetype="text/plain",
        )
        response.headers["Retry-After"] = str(broadcaster.retry_after)
        return response

    logger.info(
        f"SSE client {client_id} connected: "
        f"types={types}, project_id={project_id}, agent_id={agent_id}"
    )

    # Create streaming response
    response = Response(
        generate_events(client_id, last_event_id=last_event_id),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"  # Disable nginx buffering

    return response
