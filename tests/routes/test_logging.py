"""Tests for the logging route and API endpoints."""

import json
from datetime import datetime, timedelta, timezone
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

    def test_logging_page_has_message_column(self, client):
        """Test that the page has the Message column header."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"Message" in response.data

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
        mock_event.turn_id = None
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

    def test_get_events_includes_message_fields(self, client):
        """Test GET returns message and message_actor fields in events."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_event.project_id = None
        mock_event.agent_id = None
        mock_event.turn_id = None
        mock_event.event_type = "state_transition"
        mock_event.payload = {"text": "hello world", "actor": "user"}

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 1
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events")
            assert response.status_code == 200

            data = json.loads(response.data)
            event = data["events"][0]
            assert "message" in event
            assert "message_actor" in event
            assert event["message"] == "hello world"
            assert event["message_actor"] == "user"

    def test_get_events_message_from_turn_data(self, client):
        """Test that message is extracted from Turn when turn_id is present."""
        mock_turn_actor = MagicMock()
        mock_turn_actor.value = "agent"

        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_event.project_id = None
        mock_event.agent_id = None
        mock_event.turn_id = 10
        mock_event.event_type = "turn_detected"
        mock_event.payload = {}

        mock_turn = MagicMock()
        mock_turn.id = 10
        mock_turn.actor = mock_turn_actor
        mock_turn.text = "This is the agent response text"
        mock_turn.summary = "Agent responded"

        with patch("claude_headspace.routes.logging.db") as mock_db:
            # Main event query
            mock_query = MagicMock()
            mock_query.count.return_value = 1
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]

            # Turn query - need to chain filter().all()
            mock_turn_query = MagicMock()
            mock_turn_query.filter.return_value.all.return_value = [mock_turn]

            call_count = 0

            def query_side_effect(*args):
                nonlocal call_count
                call_count += 1
                if args and hasattr(args[0], 'key') and str(args[0]) == 'Turn.id':
                    return mock_turn_query
                return mock_query

            mock_db.session.query.side_effect = None
            mock_db.session.query.return_value = mock_query
            mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_turn]

            response = client.get("/api/events")
            assert response.status_code == 200

            data = json.loads(response.data)
            event = data["events"][0]
            assert "message" in event
            assert "message_actor" in event

    def test_get_events_message_null_when_no_turn_or_payload(self, client):
        """Test that message is null when no turn and no text in payload."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_event.project_id = None
        mock_event.agent_id = None
        mock_event.turn_id = None
        mock_event.event_type = "state_transition"
        mock_event.payload = {"from": "idle", "to": "working"}

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 1
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/events")
            assert response.status_code == 200

            data = json.loads(response.data)
            event = data["events"][0]
            assert event["message"] is None
            assert event["message_actor"] is None

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
        now = datetime.now(timezone.utc)

        # Mock that works for both projects and agents query chains
        # (same mock chain serves both since db.session.query() returns one mock)
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.name = "test-project"
        mock_item.session_uuid = UUID("12345678-1234-5678-1234-567812345678")
        mock_item.ended_at = None
        mock_item.last_seen_at = now

        with patch("claude_headspace.routes.logging.db") as mock_db:
            # Both projects and agents queries use join().distinct().order_by().all()
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = [mock_item]

            # Event types query uses distinct().order_by().all() (no join)
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = [("state_transition",), ("session_discovered",)]

            response = client.get("/api/events/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "projects" in data
            assert "agents" in data
            assert "event_types" in data

    def test_get_filters_agents_include_is_active(self, client):
        """Test that agent filter items include is_active and last_seen_at fields."""
        now = datetime.now(timezone.utc)

        # These mocks serve both projects and agents query chains
        mock_active_agent = MagicMock()
        mock_active_agent.id = 1
        mock_active_agent.name = "proj-a"
        mock_active_agent.session_uuid = UUID("11111111-1111-1111-1111-111111111111")
        mock_active_agent.ended_at = None
        mock_active_agent.last_seen_at = now

        mock_inactive_agent = MagicMock()
        mock_inactive_agent.id = 2
        mock_inactive_agent.name = "proj-b"
        mock_inactive_agent.session_uuid = UUID("22222222-2222-2222-2222-222222222222")
        mock_inactive_agent.ended_at = None
        mock_inactive_agent.last_seen_at = now - timedelta(minutes=10)

        mock_ended_agent = MagicMock()
        mock_ended_agent.id = 3
        mock_ended_agent.name = "proj-c"
        mock_ended_agent.session_uuid = UUID("33333333-3333-3333-3333-333333333333")
        mock_ended_agent.ended_at = now
        mock_ended_agent.last_seen_at = now

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = [
                mock_active_agent, mock_inactive_agent, mock_ended_agent
            ]
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = []

            response = client.get("/api/events/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            agents = data["agents"]

            # All agents should have is_active and last_seen_at fields
            for agent in agents:
                assert "is_active" in agent
                assert "last_seen_at" in agent

    def test_get_filters_agents_active_status_logic(self, client):
        """Test is_active is True only when not ended and seen within timeout."""
        now = datetime.now(timezone.utc)

        # Active: not ended, seen recently
        mock_active = MagicMock()
        mock_active.id = 1
        mock_active.name = "test-proj"
        mock_active.session_uuid = UUID("11111111-1111-1111-1111-111111111111")
        mock_active.ended_at = None
        mock_active.last_seen_at = now

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = [mock_active]
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = []

            response = client.get("/api/events/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            agents = data["agents"]
            assert len(agents) >= 1
            assert agents[0]["is_active"] is True

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


class TestExtractMessageHelpers:
    """Tests for _extract_message and _extract_message_actor helper functions."""

    def test_extract_message_from_payload_text(self):
        """Test message extraction from event payload text field."""
        from claude_headspace.routes.logging import _extract_message

        event = MagicMock()
        event.turn_id = None
        event.payload = {"text": "hello world"}

        result = _extract_message(event, {})
        assert result == "hello world"

    def test_extract_message_truncates_long_payload_text(self):
        """Test that payload text is truncated to 200 chars."""
        from claude_headspace.routes.logging import _extract_message

        event = MagicMock()
        event.turn_id = None
        event.payload = {"text": "x" * 300}

        result = _extract_message(event, {})
        assert len(result) == 200

    def test_extract_message_from_turn_data(self):
        """Test message extraction from turn data when turn_id present."""
        from claude_headspace.routes.logging import _extract_message

        event = MagicMock()
        event.turn_id = 5
        event.payload = {"text": "payload text"}

        turn_data = {5: {"actor": "user", "text": "Turn summary text"}}

        result = _extract_message(event, turn_data)
        assert result == "Turn summary text"

    def test_extract_message_returns_none_when_no_data(self):
        """Test message is None when no turn and no payload text."""
        from claude_headspace.routes.logging import _extract_message

        event = MagicMock()
        event.turn_id = None
        event.payload = {"from": "idle", "to": "working"}

        result = _extract_message(event, {})
        assert result is None

    def test_extract_message_returns_none_for_null_payload(self):
        """Test message is None when payload is None."""
        from claude_headspace.routes.logging import _extract_message

        event = MagicMock()
        event.turn_id = None
        event.payload = None

        result = _extract_message(event, {})
        assert result is None

    def test_extract_message_actor_from_payload(self):
        """Test actor extraction from event payload."""
        from claude_headspace.routes.logging import _extract_message_actor

        event = MagicMock()
        event.turn_id = None
        event.payload = {"actor": "user"}

        result = _extract_message_actor(event, {})
        assert result == "user"

    def test_extract_message_actor_from_turn_data(self):
        """Test actor extraction from turn data."""
        from claude_headspace.routes.logging import _extract_message_actor

        event = MagicMock()
        event.turn_id = 5
        event.payload = {"actor": "should-not-use"}

        turn_data = {5: {"actor": "agent", "text": "some text"}}

        result = _extract_message_actor(event, turn_data)
        assert result == "agent"

    def test_extract_message_actor_returns_none_when_no_data(self):
        """Test actor is None when no turn and no actor in payload."""
        from claude_headspace.routes.logging import _extract_message_actor

        event = MagicMock()
        event.turn_id = None
        event.payload = {"from": "idle"}

        result = _extract_message_actor(event, {})
        assert result is None


class TestInferenceLogPage:
    """Tests for the inference log page route."""

    def test_inference_log_page_renders(self, client):
        """Test that the inference log page renders successfully."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"Inference Calls" in response.data or b"inference-heading" in response.data

    def test_inference_log_page_has_filter_controls(self, client):
        """Test that the page has filter dropdown controls."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"filter-level" in response.data
        assert b"filter-model" in response.data
        assert b"filter-project" in response.data
        assert b"filter-cached" in response.data

    def test_inference_log_page_has_table(self, client):
        """Test that the page has the inference table structure."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"inference-table-body" in response.data
        assert b"Timestamp" in response.data
        assert b"Level" in response.data
        assert b"Model" in response.data
        assert b"Purpose" in response.data
        assert b"Tokens" in response.data
        assert b"Latency" in response.data
        assert b"Cost" in response.data
        assert b"Status" in response.data

    def test_inference_log_page_includes_javascript(self, client):
        """Test that logging-inference.js is included in the page."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"logging-inference.js" in response.data

    def test_inference_log_page_has_search_input(self, client):
        """Test that the inference log page has a search input."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"filter-search" in response.data
        assert b"Search prompts" in response.data

    def test_inference_log_page_has_sub_tabs(self, client):
        """Test that the inference log page has sub-tab navigation."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"Events" in response.data
        assert b"Inference" in response.data


class TestGetInferenceCallsAPI:
    """Tests for GET /api/inference/calls endpoint."""

    def test_get_inference_calls_returns_paginated_results(self, client):
        """Test GET returns paginated inference calls."""
        mock_call = MagicMock()
        mock_call.id = 1
        mock_call.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_call.level = "turn"
        mock_call.purpose = "Turn summary"
        mock_call.model = "anthropic/claude-3-haiku"
        mock_call.input_tokens = 500
        mock_call.output_tokens = 100
        mock_call.latency_ms = 342
        mock_call.cost = 0.0023
        mock_call.cached = False
        mock_call.error_message = None
        mock_call.input_text = "Summarise this turn"
        mock_call.result_text = "Summary text"
        mock_call.project_id = 1
        mock_call.agent_id = 1

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test-project"

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.session_uuid = "abcd1234-5678-9012-3456-789012345678"

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 1
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_call]
            mock_db.session.query.return_value = mock_query
            # filter().all() is called twice: once for projects, once for agents
            mock_db.session.query.return_value.filter.return_value.all.side_effect = [
                [mock_project], [mock_agent]
            ]

            response = client.get("/api/inference/calls")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "calls" in data
            assert data["page"] == 1
            assert data["per_page"] == 50
            assert "total" in data
            assert "pages" in data
            assert "has_next" in data
            assert "has_previous" in data

    def test_get_inference_calls_with_level_filter(self, client):
        """Test GET with level filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?level=turn")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_inference_calls_with_model_filter(self, client):
        """Test GET with model filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?model=some-model")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_inference_calls_with_cached_filter(self, client):
        """Test GET with cached filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?cached=true")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_inference_calls_pagination_limits(self, client):
        """Test that per_page is capped at 100."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 200
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?per_page=500")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["per_page"] == 100

    def test_get_inference_calls_empty(self, client):
        """Test GET returns empty list when no inference calls exist."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["calls"] == []
            assert data["total"] == 0
            assert data["pages"] == 0

    def test_get_inference_calls_invalid_page(self, client):
        """Test that invalid page defaults to 1."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 10
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?page=-1")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 1

    def test_get_inference_calls_with_search_filter(self, client):
        """Test GET with search filter applies ILIKE across text fields."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?search=waiting+for+input")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_inference_calls_with_search_and_other_filters(self, client):
        """Test GET with search combined with other filters."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/inference/calls?search=summary&level=turn")
            assert response.status_code == 200
            # filter should be called at least twice (search + level)
            assert mock_query.filter.call_count >= 2

    def test_get_inference_calls_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/inference/calls")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data


class TestGetInferenceCallFiltersAPI:
    """Tests for GET /api/inference/calls/filters endpoint."""

    def test_get_inference_filters_returns_options(self, client):
        """Test GET returns available filter options."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test-project"

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = [("turn",)]
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = [mock_project]

            response = client.get("/api/inference/calls/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "levels" in data
            assert "models" in data
            assert "projects" in data

    def test_get_inference_filters_empty_when_no_calls(self, client):
        """Test GET returns empty lists when no inference calls exist."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = []
            mock_db.session.query.return_value.join.return_value.distinct.return_value.order_by.return_value.all.return_value = []

            response = client.get("/api/inference/calls/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["levels"] == []
            assert data["models"] == []
            assert data["projects"] == []

    def test_get_inference_filters_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/inference/calls/filters")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data


class TestClearEventsAPI:
    """Tests for DELETE /api/events endpoint."""

    def test_clear_events_requires_confirm_header(self, client):
        """Test DELETE requires X-Confirm-Destructive header."""
        response = client.delete("/api/events")
        assert response.status_code == 403

        data = json.loads(response.data)
        assert "X-Confirm-Destructive" in data["error"]

    def test_clear_events_deletes_all(self, client):
        """Test DELETE removes all event records."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 10
            mock_query.delete.return_value = 10
            mock_db.session.query.return_value = mock_query

            response = client.delete(
                "/api/events",
                headers={"X-Confirm-Destructive": "true"},
            )
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["deleted"] == 10
            mock_db.session.commit.assert_called_once()

    def test_clear_events_database_error(self, client):
        """Test that database error returns 500 and rollback is called."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.delete(
                "/api/events",
                headers={"X-Confirm-Destructive": "true"},
            )
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data
            mock_db.session.rollback.assert_called_once()


class TestClearInferenceCallsAPI:
    """Tests for DELETE /api/inference/calls endpoint."""

    def test_clear_inference_calls_requires_confirm_header(self, client):
        """Test DELETE requires X-Confirm-Destructive header."""
        response = client.delete("/api/inference/calls")
        assert response.status_code == 403

        data = json.loads(response.data)
        assert "X-Confirm-Destructive" in data["error"]

    def test_clear_inference_calls_deletes_all(self, client):
        """Test DELETE removes all inference call records."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 5
            mock_query.delete.return_value = 5
            mock_db.session.query.return_value = mock_query

            response = client.delete(
                "/api/inference/calls",
                headers={"X-Confirm-Destructive": "true"},
            )
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["deleted"] == 5
            mock_db.session.commit.assert_called_once()

    def test_clear_inference_calls_database_error(self, client):
        """Test that database error returns 500 and rollback is called."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.delete(
                "/api/inference/calls",
                headers={"X-Confirm-Destructive": "true"},
            )
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data
            mock_db.session.rollback.assert_called_once()


class TestLoggingSubTabs:
    """Tests for logging sub-tab navigation across both pages."""

    def test_events_page_has_sub_tabs(self, client):
        """Test that the events page has sub-tab navigation."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"Events" in response.data
        assert b"Inference" in response.data

    def test_main_nav_active_on_inference_page(self, client):
        """Test that the main logging nav tab stays highlighted on inference page."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        # The main header nav should have the logging tab marked as active
        assert b'class="tab-link active"' in response.data or b"tab-link active" in response.data
