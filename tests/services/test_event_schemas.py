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

    def test_hook_event_types_defined(self):
        """Test that specific hook event types are defined (Issue 9 remediation)."""
        assert EventType.HOOK_SESSION_START == "hook_session_start"
        assert EventType.HOOK_SESSION_END == "hook_session_end"
        assert EventType.HOOK_USER_PROMPT == "hook_user_prompt"
        assert EventType.HOOK_STOP == "hook_stop"
        assert EventType.HOOK_NOTIFICATION == "hook_notification"

    def test_all_types_list(self):
        """Test that ALL_TYPES contains all event types."""
        # Core types + hook_received + 6 specific hook types + question_detected = 12
        assert len(EventType.ALL_TYPES) == 12
        assert EventType.SESSION_REGISTERED in EventType.ALL_TYPES
        assert EventType.SESSION_ENDED in EventType.ALL_TYPES
        assert EventType.TURN_DETECTED in EventType.ALL_TYPES
        assert EventType.STATE_TRANSITION in EventType.ALL_TYPES
        assert EventType.HOOK_RECEIVED in EventType.ALL_TYPES
        # Hook types
        assert EventType.HOOK_SESSION_START in EventType.ALL_TYPES
        assert EventType.HOOK_SESSION_END in EventType.ALL_TYPES
        assert EventType.HOOK_USER_PROMPT in EventType.ALL_TYPES
        assert EventType.HOOK_STOP in EventType.ALL_TYPES
        assert EventType.HOOK_NOTIFICATION in EventType.ALL_TYPES
        assert EventType.HOOK_POST_TOOL_USE in EventType.ALL_TYPES
        # Content pipeline events
        assert EventType.QUESTION_DETECTED in EventType.ALL_TYPES


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
        """Test state_transition schema.

        Note: agent_id and command_id are passed as function parameters to write_event(),
        not in the payload (Issue 9 remediation fix).
        """
        schema = PAYLOAD_SCHEMAS[EventType.STATE_TRANSITION]
        assert "from_state" in schema.required_fields
        assert "to_state" in schema.required_fields
        assert "trigger" in schema.required_fields
        assert "confidence" in schema.optional_fields
        # agent_id and command_id are NOT in payload - passed as function params
        assert "agent_id" not in schema.required_fields
        assert "command_id" not in schema.required_fields

    def test_hook_received_schema(self):
        """Test hook_received schema."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_RECEIVED]
        assert "hook_type" in schema.required_fields
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.required_fields

    def test_hook_session_start_schema(self):
        """Test hook_session_start schema (Issue 9 remediation)."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_SESSION_START]
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.optional_fields

    def test_hook_session_end_schema(self):
        """Test hook_session_end schema (Issue 9 remediation)."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_SESSION_END]
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.optional_fields

    def test_hook_user_prompt_schema(self):
        """Test hook_user_prompt schema (Issue 9 remediation)."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_USER_PROMPT]
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.optional_fields

    def test_hook_stop_schema(self):
        """Test hook_stop schema (Issue 9 remediation)."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_STOP]
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.optional_fields

    def test_hook_notification_schema(self):
        """Test hook_notification schema (Issue 9 remediation)."""
        schema = PAYLOAD_SCHEMAS[EventType.HOOK_NOTIFICATION]
        assert "claude_session_id" in schema.required_fields
        assert "working_directory" in schema.optional_fields
        assert "title" in schema.optional_fields
        assert "message" in schema.optional_fields


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
        """Test valid state_transition payload.

        Note: agent_id and command_id are passed as function params, not in payload.
        """
        payload = {
            "from_state": "idle",
            "to_state": "processing",
            "trigger": "user:command",
        }
        is_valid, error = validate_payload(EventType.STATE_TRANSITION, payload)
        assert is_valid is True

    def test_valid_state_transition_payload_with_confidence(self):
        """Test state_transition payload with optional confidence field."""
        payload = {
            "from_state": "idle",
            "to_state": "processing",
            "trigger": "user:command",
            "confidence": 0.95,
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

    def test_valid_hook_session_start_payload(self):
        """Test valid hook_session_start payload (Issue 9 remediation)."""
        payload = {
            "claude_session_id": "session-123",
        }
        is_valid, error = validate_payload(EventType.HOOK_SESSION_START, payload)
        assert is_valid is True

    def test_valid_hook_stop_payload(self):
        """Test valid hook_stop payload (Issue 9 remediation)."""
        payload = {
            "claude_session_id": "session-123",
            "working_directory": "/Users/test/project",  # optional
        }
        is_valid, error = validate_payload(EventType.HOOK_STOP, payload)
        assert is_valid is True

    def test_valid_hook_notification_payload(self):
        """Test valid hook_notification payload with optional fields."""
        payload = {
            "claude_session_id": "session-123",
            "title": "Command Complete",
            "message": "Your command has finished",
        }
        is_valid, error = validate_payload(EventType.HOOK_NOTIFICATION, payload)
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
        """Test creating event with foreign keys.

        Note: agent_id and command_id are passed as function params, not in payload.
        """
        payload = {
            "from_state": "idle",
            "to_state": "processing",
            "trigger": "user:command",
            "confidence": 0.95,
        }
        event, error = create_validated_event(
            event_type=EventType.STATE_TRANSITION,
            payload=payload,
            project_id=1,
            agent_id=2,
            command_id=3,
        )
        assert event is not None
        assert event.project_id == 1
        assert event.agent_id == 2
        assert event.command_id == 3

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
