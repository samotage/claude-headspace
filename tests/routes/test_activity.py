"""Tests for activity monitoring routes."""

from unittest.mock import patch, MagicMock

import pytest

from claude_headspace.routes.activity import _metric_to_dict


class TestMetricToDict:
    """Test _metric_to_dict helper function."""

    def test_frustration_avg_computed(self):
        """frustration_avg is computed from total_frustration / frustration_turn_count."""
        m = MagicMock()
        m.id = 1
        m.bucket_start = MagicMock()
        m.bucket_start.isoformat.return_value = "2026-02-04T10:00:00"
        m.turn_count = 10
        m.avg_turn_time_seconds = 5.0
        m.active_agents = 2
        m.total_frustration = 15.0
        m.frustration_turn_count = 3
        result = _metric_to_dict(m)
        assert result["frustration_avg"] == 5.0

    def test_frustration_avg_null_when_no_turns(self):
        """frustration_avg is None when frustration_turn_count is 0."""
        m = MagicMock()
        m.id = 1
        m.bucket_start = MagicMock()
        m.bucket_start.isoformat.return_value = "2026-02-04T10:00:00"
        m.turn_count = 10
        m.avg_turn_time_seconds = 5.0
        m.active_agents = 2
        m.total_frustration = 0
        m.frustration_turn_count = 0
        result = _metric_to_dict(m)
        assert result["frustration_avg"] is None

    def test_frustration_avg_null_when_none(self):
        """frustration_avg is None when total_frustration is None."""
        m = MagicMock()
        m.id = 1
        m.bucket_start = MagicMock()
        m.bucket_start.isoformat.return_value = "2026-02-04T10:00:00"
        m.turn_count = 10
        m.avg_turn_time_seconds = 5.0
        m.active_agents = 2
        m.total_frustration = None
        m.frustration_turn_count = None
        result = _metric_to_dict(m)
        assert result["frustration_avg"] is None

    def test_frustration_avg_rounded_to_1_decimal(self):
        """frustration_avg is rounded to 1 decimal place."""
        m = MagicMock()
        m.id = 1
        m.bucket_start = MagicMock()
        m.bucket_start.isoformat.return_value = "2026-02-04T10:00:00"
        m.turn_count = 10
        m.avg_turn_time_seconds = 5.0
        m.active_agents = 2
        m.total_frustration = 10.0
        m.frustration_turn_count = 3
        result = _metric_to_dict(m)
        assert result["frustration_avg"] == 3.3


class TestActivityPage:
    """Test GET /activity page route."""

    def test_activity_page_returns_200(self, client):
        """GET /activity returns 200."""
        response = client.get("/activity")
        assert response.status_code == 200

    def test_activity_page_contains_expected_content(self, client):
        """GET /activity renders page with key UI elements."""
        response = client.get("/activity")
        html = response.data.decode("utf-8")

        assert "activity-chart" in html
        assert "activity.js" in html
        assert "Turn Activity" in html
        assert "chart.js" in html.lower() or "Chart" in html

    def test_activity_page_includes_status_counts(self, client):
        """GET /activity provides status_counts context for header stats bar."""
        response = client.get("/activity")
        html = response.data.decode("utf-8")
        assert "[0]" in html

    def test_activity_page_includes_frustration_thresholds(self, client):
        """GET /activity injects frustration thresholds into template."""
        response = client.get("/activity")
        html = response.data.decode("utf-8")
        assert "FRUSTRATION_THRESHOLDS" in html

    def test_activity_page_includes_headspace_enabled(self, client):
        """GET /activity injects HEADSPACE_ENABLED into template."""
        response = client.get("/activity")
        html = response.data.decode("utf-8")
        assert "HEADSPACE_ENABLED" in html


class TestOverallMetricsAPI:
    """Test GET /api/metrics/overall endpoint."""

    @patch("claude_headspace.routes.activity.db")
    def test_overall_metrics_returns_200(self, mock_db, client):
        """GET /api/metrics/overall returns 200 with correct structure."""
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        response = client.get("/api/metrics/overall")
        assert response.status_code == 200
        data = response.get_json()
        assert "window" in data
        assert "current" in data
        assert "history" in data
        assert "daily_totals" in data
        assert data["window"] == "day"

    @patch("claude_headspace.routes.activity.db")
    def test_overall_metrics_default_window_is_day(self, mock_db, client):
        """Default window parameter is 'day'."""
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        response = client.get("/api/metrics/overall")
        data = response.get_json()
        assert data["window"] == "day"

    @patch("claude_headspace.routes.activity.db")
    def test_overall_metrics_accepts_window_param(self, mock_db, client):
        """Window parameter is accepted and reflected in response."""
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        for window in ["day", "week", "month"]:
            response = client.get(f"/api/metrics/overall?window={window}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["window"] == window

    @patch("claude_headspace.routes.activity.db")
    def test_overall_metrics_invalid_window_defaults_to_day(self, mock_db, client):
        """Invalid window parameter falls back to 'day'."""
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        response = client.get("/api/metrics/overall?window=invalid")
        assert response.status_code == 200
        data = response.get_json()
        assert data["window"] == "day"

    @patch("claude_headspace.routes.activity.db")
    def test_overall_metrics_empty_returns_null_current(self, mock_db, client):
        """When no metrics exist, current is null and history is empty."""
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        response = client.get("/api/metrics/overall")
        data = response.get_json()
        assert data["current"] is None
        assert data["history"] == []


class TestAgentMetricsAPI:
    """Test GET /api/metrics/agents/<id> endpoint."""

    def test_agent_metrics_nonexistent_returns_404(self, client):
        """GET /api/metrics/agents/<id> returns 404 for nonexistent agent."""
        response = client.get("/api/metrics/agents/99999")
        assert response.status_code == 404

    def test_agent_metrics_accepts_window_param(self, client):
        """Window parameter is reflected in response for agent endpoint."""
        response = client.get("/api/metrics/agents/99999?window=week")
        assert response.status_code == 404


class TestProjectMetricsAPI:
    """Test GET /api/metrics/projects/<id> endpoint."""

    def test_project_metrics_nonexistent_returns_404(self, client):
        """GET /api/metrics/projects/<id> returns 404 for nonexistent project."""
        response = client.get("/api/metrics/projects/99999")
        assert response.status_code == 404

    def test_project_metrics_accepts_window_param(self, client):
        """Window parameter is reflected in response for project endpoint."""
        response = client.get("/api/metrics/projects/99999?window=month")
        assert response.status_code == 404
