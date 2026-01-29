"""Event type definitions and payload schemas for the event system."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Event type constants matching the Event model
class EventType:
    """Supported event types for the event system."""

    # Core events
    SESSION_REGISTERED = "session_registered"
    SESSION_ENDED = "session_ended"
    TURN_DETECTED = "turn_detected"
    STATE_TRANSITION = "state_transition"

    # Generic hook event (legacy)
    HOOK_RECEIVED = "hook_received"

    # Specific hook events (Issue 9 remediation)
    HOOK_SESSION_START = "hook_session_start"
    HOOK_SESSION_END = "hook_session_end"
    HOOK_USER_PROMPT = "hook_user_prompt"
    HOOK_STOP = "hook_stop"
    HOOK_NOTIFICATION = "hook_notification"

    # List of all valid event types
    ALL_TYPES = [
        SESSION_REGISTERED,
        SESSION_ENDED,
        TURN_DETECTED,
        STATE_TRANSITION,
        HOOK_RECEIVED,
        HOOK_SESSION_START,
        HOOK_SESSION_END,
        HOOK_USER_PROMPT,
        HOOK_STOP,
        HOOK_NOTIFICATION,
    ]


@dataclass
class PayloadSchema:
    """Schema definition for event payloads."""

    required_fields: list[str]
    optional_fields: list[str]


# Payload schemas per event type
# Note: agent_id, task_id, etc. are passed as function parameters to write_event(),
# not in the payload. The payload contains semantic event data only.
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
    # STATE_TRANSITION: agent_id and task_id are passed as function params, not payload
    # (Issue 9 remediation - fixed schema to match actual usage in task_lifecycle.py)
    EventType.STATE_TRANSITION: PayloadSchema(
        required_fields=["from_state", "to_state", "trigger"],
        optional_fields=["confidence"],
    ),
    # Generic hook event (legacy)
    EventType.HOOK_RECEIVED: PayloadSchema(
        required_fields=["hook_type", "claude_session_id", "working_directory"],
        optional_fields=[],
    ),
    # Specific hook event schemas (Issue 9 remediation)
    EventType.HOOK_SESSION_START: PayloadSchema(
        required_fields=["claude_session_id"],
        optional_fields=["working_directory"],
    ),
    EventType.HOOK_SESSION_END: PayloadSchema(
        required_fields=["claude_session_id"],
        optional_fields=["working_directory"],
    ),
    EventType.HOOK_USER_PROMPT: PayloadSchema(
        required_fields=["claude_session_id"],
        optional_fields=["working_directory"],
    ),
    EventType.HOOK_STOP: PayloadSchema(
        required_fields=["claude_session_id"],
        optional_fields=["working_directory"],
    ),
    EventType.HOOK_NOTIFICATION: PayloadSchema(
        required_fields=["claude_session_id"],
        optional_fields=["working_directory", "title", "message"],
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
