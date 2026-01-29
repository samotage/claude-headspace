"""Event type definitions and payload schemas for the event system."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Event type constants matching the Event model
class EventType:
    """Supported event types for the event system."""

    SESSION_REGISTERED = "session_registered"
    SESSION_ENDED = "session_ended"
    TURN_DETECTED = "turn_detected"
    STATE_TRANSITION = "state_transition"
    HOOK_RECEIVED = "hook_received"

    # List of all valid event types
    ALL_TYPES = [
        SESSION_REGISTERED,
        SESSION_ENDED,
        TURN_DETECTED,
        STATE_TRANSITION,
        HOOK_RECEIVED,
    ]


@dataclass
class PayloadSchema:
    """Schema definition for event payloads."""

    required_fields: list[str]
    optional_fields: list[str]


# Payload schemas per event type
PAYLOAD_SCHEMAS: dict[str, PayloadSchema] = {
    EventType.SESSION_REGISTERED: PayloadSchema(
        required_fields=["session_uuid", "project_path", "working_directory"],
        optional_fields=["iterm_pane_id"],
    ),
    EventType.SESSION_ENDED: PayloadSchema(
        required_fields=["session_uuid", "reason"],
        optional_fields=["duration_seconds"],
    ),
    EventType.TURN_DETECTED: PayloadSchema(
        required_fields=["session_uuid", "actor", "text", "source", "turn_timestamp"],
        optional_fields=[],
    ),
    EventType.STATE_TRANSITION: PayloadSchema(
        required_fields=["agent_id", "task_id", "from_state", "to_state", "trigger"],
        optional_fields=[],
    ),
    EventType.HOOK_RECEIVED: PayloadSchema(
        required_fields=["hook_type", "claude_session_id", "working_directory"],
        optional_fields=[],
    ),
}


def validate_event_type(event_type: str) -> bool:
    """
    Validate that an event type is in the defined taxonomy.

    Args:
        event_type: The event type string to validate

    Returns:
        True if valid, False otherwise
    """
    return event_type in EventType.ALL_TYPES


def validate_payload(event_type: str, payload: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate that a payload conforms to the schema for its event type.

    Args:
        event_type: The event type
        payload: The payload dictionary to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not validate_event_type(event_type):
        return False, f"Unknown event type: {event_type}"

    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"

    schema = PAYLOAD_SCHEMAS.get(event_type)
    if not schema:
        return False, f"No schema defined for event type: {event_type}"

    # Check required fields
    missing_fields = []
    for field in schema.required_fields:
        if field not in payload:
            missing_fields.append(field)

    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    return True, None


@dataclass
class ValidatedEvent:
    """A validated event ready for writing to the database."""

    event_type: str
    payload: dict[str, Any]
    timestamp: datetime
    project_id: Optional[int] = None
    agent_id: Optional[int] = None
    task_id: Optional[int] = None
    turn_id: Optional[int] = None


def create_validated_event(
    event_type: str,
    payload: dict[str, Any],
    timestamp: Optional[datetime] = None,
    project_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    task_id: Optional[int] = None,
    turn_id: Optional[int] = None,
) -> tuple[Optional[ValidatedEvent], Optional[str]]:
    """
    Create a validated event ready for writing.

    Args:
        event_type: The event type
        payload: The event payload
        timestamp: Optional timestamp (defaults to now)
        project_id: Optional project foreign key
        agent_id: Optional agent foreign key
        task_id: Optional task foreign key
        turn_id: Optional turn foreign key

    Returns:
        Tuple of (ValidatedEvent or None, error_message or None)
    """
    from datetime import timezone

    is_valid, error = validate_payload(event_type, payload)
    if not is_valid:
        logger.warning(f"Event validation failed: {error}")
        return None, error

    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return ValidatedEvent(
        event_type=event_type,
        payload=payload,
        timestamp=timestamp,
        project_id=project_id,
        agent_id=agent_id,
        task_id=task_id,
        turn_id=turn_id,
    ), None
