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

# Single source of truth for event types and schemas
from .event_schemas import (
    EventType,
    ValidatedEvent,
    create_validated_event,
    validate_event_type,
    validate_payload,
)

logger = logging.getLogger(__name__)

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
            database_url, pool_size=2, max_overflow=3,
            pool_pre_ping=True, pool_recycle=3600,
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
        command_id: Optional[int] = None,
        turn_id: Optional[int] = None,
        session: Optional[Session] = None,
    ) -> WriteResult:
        """Write an event to the database with validation and retry logic."""
        if not self._running:
            return WriteResult(success=False, error="EventWriter is stopped")

        validated, error = create_validated_event(
            event_type=event_type, payload=payload, timestamp=timestamp,
            project_id=project_id, agent_id=agent_id, command_id=command_id, turn_id=turn_id,
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
            command_id=event.command_id,
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
