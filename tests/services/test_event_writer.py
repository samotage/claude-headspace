"""Tests for event writer service."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

from claude_headspace.services.event_writer import (
    EventWriter,
    EventWriterMetrics,
    WriteResult,
    create_event_writer,
)
from claude_headspace.services.event_schemas import EventType


class TestEventWriterMetrics:
    """Test EventWriterMetrics class."""

    def test_initial_state(self):
        """Test metrics initial state."""
        metrics = EventWriterMetrics()
        assert metrics.total_writes == 0
        assert metrics.successful_writes == 0
        assert metrics.failed_writes == 0
        assert metrics.last_write_timestamp is None
        assert metrics.last_error is None

    def test_record_success(self):
        """Test recording successful write."""
        metrics = EventWriterMetrics()
        metrics.record_success()

        assert metrics.total_writes == 1
        assert metrics.successful_writes == 1
        assert metrics.failed_writes == 0
        assert metrics.last_write_timestamp is not None

    def test_record_failure(self):
        """Test recording failed write."""
        metrics = EventWriterMetrics()
        metrics.record_failure("Connection error")

        assert metrics.total_writes == 1
        assert metrics.successful_writes == 0
        assert metrics.failed_writes == 1
        assert metrics.last_error == "Connection error"

    def test_get_stats(self):
        """Test getting stats dictionary."""
        metrics = EventWriterMetrics()
        metrics.record_success()
        metrics.record_failure("Error")

        stats = metrics.get_stats()
        assert stats["total_writes"] == 2
        assert stats["successful_writes"] == 1
        assert stats["failed_writes"] == 1
        assert stats["last_write_timestamp"] is not None
        assert stats["last_error"] == "Error"


class TestWriteResult:
    """Test WriteResult class."""

    def test_success_result(self):
        """Test successful write result."""
        result = WriteResult(success=True, event_id=123)
        assert result.success is True
        assert result.event_id == 123
        assert result.error is None
        assert result.retries == 0

    def test_failure_result(self):
        """Test failed write result."""
        result = WriteResult(success=False, error="Database error", retries=3)
        assert result.success is False
        assert result.event_id is None
        assert result.error == "Database error"
        assert result.retries == 3


class TestEventWriter:
    """Test EventWriter class."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock SQLAlchemy engine."""
        with patch("claude_headspace.services.event_writer.create_engine") as mock:
            yield mock

    @pytest.fixture
    def mock_session(self):
        """Create a mock SQLAlchemy session."""
        with patch("claude_headspace.services.event_writer.sessionmaker") as mock:
            session = MagicMock()
            mock.return_value = MagicMock(return_value=session)
            yield session

    def test_initialization(self, mock_engine, mock_session):
        """Test EventWriter initialization."""
        writer = EventWriter(
            database_url="postgresql://test@localhost/test",
            retry_attempts=5,
            retry_delay_ms=200,
        )

        assert writer._retry_attempts == 5
        assert writer._retry_delay_ms == 200
        mock_engine.assert_called_once()

    def test_write_event_validation_failure(self, mock_engine, mock_session):
        """Test that invalid events are rejected."""
        writer = EventWriter(database_url="postgresql://test@localhost/test")

        # Missing required fields
        result = writer.write_event(
            event_type=EventType.TURN_DETECTED,
            payload={"session_uuid": "abc"},  # missing required fields
        )

        assert result.success is False
        assert "Missing required fields" in result.error

    def test_write_event_invalid_type(self, mock_engine, mock_session):
        """Test that invalid event types are rejected."""
        writer = EventWriter(database_url="postgresql://test@localhost/test")

        result = writer.write_event(
            event_type="unknown_type",
            payload={},
        )

        assert result.success is False
        assert "Unknown event type" in result.error

    def test_write_event_when_stopped(self, mock_engine, mock_session):
        """Test that writes fail when writer is stopped."""
        writer = EventWriter(database_url="postgresql://test@localhost/test")
        writer.stop()

        result = writer.write_event(
            event_type=EventType.SESSION_ENDED,
            payload={"session_uuid": "abc", "reason": "timeout"},
        )

        assert result.success is False
        assert "stopped" in result.error.lower()

    def test_get_health_status(self, mock_engine, mock_session):
        """Test getting health status."""
        writer = EventWriter(database_url="postgresql://test@localhost/test")

        status = writer.get_health_status()

        assert status["running"] is True
        assert "metrics" in status

    def test_stop(self, mock_engine, mock_session):
        """Test stopping the writer."""
        mock_eng = MagicMock()
        mock_engine.return_value = mock_eng

        writer = EventWriter(database_url="postgresql://test@localhost/test")
        writer.stop()

        assert writer._running is False
        mock_eng.dispose.assert_called_once()


class TestEventWriterSessionPassThrough:
    """Test EventWriter session pass-through mode."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock SQLAlchemy engine."""
        with patch("claude_headspace.services.event_writer.create_engine") as mock:
            yield mock

    @pytest.fixture
    def mock_sessionmaker(self):
        """Create a mock sessionmaker."""
        with patch("claude_headspace.services.event_writer.sessionmaker") as mock:
            yield mock

    def test_write_event_with_session_adds_and_flushes(self, mock_engine, mock_sessionmaker):
        """When a session is passed, event should be added and flushed but not committed."""
        writer = EventWriter(database_url="postgresql://test@localhost/test")
        caller_session = MagicMock()

        # Mock flush to set the event ID
        def set_id_on_flush():
            for call in caller_session.add.call_args_list:
                obj = call[0][0]
                if hasattr(obj, 'id'):
                    obj.id = 99

        caller_session.flush.side_effect = set_id_on_flush

        result = writer.write_event(
            event_type="session_ended",
            payload={"session_uuid": "abc", "reason": "timeout"},
            session=caller_session,
        )

        assert result.success is True
        assert result.event_id == 99
        caller_session.add.assert_called_once()
        caller_session.flush.assert_called_once()
        caller_session.commit.assert_not_called()

    def test_write_event_with_session_records_metrics(self, mock_engine, mock_sessionmaker):
        """Session pass-through should record success metrics."""
        writer = EventWriter(database_url="postgresql://test@localhost/test")
        caller_session = MagicMock()

        writer.write_event(
            event_type="session_ended",
            payload={"session_uuid": "abc", "reason": "timeout"},
            session=caller_session,
        )

        stats = writer.metrics.get_stats()
        assert stats["successful_writes"] == 1
        assert stats["failed_writes"] == 0

    def test_write_event_with_session_handles_db_error(self, mock_engine, mock_sessionmaker):
        """Session pass-through should handle SQLAlchemy errors gracefully."""
        from sqlalchemy.exc import IntegrityError

        writer = EventWriter(database_url="postgresql://test@localhost/test")
        caller_session = MagicMock()
        caller_session.flush.side_effect = IntegrityError("", {}, Exception("FK violation"))

        result = writer.write_event(
            event_type="session_ended",
            payload={"session_uuid": "abc", "reason": "timeout"},
            session=caller_session,
        )

        assert result.success is False
        assert result.error is not None
        stats = writer.metrics.get_stats()
        assert stats["failed_writes"] == 1

    def test_write_event_without_session_uses_own_factory(self, mock_engine, mock_sessionmaker):
        """Without a session, should use own session factory (existing behavior)."""
        own_session = MagicMock()
        mock_sessionmaker.return_value = MagicMock(return_value=own_session)

        writer = EventWriter(database_url="postgresql://test@localhost/test")

        result = writer.write_event(
            event_type="session_ended",
            payload={"session_uuid": "abc", "reason": "timeout"},
        )

        # The own session factory should be used (commit is called)
        own_session.commit.assert_called_once()


class TestCreateEventWriter:
    """Test create_event_writer factory function."""

    @patch("claude_headspace.services.event_writer.create_engine")
    @patch("claude_headspace.services.event_writer.sessionmaker")
    def test_create_with_defaults(self, mock_session, mock_engine):
        """Test creating writer with default config."""
        writer = create_event_writer(database_url="postgresql://test@localhost/test")

        assert writer._retry_attempts == 3
        assert writer._retry_delay_ms == 100

    @patch("claude_headspace.services.event_writer.create_engine")
    @patch("claude_headspace.services.event_writer.sessionmaker")
    def test_create_with_config(self, mock_session, mock_engine):
        """Test creating writer with custom config."""
        config = {
            "event_system": {
                "write_retry_attempts": 5,
                "write_retry_delay_ms": 500,
            }
        }
        writer = create_event_writer(
            database_url="postgresql://test@localhost/test",
            config=config,
        )

        assert writer._retry_attempts == 5
        assert writer._retry_delay_ms == 500


class TestEventWriterRetryLogic:
    """Test retry logic for event writer."""

    @patch("claude_headspace.services.event_writer.create_engine")
    @patch("claude_headspace.services.event_writer.sessionmaker")
    @patch("claude_headspace.services.event_writer.time.sleep")
    def test_retry_on_transient_error(self, mock_sleep, mock_session_maker, mock_engine):
        """Test that transient errors trigger retries."""
        from sqlalchemy.exc import OperationalError

        # Set up session to fail twice then succeed
        mock_session = MagicMock()
        mock_session_maker.return_value = MagicMock(return_value=mock_session)

        call_count = [0]

        def mock_commit():
            call_count[0] += 1
            if call_count[0] < 3:
                raise OperationalError("statement", {}, Exception("Connection lost"))

        mock_session.commit.side_effect = mock_commit

        writer = EventWriter(
            database_url="postgresql://test@localhost/test",
            retry_attempts=3,
            retry_delay_ms=100,
        )

        # Should succeed after retries (session mock fails twice, succeeds third)
        result = writer.write_event(
            event_type=EventType.SESSION_ENDED,
            payload={"session_uuid": "abc", "reason": "timeout"},
        )

        # Verify retries happened with exponential backoff
        assert mock_sleep.call_count == 2
        assert result.success is True
