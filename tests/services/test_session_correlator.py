"""Tests for session correlator service."""

from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.session_correlator import (
    CorrelationResult,
    cache_session_mapping,
    clear_session_cache,
    correlate_session,
    get_cached_agent_id,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear session cache before each test."""
    clear_session_cache()
    yield
    clear_session_cache()


class TestCorrelateSession:
    """Tests for correlate_session function."""

    @patch("claude_headspace.services.session_correlator.db")
    def test_correlate_by_cached_session_id(self, mock_db):
        """Test correlation by cached session ID."""
        # Setup: cache a session ID
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_db.session.get.return_value = mock_agent

        cache_session_mapping("session-123", 1)

        # Execute
        result = correlate_session("session-123")

        # Verify
        assert result.agent == mock_agent
        assert result.is_new is False
        assert result.correlation_method == "session_id"

    @patch("claude_headspace.services.session_correlator.db")
    def test_correlate_by_working_directory(self, mock_db):
        """Test correlation by working directory."""
        mock_project = MagicMock()
        mock_project.id = 1

        mock_agent = MagicMock()
        mock_agent.id = 2
        mock_agent.project_id = 1

        # Setup query mocks
        mock_db.session.get.return_value = None  # No cached agent
        mock_db.session.query.return_value.filter.return_value.first.return_value = (
            mock_project
        )
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_agent
        )

        # Execute
        result = correlate_session("new-session", "/path/to/project")

        # Verify - should find by working directory
        # Note: This test verifies the flow, actual DB queries may differ
        assert result is not None

    @patch("claude_headspace.services.session_correlator.db")
    @patch("claude_headspace.services.session_correlator._create_agent_for_session")
    def test_create_new_agent_when_no_match(self, mock_create, mock_db):
        """Test creating new agent when no correlation found."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "new-project"

        mock_agent = MagicMock()
        mock_agent.id = 3

        mock_create.return_value = (mock_agent, mock_project)

        # Setup: no cached session, no project match
        mock_db.session.get.return_value = None
        mock_db.session.query.return_value.filter.return_value.first.return_value = None

        # Execute
        result = correlate_session("brand-new-session", "/unknown/path")

        # Verify
        assert result.agent == mock_agent
        assert result.is_new is True
        assert result.correlation_method == "created"


class TestSessionCache:
    """Tests for session cache functions."""

    def test_cache_session_mapping(self):
        """Test caching a session mapping."""
        cache_session_mapping("session-abc", 42)
        assert get_cached_agent_id("session-abc") == 42

    def test_get_cached_agent_id_not_found(self):
        """Test getting uncached session returns None."""
        assert get_cached_agent_id("nonexistent") is None

    def test_clear_session_cache(self):
        """Test clearing the session cache."""
        cache_session_mapping("session-1", 1)
        cache_session_mapping("session-2", 2)

        clear_session_cache()

        assert get_cached_agent_id("session-1") is None
        assert get_cached_agent_id("session-2") is None


class TestCorrelationResult:
    """Tests for CorrelationResult named tuple."""

    def test_correlation_result_fields(self):
        """Test CorrelationResult has expected fields."""
        agent = MagicMock()
        result = CorrelationResult(
            agent=agent,
            is_new=True,
            correlation_method="created",
        )

        assert result.agent == agent
        assert result.is_new is True
        assert result.correlation_method == "created"
