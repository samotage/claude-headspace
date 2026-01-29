"""Tests for the logging route and API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest


class TestLoggingPage:
    """Tests for the logging page route."""

    def test_logging_page_renders(self, client):
        """Test that the logging page renders successfully."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"System Events" in response.data or b"events-heading" in response.data

    def test_logging_page_has_filter_controls(self, client):
        """Test that the page has filter dropdown controls."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"filter-project" in response.data
        assert b"filter-agent" in response.data
        assert b"filter-event-type" in response.data

    def test_logging_page_has_clear_filters_button(self, client):
        """Test that the page has a Clear Filters button."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"clear-filters-btn" in response.data
        assert b"Clear Filters" in response.data

    def test_logging_page_has_pagination_controls(self, client):
        """Test that the page has pagination controls."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"prev-page-btn" in response.data
        assert b"next-page-btn" in response.data
        assert b"page-indicator" in response.data

    def test_logging_page_has_event_table(self, client):
        """Test that the page has the event table structure."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"events-table-body" in response.data
        assert b"Timestamp" in response.data
        assert b"Project" in response.data
        assert b"Agent" in response.data
        assert b"Event Type" in response.data

    def test_logging_page_has_empty_state(self, client):
        """Test that the page has empty state elements."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"empty-state" in response.data
        assert b"no-results-state" in response.data

    def test_logging_page_includes_javascript(self, client):
        """Test that logging.js is included in the page."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"logging.js" in response.data

    def test_logging_page_includes_sse_client(self, client):
        """Test that sse-client.js is included in the page."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"sse-client.js" in response.data


class TestGetEventsAPI:
    """Tests for GET /api/events endpoint."""

    def test_get_events_returns_paginated_results(self, client):
        """Test GET returns paginated events."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_event.project_id = 1
        mock_event.agent_id = 1
        mock_event.event_type = "state_transition"
        mock_event.payload = {"from": "idle", "to": "working"}

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test-project"

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.session_uuid = UUID("12345678-1234-5678-1234-567812345678")

        with patch("claude_headspace.routes.logging.db") as mock_db:
            # Main query
            mock_query = MagicMock()
            mock_query.count.return_value = 1
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
            mock_db.session.query.return_value = mock_query

            # Project query
            mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_project]

            response = client.get("/api/events")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "events" in data
            assert data["page"] == 1
            assert data["per_page"] == 50
            assert "total" in data
            assert "pages" in data
            assert "has_next" in data
            assert "has_previous" in data

    def test_get_events_with_project_filter(self, client):
        """Test GET with project_id filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?project_id=1")
            assert response.status_code == 200

            # Verify filter was called
            mock_query.filter.assert_called()

    def test_get_events_with_agent_filter(self, client):
        """Test GET with agent_id filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?agent_id=1")
            assert response.status_code == 200

            mock_query.filter.assert_called()

    def test_get_events_with_event_type_filter(self, client):
        """Test GET with event_type filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?event_type=state_transition")
            assert response.status_code == 200

            mock_query.filter.assert_called()

    def test_get_events_with_combined_filters(self, client):
        """Test GET with multiple filters combined."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?project_id=1&agent_id=2&event_type=state_transition")
            assert response.status_code == 200

            # Filter should be called multiple times for combined filters
            assert mock_query.filter.call_count >= 3

    def test_get_events_pagination(self, client):
        """Test GET with custom pagination parameters."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 100
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?page=2&per_page=25")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 2
            assert data["per_page"] == 25

    def test_get_events_per_page_max_limit(self, client):
        """Test that per_page is capped at 100."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 200
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?per_page=500")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["per_page"] == 100

    def test_get_events_invalid_page(self, client):
        """Test that invalid page defaults to 1."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 10
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?page=-1")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 1

    def test_get_events_empty(self, client):
        """Test GET returns empty list when no events exist."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["events"] == []
            assert data["total"] == 0
            assert data["pages"] == 0

    def test_get_events_calculates_pages_correctly(self, client):
        """Test that total pages is calculated correctly."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 125
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events?per_page=50")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["pages"] == 3  # 125 items / 50 per page = 3 pages

    def test_get_events_has_next_and_previous(self, client):
        """Test that has_next and has_previous are set correctly."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 100
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            # Page 1 of 2
            response = client.get("/api/events?page=1&per_page=50")
            data = json.loads(response.data)
            assert data["has_next"] is True
            assert data["has_previous"] is False

            # Page 2 of 2
            response = client.get("/api/events?page=2&per_page=50")
            data = json.loads(response.data)
            assert data["has_next"] is False
            assert data["has_previous"] is True

    def test_get_events_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/events")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data


class TestGetEventFiltersAPI:
    """Tests for GET /api/events/filters endpoint."""

    def test_get_filters_returns_available_options(self, client):
        """Test GET returns available filter options."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test-project"

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.session_uuid = UUID("12345678-1234-5678-1234-567812345678")

        with patch("claude_headspace.routes.logging.db") as mock_db:
            # Projects query
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = [mock_project]

            # Agents query - need to set up separate return
            mock_agent_query = MagicMock()
            mock_agent_query.join.return_value.distinct.return_value.order_by.return_value.all.return_value = [mock_agent]

            # Event types query
            mock_type_query = MagicMock()
            mock_type_query.distinct.return_value.order_by.return_value.all.return_value = [("state_transition",), ("session_discovered",)]

            response = client.get("/api/events/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "projects" in data
            assert "agents" in data
            assert "event_types" in data

    def test_get_filters_returns_empty_when_no_events(self, client):
        """Test GET returns empty lists when no events exist."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = []
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = []

            response = client.get("/api/events/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["projects"] == []
            assert data["agents"] == []
            assert data["event_types"] == []

    def test_get_filters_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/events/filters")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data


class TestLoggingNavigation:
    """Tests for logging tab navigation."""

    def test_header_has_logging_link(self, client):
        """Test that the dashboard header has the logging link."""
        with patch("claude_headspace.routes.dashboard.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.all.return_value = []

            response = client.get("/")
            assert response.status_code == 200
            assert b'href="/logging"' in response.data

    def test_logging_link_is_active_on_logging_page(self, client):
        """Test that the logging link is marked active on the logging page."""
        response = client.get("/logging")
        assert response.status_code == 200
        # Check that logging link has aria-current="page"
        assert b'aria-current="page"' in response.data

    def test_objective_page_has_logging_link(self, client):
        """Test that the objective page has the logging link."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value.count.return_value = 0

            response = client.get("/objective")
            assert response.status_code == 200
            assert b'href="/logging"' in response.data
