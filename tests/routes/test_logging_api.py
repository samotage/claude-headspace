"""Tests for the API call log route and API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestApiLogPage:
    """Tests for the API log page route."""

    def test_api_log_page_renders(self, client):
        """Test that the API log page renders successfully."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"API Calls" in response.data or b"api-calls-heading" in response.data

    def test_api_log_page_has_filter_controls(self, client):
        """Test that the page has filter dropdown controls."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"filter-endpoint" in response.data
        assert b"filter-method" in response.data
        assert b"filter-status" in response.data
        assert b"filter-auth" in response.data

    def test_api_log_page_has_search_input(self, client):
        """Test that the API log page has a search input."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"filter-search" in response.data
        assert b"Search request" in response.data

    def test_api_log_page_has_table(self, client):
        """Test that the page has the API calls table structure."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"api-calls-table-body" in response.data
        assert b"Timestamp" in response.data
        assert b"Method" in response.data
        assert b"Endpoint" in response.data
        assert b"Status" in response.data
        assert b"Latency" in response.data
        assert b"Source IP" in response.data
        assert b"Auth" in response.data

    def test_api_log_page_includes_javascript(self, client):
        """Test that logging-api.js is included in the page."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"logging-api.js" in response.data

    def test_api_log_page_has_sub_tabs(self, client):
        """Test that the API log page has sub-tab navigation."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"Events" in response.data
        assert b"Inference" in response.data
        assert b"API" in response.data

    def test_api_log_page_has_clear_filters(self, client):
        """Test that the page has Clear Filters button."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"clear-filters-btn" in response.data
        assert b"Clear Filters" in response.data

    def test_api_log_page_has_clear_logs(self, client):
        """Test that the page has Clear All Logs button."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"clear-logs-btn" in response.data
        assert b"Clear All Logs" in response.data

    def test_api_log_page_has_pagination(self, client):
        """Test that the page has pagination controls."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"prev-page-btn" in response.data
        assert b"next-page-btn" in response.data
        assert b"page-indicator" in response.data

    def test_api_log_page_has_states(self, client):
        """Test that the page has all state elements."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"empty-state" in response.data
        assert b"no-results-state" in response.data
        assert b"error-state" in response.data
        assert b"loading-state" in response.data


class TestGetApiCallsAPI:
    """Tests for GET /api/logging/api-calls endpoint."""

    def test_get_api_calls_returns_paginated_results(self, client):
        """Test GET returns paginated API call results."""
        mock_call = MagicMock()
        mock_call.id = 1
        mock_call.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_call.http_method = "POST"
        mock_call.endpoint_path = "/api/remote_agents/create"
        mock_call.query_string = None
        mock_call.request_content_type = "application/json"
        mock_call.request_headers = {"Content-Type": "application/json"}
        mock_call.request_body = '{"name":"test"}'
        mock_call.response_status_code = 200
        mock_call.response_content_type = "application/json"
        mock_call.response_body = '{"id":1}'
        mock_call.latency_ms = 42
        mock_call.source_ip = "192.168.1.1"
        mock_call.auth_status = "authenticated"
        mock_call.project_id = None
        mock_call.agent_id = None

        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 1
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_call]
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "calls" in data
            assert data["page"] == 1
            assert data["per_page"] == 50
            assert "total" in data
            assert "pages" in data
            assert "has_next" in data
            assert "has_previous" in data
            assert len(data["calls"]) == 1
            call = data["calls"][0]
            assert call["http_method"] == "POST"
            assert call["endpoint_path"] == "/api/remote_agents/create"
            assert call["response_status_code"] == 200

    def test_get_api_calls_with_endpoint_filter(self, client):
        """Test GET with endpoint_path filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?endpoint_path=/api/remote_agents/create")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_api_calls_with_method_filter(self, client):
        """Test GET with http_method filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?http_method=POST")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_api_calls_with_status_category_filter(self, client):
        """Test GET with status_category filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?status_category=2xx")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_api_calls_with_auth_status_filter(self, client):
        """Test GET with auth_status filter."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?auth_status=authenticated")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_api_calls_with_search_filter(self, client):
        """Test GET with search filter applies ILIKE across body fields."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?search=test-agent")
            assert response.status_code == 200
            mock_query.filter.assert_called()

    def test_get_api_calls_with_combined_filters(self, client):
        """Test GET with multiple filters combined."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get(
                "/api/logging/api-calls?endpoint_path=/api/remote_agents/create"
                "&http_method=POST&auth_status=authenticated"
            )
            assert response.status_code == 200
            assert mock_query.filter.call_count >= 3

    def test_get_api_calls_pagination(self, client):
        """Test GET with custom pagination parameters."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 100
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?page=2&per_page=25")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 2
            assert data["per_page"] == 25

    def test_get_api_calls_per_page_max_limit(self, client):
        """Test that per_page is capped at 100."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 200
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?per_page=500")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["per_page"] == 100

    def test_get_api_calls_invalid_page(self, client):
        """Test that invalid page defaults to 1."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 10
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls?page=-1")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 1

    def test_get_api_calls_empty(self, client):
        """Test GET returns empty list when no API calls exist."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 0
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            response = client.get("/api/logging/api-calls")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["calls"] == []
            assert data["total"] == 0
            assert data["pages"] == 0

    def test_get_api_calls_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/logging/api-calls")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data

    def test_get_api_calls_has_next_and_previous(self, client):
        """Test that has_next and has_previous are set correctly."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 100
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value = mock_query

            # Page 1 of 2
            response = client.get("/api/logging/api-calls?page=1&per_page=50")
            data = json.loads(response.data)
            assert data["has_next"] is True
            assert data["has_previous"] is False

            # Page 2 of 2
            response = client.get("/api/logging/api-calls?page=2&per_page=50")
            data = json.loads(response.data)
            assert data["has_next"] is False
            assert data["has_previous"] is True


class TestGetApiCallFiltersAPI:
    """Tests for GET /api/logging/api-calls/filters endpoint."""

    def test_get_api_call_filters_returns_options(self, client):
        """Test GET returns available filter options."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = [
                ("/api/remote_agents/create",)
            ]
            mock_db.session.query.return_value.filter.return_value.first.return_value = MagicMock(id=1)

            response = client.get("/api/logging/api-calls/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "endpoints" in data
            assert "methods" in data
            assert "status_categories" in data
            assert "auth_statuses" in data

    def test_get_api_call_filters_empty_when_no_calls(self, client):
        """Test GET returns empty lists when no API calls exist."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.return_value.distinct.return_value.order_by.return_value.all.return_value = []
            mock_db.session.query.return_value.filter.return_value.first.return_value = None

            response = client.get("/api/logging/api-calls/filters")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["endpoints"] == []
            assert data["methods"] == []
            assert data["status_categories"] == []
            assert data["auth_statuses"] == []

    def test_get_api_call_filters_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/logging/api-calls/filters")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data


class TestClearApiCallsAPI:
    """Tests for DELETE /api/logging/api-calls endpoint."""

    def test_clear_api_calls_requires_confirm_header(self, client):
        """Test DELETE requires X-Confirm-Destructive header."""
        response = client.delete("/api/logging/api-calls")
        assert response.status_code == 403

        data = json.loads(response.data)
        assert "X-Confirm-Destructive" in data["error"]

    def test_clear_api_calls_deletes_all(self, client):
        """Test DELETE removes all API call log records."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_query = MagicMock()
            mock_query.count.return_value = 15
            mock_query.delete.return_value = 15
            mock_db.session.query.return_value = mock_query

            response = client.delete(
                "/api/logging/api-calls",
                headers={"X-Confirm-Destructive": "true"},
            )
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["deleted"] == 15
            mock_db.session.commit.assert_called_once()

    def test_clear_api_calls_database_error(self, client):
        """Test that database error returns 500 and rollback is called."""
        with patch("claude_headspace.routes.logging.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.delete(
                "/api/logging/api-calls",
                headers={"X-Confirm-Destructive": "true"},
            )
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data
            mock_db.session.rollback.assert_called_once()


class TestApiLogSubTabs:
    """Tests for API log tab in sub-tab navigation."""

    def test_api_tab_appears_on_events_page(self, client):
        """Test that the API tab appears in sub-tab navigation on events page."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"API" in response.data

    def test_api_tab_appears_on_inference_page(self, client):
        """Test that the API tab appears in sub-tab navigation on inference page."""
        response = client.get("/logging/inference")
        assert response.status_code == 200
        assert b"API" in response.data

    def test_api_tab_active_on_api_page(self, client):
        """Test that the API tab is active on the API log page."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        # The API tab should have aria-selected="true"
        # We check that the page contains the active indicator for the API tab
        html = response.data.decode()
        # Find the API tab link and check if it has aria-current="page"
        assert 'aria-current="page"' in html

    def test_main_nav_active_on_api_page(self, client):
        """Test that the main logging nav tab stays highlighted on API page."""
        response = client.get("/logging/api")
        assert response.status_code == 200
        assert b"tab-link active" in response.data
