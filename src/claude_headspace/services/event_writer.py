"""Event writer service with schema validation for persisting events to Postgres."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event type definitions and payload schemas (inlined from event_schemas.py)
# ---------------------------------------------------------------------------

class EventType:
    """Supported event types for the event system."""

    SESSION_REGISTERED = "session_registered"
    SESSION_ENDED = "session_ended"
    TURN_DETECTED = "turn_detected"
    STATE_TRANSITION = "state_transition"
    HOOK_RECEIVED = "hook_received"
    HOOK_SESSION_START = "hook_session_start"
    HOOK_SESSION_END = "hook_session_end"
    HOOK_USER_PROMPT = "hook_user_prompt"
    HOOK_STOP = "hook_stop"
    HOOK_NOTIFICATION = "hook_notification"
    HOOK_POST_TOOL_USE = "hook_post_tool_use"
    QUESTION_DETECTED = "question_detected"

    ALL_TYPES = [
        SESSION_REGISTERED, SESSION_ENDED, TURN_DETECTED, STATE_TRANSITION,
        HOOK_RECEIVED, HOOK_SESSION_START, HOOK_SESSION_END, HOOK_USER_PROMPT,
        HOOK_STOP, HOOK_NOTIFICATION, HOOK_POST_TOOL_USE, QUESTION_DETECTED,
    ]


@dataclass
class PayloadSchema:
    """Schema definition for event payloads."""
    required_fields: list[str]
    optional_fields: list[str]


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
        required_fields=["from_state", "to_state", "trigger"],
        optional_fields=["confidence"],
    ),
    EventType.HOOK_RECEIVED: PayloadSchema(
        required_fields=["hook_type", "claude_session_id", "working_directory"],
        optional_fields=[],
    ),
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
        optional_fields=["working_directory", "title", "message", "notification_type"],
    ),
    EventType.HOOK_POST_TOOL_USE: PayloadSchema(
        required_fields=["claude_session_id"],
        optional_fields=["working_directory", "tool_name"],
    ),
    EventType.QUESTION_DETECTED: PayloadSchema(
        required_fields=["agent_id", "source"],
        optional_fields=["content"],
    ),
}


def validate_event_type(event_type: str) -> bool:
    """Check if event_type is in the defined taxonomy."""
    return event_type in EventType.ALL_TYPES


def validate_payload(event_type: str, payload: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate payload conforms to schema. Returns (is_valid, error_message)."""
    if not validate_event_type(event_type):
        return False, f"Unknown event type: {event_type}"
    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"
    schema = PAYLOAD_SCHEMAS.get(event_type)
    if not schema:
        return False, f"No schema defined for event type: {event_type}"
    missing = [f for f in schema.required_fields if f not in payload]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
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
    """Create a validated event. Returns (ValidatedEvent or None, error or None)."""
    is_valid, error = validate_payload(event_type, payload)
    if not is_valid:
        logger.warning(f"Event validation failed: {error}")
        return None, error
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return ValidatedEvent(
        event_type=event_type, payload=payload, timestamp=timestamp,
        project_id=project_id, agent_id=agent_id, task_id=task_id, turn_id=turn_id,
    ), None


# ---------------------------------------------------------------------------
# Event writer
# ---------------------------------------------------------------------------

@dataclass
class WriteResult:
    """Result of an event write operation."""
    success: bool
    event_id: Optional[int] = None
    error: Optional[str] = None
    retries: int = 0


@dataclass
class EventWriterMetrics:
    """Metrics for monitoring event writer health."""
    total_writes: int = 0
    successful_writes: int = 0
    failed_writes: int = 0
    last_write_timestamp: Optional[datetime] = None
    last_error: Optional[str] = None
    _lock: Lock = field(default_factory=Lock)

    def record_success(self) -> None:
        with self._lock:
            self.total_writes += 1
            self.successful_writes += 1
            self.last_write_timestamp = datetime.now(timezone.utc)

    def record_failure(self, error: str) -> None:
        with self._lock:
            self.total_writes += 1
            self.failed_writes += 1
            self.last_error = error

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_writes": self.total_writes,
                "successful_writes": self.successful_writes,
                "failed_writes": self.failed_writes,
                "last_write_timestamp": (
                    self.last_write_timestamp.isoformat()
                    if self.last_write_timestamp else None
                ),
                "last_error": self.last_error,
            }


class EventWriter:
    """Writes events to Postgres with validation, retries, and metrics."""

    def __init__(
        self,
        database_url: str,
        retry_attempts: int = 3,
        retry_delay_ms: int = 100,
    ) -> None:
        self._database_url = database_url
        self._retry_attempts = retry_attempts
        self._retry_delay_ms = retry_delay_ms
        self._engine = create_engine(
            database_url, pool_size=5, pool_pre_ping=True, pool_recycle=3600,
        )
        self._session_factory = sessionmaker(bind=self._engine)
        self._metrics = EventWriterMetrics()
        self._running = True
        logger.info("EventWriter initialized")

    @property
    def metrics(self) -> EventWriterMetrics:
        return self._metrics

    def write_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        timestamp: Optional[datetime] = None,
        project_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        task_id: Optional[int] = None,
        turn_id: Optional[int] = None,
        session: Optional[Session] = None,
    ) -> WriteResult:
        """Write an event to the database with validation and retry logic."""
        if not self._running:
            return WriteResult(success=False, error="EventWriter is stopped")

        validated, error = create_validated_event(
            event_type=event_type, payload=payload, timestamp=timestamp,
            project_id=project_id, agent_id=agent_id, task_id=task_id, turn_id=turn_id,
        )
        if not validated:
            self._metrics.record_failure(error or "Validation failed")
            return WriteResult(success=False, error=error)

        if session is not None:
            return self._write_to_session(validated, session)
        return self._write_with_retry(validated)

    def _create_db_event(self, event: ValidatedEvent):
        """Create an Event model instance from a ValidatedEvent."""
        from ..models.event import Event
        return Event(
            timestamp=event.timestamp,
            event_type=event.event_type,
            payload=event.payload,
            project_id=event.project_id,
            agent_id=event.agent_id,
            task_id=event.task_id,
            turn_id=event.turn_id,
        )

    def _write_with_retry(self, event: ValidatedEvent) -> WriteResult:
        last_error = None
        for attempt in range(self._retry_attempts):
            try:
                session: Session = self._session_factory()
                try:
                    db_event = self._create_db_event(event)
                    session.add(db_event)
                    session.commit()
                    event_id = db_event.id
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

                self._metrics.record_success()
                return WriteResult(success=True, event_id=event_id, retries=attempt)

            except OperationalError as e:
                last_error = str(e)
                logger.warning(f"Database error attempt {attempt + 1}/{self._retry_attempts}: {e}")
                if attempt < self._retry_attempts - 1:
                    time.sleep((self._retry_delay_ms / 1000.0) * (2 ** attempt))
            except SQLAlchemyError as e:
                last_error = str(e)
                logger.error(f"Database write failed (non-transient): {e}")
                break
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error writing event: {e}")
                break

        self._metrics.record_failure(last_error or "Unknown error")
        return WriteResult(success=False, error=last_error, retries=self._retry_attempts)

    def _write_to_session(self, event: ValidatedEvent, session: Session) -> WriteResult:
        """Write event into a caller-provided session (no commit)."""
        try:
            db_event = self._create_db_event(event)
            session.add(db_event)
            session.flush()
            self._metrics.record_success()
            return WriteResult(success=True, event_id=db_event.id)
        except SQLAlchemyError as e:
            self._metrics.record_failure(str(e))
            logger.error(f"Failed to write event to caller session: {e}")
            return WriteResult(success=False, error=str(e))

    def stop(self) -> None:
        self._running = False
        if self._engine:
            self._engine.dispose()
        logger.info("EventWriter stopped")

    def get_health_status(self) -> dict[str, Any]:
        return {"running": self._running, "metrics": self._metrics.get_stats()}


def create_event_writer(database_url: str, config: Optional[dict] = None) -> EventWriter:
    """Create an EventWriter instance with configuration."""
    event_config = (config or {}).get("event_system", {})
    return EventWriter(
        database_url=database_url,
        retry_attempts=event_config.get("write_retry_attempts", 3),
        retry_delay_ms=event_config.get("write_retry_delay_ms", 100),
    )
