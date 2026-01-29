"""Event writer service for persisting events to Postgres."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

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
        """Record a successful write."""
        with self._lock:
            self.total_writes += 1
            self.successful_writes += 1
            self.last_write_timestamp = datetime.now(timezone.utc)

    def record_failure(self, error: str) -> None:
        """Record a failed write."""
        with self._lock:
            self.total_writes += 1
            self.failed_writes += 1
            self.last_error = error

    def get_stats(self) -> dict[str, Any]:
        """Get current metrics as a dictionary."""
        with self._lock:
            return {
                "total_writes": self.total_writes,
                "successful_writes": self.successful_writes,
                "failed_writes": self.failed_writes,
                "last_write_timestamp": (
                    self.last_write_timestamp.isoformat()
                    if self.last_write_timestamp
                    else None
                ),
                "last_error": self.last_error,
            }


class EventWriter:
    """
    Service for writing events to the Postgres Event table.

    Handles validation, retries with exponential backoff, and metrics tracking.
    Uses its own database connection pool, independent of Flask.
    """

    def __init__(
        self,
        database_url: str,
        retry_attempts: int = 3,
        retry_delay_ms: int = 100,
    ) -> None:
        """
        Initialize the event writer.

        Args:
            database_url: PostgreSQL connection URL
            retry_attempts: Maximum number of retry attempts for failed writes
            retry_delay_ms: Base delay in milliseconds between retries
        """
        self._database_url = database_url
        self._retry_attempts = retry_attempts
        self._retry_delay_ms = retry_delay_ms

        # Create engine and session factory
        self._engine = create_engine(
            database_url,
            pool_size=5,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = sessionmaker(bind=self._engine)

        self._metrics = EventWriterMetrics()
        self._running = True

        logger.info("EventWriter initialized")

    @property
    def metrics(self) -> EventWriterMetrics:
        """Get the metrics tracker."""
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
    ) -> WriteResult:
        """
        Write an event to the database with validation and retry logic.

        Args:
            event_type: The event type string
            payload: The event payload dictionary
            timestamp: Optional event timestamp
            project_id: Optional project foreign key
            agent_id: Optional agent foreign key
            task_id: Optional task foreign key
            turn_id: Optional turn foreign key

        Returns:
            WriteResult indicating success/failure
        """
        if not self._running:
            return WriteResult(success=False, error="EventWriter is stopped")

        # Validate event
        validated, error = create_validated_event(
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            project_id=project_id,
            agent_id=agent_id,
            task_id=task_id,
            turn_id=turn_id,
        )

        if not validated:
            self._metrics.record_failure(error or "Validation failed")
            logger.warning(f"Event validation failed: {error}")
            return WriteResult(success=False, error=error)

        # Attempt write with retries
        return self._write_with_retry(validated)

    def _write_with_retry(self, event: ValidatedEvent) -> WriteResult:
        """
        Write event with retry logic and exponential backoff.

        Args:
            event: Validated event to write

        Returns:
            WriteResult indicating success/failure
        """
        last_error = None

        for attempt in range(self._retry_attempts):
            try:
                event_id = self._write_to_db(event)
                self._metrics.record_success()
                logger.debug(
                    f"Event written successfully: id={event_id}, type={event.event_type}"
                )
                return WriteResult(success=True, event_id=event_id, retries=attempt)

            except OperationalError as e:
                # Transient database error - retry
                last_error = str(e)
                logger.warning(
                    f"Database error on attempt {attempt + 1}/{self._retry_attempts}: {e}"
                )

                if attempt < self._retry_attempts - 1:
                    # Exponential backoff
                    delay = (self._retry_delay_ms / 1000.0) * (2**attempt)
                    time.sleep(delay)

            except SQLAlchemyError as e:
                # Non-transient error - don't retry
                last_error = str(e)
                logger.error(f"Database write failed (non-transient): {e}")
                break

            except Exception as e:
                # Unexpected error
                last_error = str(e)
                logger.error(f"Unexpected error writing event: {e}")
                break

        # All retries exhausted
        self._metrics.record_failure(last_error or "Unknown error")
        logger.error(
            f"Event write failed after {self._retry_attempts} attempts: {last_error}"
        )
        return WriteResult(
            success=False,
            error=last_error,
            retries=self._retry_attempts,
        )

    def _write_to_db(self, event: ValidatedEvent) -> int:
        """
        Write event to database in a single transaction.

        Args:
            event: Validated event to write

        Returns:
            The ID of the created event record

        Raises:
            SQLAlchemyError: On database error
        """
        # Import here to avoid circular imports
        from ..models.event import Event

        session: Session = self._session_factory()
        try:
            db_event = Event(
                timestamp=event.timestamp,
                event_type=event.event_type,
                payload=event.payload,
                project_id=event.project_id,
                agent_id=event.agent_id,
                task_id=event.task_id,
                turn_id=event.turn_id,
            )
            session.add(db_event)
            session.commit()
            event_id = db_event.id
            return event_id
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def stop(self) -> None:
        """Stop the event writer and close connections."""
        self._running = False
        if self._engine:
            self._engine.dispose()
        logger.info("EventWriter stopped")

    def get_health_status(self) -> dict[str, Any]:
        """
        Get health status for the event writer.

        Returns:
            Dictionary with health information
        """
        return {
            "running": self._running,
            "metrics": self._metrics.get_stats(),
        }


def create_event_writer(
    database_url: str,
    config: Optional[dict] = None,
) -> EventWriter:
    """
    Create an EventWriter instance with configuration.

    Args:
        database_url: PostgreSQL connection URL
        config: Optional configuration dictionary

    Returns:
        Configured EventWriter instance
    """
    if config is None:
        config = {}

    event_config = config.get("event_system", {})

    return EventWriter(
        database_url=database_url,
        retry_attempts=event_config.get("write_retry_attempts", 3),
        retry_delay_ms=event_config.get("write_retry_delay_ms", 100),
    )
