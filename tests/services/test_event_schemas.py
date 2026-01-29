"""Tests for event schemas and validation."""

import pytest
from datetime import datetime, timezone

from claude_headspace.services.event_schemas import (
    EventType,
    PayloadSchema,
    PAYLOAD_SCHEMAS,
    validate_event_type,
    validate_payload,
    create_validated_event,
    ValidatedEvent,
)


class TestEventType:
    """Test EventType constants."""

    def test_all_types_defined(self):
        """Test that all event types are defined."""
        assert EventType.SESSION_REGISTERED == "session_registered"
        assert EventType.SESSION_ENDED == "session_ended"
        assert EventType.TURN_DETECTED == "turn_detected"
        assert EventType.STATE_TRANSITION == "state_transition"
        assert EventType.HOOK_RECEIVED == "hook_received"

    def test_all_types_list(self):
        """Test that ALL_TYPES contains all event types."""
        assert len(EventType.ALL_TYPES) == 5
        assert EventType.SESSION_REGISTERED in EventType.ALL_TYPES
        assert EventType.SESSION_ENDED in EventType.ALL_TYPES
        assert EventType.TURN_DETECTED in EventType.ALL_TYPES
        assert EventType.STATE_TRANSITION in EventType.ALL_TYPES
        assert EventType.HOOK_RECEIVED in EventType.ALL_TYPES


class TestPayloadSchemas:
    """Test payload schema definitions."""

    def test_all_event_types_have_schemas(self):
        """Test that every event type has a schema defined."""
        for event_type in EventType.ALL_TYPES:
            assert event_type in PAYLOAD_SCHEMAS
            assert isinstance(PAYLOAD_SCHEMAS[event_type], PayloadSchema)

    def test_session_registered_schema(self):
        """Test session_registered schema."""
        schema = PAYLOAD_SCHEMAS[EventType.SESSION_REGISTERED]
        assert "session_uuid" in schema.required_fields
        assert "project_path" in schema.required_fields
        assert "working_directory" in schema.required_fields
        assert "iterm_pane_id" in schema.optional_fields

    def test_session_ended_schema(self):
        """Test session_ended schema."""
        schema = PAYLOAD_SCHEMAS[EventType.SESSION_ENDED]
        assert "session_uuid" in schema.required_fields
        assert "reason" in schema.required_fields
        assert "duration_seconds" in schema.optional_fields

    def test_turn_detected_schema(self):
        """Test turn_detected schema."""
        schema = PAYLOAD_SCHEMAS[EventType.TURN_DETECTED]
        assert "session_uuid" in schema.required_fields
        assert "actor" in schema.required_fields
        assert "text" in schema.required_fields
        assert "source" in schema.required_fields
        assert "turn_timestamp" in schema.required_fields

    def test_state_transition_schema(self):
        """Test state_transition schema."""
        schema = PAYLOAD_SCHEMAS[EventType.STATE_TRANSITION]
        assert "agent_id" in schema.required_fields
        assert "task_id" in schema.required_fields
        assert "from_state" in schema.required_fields
        assert "to_state" in schema.required_fields
        assert "trigger" in schema.required_fields

    def test_hook_received_schema(self):
        """Test hook_received schema."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_RECEIVED]
        assert "hook_type" in schema.required_fields
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.required_fields


class TestValidateEventType:
    """Test validate_event_type function."""

    def test_valid_event_types(self):
        """Test that valid event types pass validation."""
        for event_type in EventType.ALL_TYPES:
            assert validate_event_type(event_type) is True

    def test_invalid_event_type(self):
        """Test that invalid event types fail validation."""
        assert validate_event_type("unknown_event") is False
        assert validate_event_type("") is False
        assert validate_event_type("TURN_DETECTED") is False  # case sensitive


class TestValidatePayload:
    """Test validate_payload function."""

    def test_valid_turn_detected_payload(self):
        """Test valid turn_detected payload."""
        payload = {
            "session_uuid": "abc-123",
            "actor": "user",
            "text": "Hello, Claude!",
            "source": "polling",
            "turn_timestamp": "2024-01-01T12:00:00Z",
        }
        is_valid, error = validate_payload(EventType.TURN_DETECTED, payload)
        assert is_valid is True
        assert error is None

    def test_missing_required_field(self):
        """Test that missing required fields are detected."""
        payload = {
            "session_uuid": "abc-123",
            "actor": "user",
            # missing text, source, turn_timestamp
        }
        is_valid, error = validate_payload(EventType.TURN_DETECTED, payload)
        assert is_valid is False
        assert "Missing required fields" in error
        assert "text" in error

    def test_valid_session_registered_payload(self):
        """Test valid session_registered payload."""
        payload = {
            "session_uuid": "abc-123",
            "project_path": "/Users/test/project",
            "working_directory": "/Users/test/project",
        }
        is_valid, error = validate_payload(EventType.SESSION_REGISTERED, payload)
        assert is_valid is True
        assert error is None

    def test_valid_session_registered_with_optional(self):
        """Test session_registered with optional field."""
        payload = {
            "session_uuid": "abc-123",
            "project_path": "/Users/test/project",
            "working_directory": "/Users/test/project",
            "iterm_pane_id": "pane-1",
        }
        is_valid, error = validate_payload(EventType.SESSION_REGISTERED, payload)
        assert is_valid is True
        assert error is None

    def test_valid_session_ended_payload(self):
        """Test valid session_ended payload."""
        payload = {
            "session_uuid": "abc-123",
            "reason": "timeout",
        }
        is_valid, error = validate_payload(EventType.SESSION_ENDED, payload)
        assert is_valid is True

    def test_valid_state_transition_payload(self):
        """Test valid state_transition payload."""
        payload = {
            "agent_id": 1,
            "task_id": 2,
            "from_state": "idle",
            "to_state": "processing",
            "trigger": "turn",
        }
        is_valid, error = validate_payload(EventType.STATE_TRANSITION, payload)
        assert is_valid is True

    def test_valid_hook_received_payload(self):
        """Test valid hook_received payload."""
        payload = {
            "hook_type": "session_start",
            "claude_session_id": "session-123",
            "working_directory": "/Users/test",
        }
        is_valid, error = validate_payload(EventType.HOOK_RECEIVED, payload)
        assert is_valid is True

    def test_invalid_event_type(self):
        """Test that invalid event type fails validation."""
        is_valid, error = validate_payload("unknown", {})
        assert is_valid is False
        assert "Unknown event type" in error

    def test_invalid_payload_type(self):
        """Test that non-dict payload fails validation."""
        is_valid, error = validate_payload(EventType.TURN_DETECTED, "not a dict")
        assert is_valid is False
        assert "must be a dictionary" in error


class TestCreateValidatedEvent:
    """Test create_validated_event function."""

    def test_create_valid_event(self):
        """Test creating a valid event."""
        payload = {
            "session_uuid": "abc-123",
            "actor": "user",
            "text": "Hello",
            "source": "polling",
            "turn_timestamp": "2024-01-01T12:00:00Z",
        }
        event, error = create_validated_event(
            event_type=EventType.TURN_DETECTED,
            payload=payload,
        )
        assert event is not None
        assert error is None
        assert event.event_type == EventType.TURN_DETECTED
        assert event.payload == payload
        assert event.timestamp is not None

    def test_create_event_with_timestamp(self):
        """Test creating event with custom timestamp."""
        payload = {
            "session_uuid": "abc-123",
            "reason": "timeout",
        }
        custom_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        event, error = create_validated_event(
            event_type=EventType.SESSION_ENDED,
            payload=payload,
            timestamp=custom_time,
        )
        assert event is not None
        assert event.timestamp == custom_time

    def test_create_event_with_foreign_keys(self):
        """Test creating event with foreign keys."""
        payload = {
            "agent_id": 1,
            "task_id": 2,
            "from_state": "idle",
            "to_state": "processing",
            "trigger": "turn",
        }
        event, error = create_validated_event(
            event_type=EventType.STATE_TRANSITION,
            payload=payload,
            project_id=1,
            agent_id=2,
            task_id=3,
        )
        assert event is not None
        assert event.project_id == 1
        assert event.agent_id == 2
        assert event.task_id == 3

    def test_create_invalid_event(self):
        """Test creating invalid event returns error."""
        payload = {"missing": "required fields"}
        event, error = create_validated_event(
            event_type=EventType.TURN_DETECTED,
            payload=payload,
        )
        assert event is None
        assert error is not None
        assert "Missing required fields" in error
