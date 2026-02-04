"""Route tests for headspace API endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.headspace import headspace_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(headspace_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_monitor():
    monitor = MagicMock()
    monitor.enabled = True
    monitor.get_current_state.return_value = {
        "state": "green",
        "frustration_rolling_10": 2.5,
        "frustration_rolling_30min": 1.8,
        "frustration_rolling_3hr": 2.1,
        "turn_rate_per_hour": 10.0,
        "is_flow_state": False,
        "flow_duration_minutes": None,
        "last_alert_at": None,
        "alert_count_today": 0,
        "alert_suppressed": False,
        "timestamp": "2026-02-02T10:00:00+00:00",
    }
    return monitor


class TestHeadspaceCurrent:

    def test_returns_current_state(self, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}
        resp = client.get("/api/headspace/current")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is True
        assert data["current"]["state"] == "green"
        assert data["current"]["frustration_rolling_3hr"] == 2.1

    def test_disabled_monitor(self, app, client):
        monitor = MagicMock()
        monitor.enabled = False
        app.extensions = {"headspace_monitor": monitor}
        resp = client.get("/api/headspace/current")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is False
        assert data["current"] is None

    def test_no_monitor(self, app, client):
        app.extensions = {}
        resp = client.get("/api/headspace/current")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is False


class TestHeadspaceHistory:

    @patch("src.claude_headspace.routes.headspace.db")
    def test_returns_history(self, mock_db, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}

        mock_snapshot = MagicMock()
        mock_snapshot.timestamp = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        mock_snapshot.state = "green"
        mock_snapshot.frustration_rolling_10 = 2.0
        mock_snapshot.frustration_rolling_30min = 1.5
        mock_snapshot.frustration_rolling_3hr = 1.8
        mock_snapshot.turn_rate_per_hour = 8.0
        mock_snapshot.is_flow_state = False
        mock_snapshot.flow_duration_minutes = None
        mock_snapshot.alert_count_today = 0

        mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_snapshot]

        resp = client.get("/api/headspace/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is True
        assert len(data["history"]) == 1
        assert data["history"][0]["state"] == "green"
        assert data["history"][0]["frustration_rolling_3hr"] == 1.8

    @patch("src.claude_headspace.routes.headspace.db")
    def test_with_since_param(self, mock_db, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}

        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        resp = client.get("/api/headspace/history?since=2026-02-01T00:00:00")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["history"] == []

    @patch("src.claude_headspace.routes.headspace.db")
    def test_with_limit_param(self, mock_db, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}

        mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        resp = client.get("/api/headspace/history?limit=50")
        assert resp.status_code == 200

    @patch("src.claude_headspace.routes.headspace.db")
    def test_limit_capped_at_1000(self, mock_db, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}

        mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        resp = client.get("/api/headspace/history?limit=5000")
        assert resp.status_code == 200
        # The query was called with min(5000, 1000) = 1000
        limit_call = mock_db.session.query.return_value.order_by.return_value.limit
        limit_call.assert_called_with(1000)

    def test_disabled_monitor_returns_empty(self, app, client):
        monitor = MagicMock()
        monitor.enabled = False
        app.extensions = {"headspace_monitor": monitor}
        resp = client.get("/api/headspace/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is False
        assert data["history"] == []


class TestHeadspaceSuppress:

    def test_suppress_alerts(self, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}
        resp = client.post("/api/headspace/suppress", json={"hours": 2})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["suppressed_hours"] == 2
        mock_monitor.suppress_alerts.assert_called_once_with(hours=2)

    def test_suppress_default_1_hour(self, app, client, mock_monitor):
        app.extensions = {"headspace_monitor": mock_monitor}
        resp = client.post("/api/headspace/suppress", content_type="application/json", data="{}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["suppressed_hours"] == 1

    def test_suppress_disabled_monitor(self, app, client):
        monitor = MagicMock()
        monitor.enabled = False
        app.extensions = {"headspace_monitor": monitor}
        resp = client.post("/api/headspace/suppress", json={"hours": 1})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False
