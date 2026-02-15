"""Unit tests for HeadspaceMonitor service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.claude_headspace.services.headspace_monitor import (
    HeadspaceMonitor,
    GENTLE_ALERTS_DEFAULT,
    FLOW_MESSAGES_DEFAULT,
)


@pytest.fixture
def mock_app():
    """Minimal Flask app mock with app_context."""
    mock = MagicMock()
    mock.app_context.return_value.__enter__ = MagicMock()
    mock.app_context.return_value.__exit__ = MagicMock(return_value=False)
    return mock


@pytest.fixture
def config():
    return {
        "headspace": {
            "enabled": True,
            "thresholds": {"yellow": 4, "red": 7},
            "alert_cooldown_minutes": 10,
            "snapshot_retention_days": 7,
            "flow_detection": {
                "min_turn_rate": 6,
                "max_frustration": 3,
                "min_duration_minutes": 15,
            },
        }
    }


@pytest.fixture
def monitor(mock_app, config):
    return HeadspaceMonitor(app=mock_app, config=config)


class TestConfiguration:

    def test_enabled_from_config(self, mock_app):
        config = {"headspace": {"enabled": True}}
        m = HeadspaceMonitor(app=mock_app, config=config)
        assert m.enabled is True

    def test_disabled_from_config(self, mock_app):
        config = {"headspace": {"enabled": False}}
        m = HeadspaceMonitor(app=mock_app, config=config)
        assert m.enabled is False

    def test_default_enabled(self, mock_app):
        m = HeadspaceMonitor(app=mock_app, config={})
        assert m.enabled is True

    def test_thresholds_from_config(self, monitor):
        assert monitor._yellow_threshold == 4
        assert monitor._red_threshold == 7

    def test_flow_detection_from_config(self, monitor):
        assert monitor._flow_min_turn_rate == 6
        assert monitor._flow_max_frustration == 3
        assert monitor._flow_min_duration == 15

    def test_session_rolling_window_default(self, mock_app):
        m = HeadspaceMonitor(app=mock_app, config={})
        assert m._session_rolling_window_minutes == 180

    def test_session_rolling_window_from_config(self, mock_app):
        config = {"headspace": {"session_rolling_window_minutes": 60}}
        m = HeadspaceMonitor(app=mock_app, config=config)
        assert m._session_rolling_window_minutes == 60

    def test_custom_messages(self, mock_app):
        config = {
            "headspace": {
                "messages": {
                    "gentle_alerts": ["Custom alert"],
                    "flow_messages": ["Custom flow"],
                }
            }
        }
        m = HeadspaceMonitor(app=mock_app, config=config)
        assert m._gentle_alerts == ["Custom alert"]
        assert m._flow_messages == ["Custom flow"]


class TestDetermineState:

    def test_green_when_no_averages(self, monitor):
        assert monitor._determine_state(None, None) == "green"

    def test_green_when_below_yellow(self, monitor):
        assert monitor._determine_state(2.0, 3.0) == "green"

    def test_yellow_when_above_threshold(self, monitor):
        assert monitor._determine_state(5.0, 3.0) == "yellow"

    def test_yellow_from_30min(self, monitor):
        assert monitor._determine_state(2.0, 5.0) == "yellow"

    def test_red_when_above_threshold(self, monitor):
        assert monitor._determine_state(8.0, 3.0) == "red"

    def test_red_from_30min(self, monitor):
        assert monitor._determine_state(2.0, 7.5) == "red"

    def test_only_rolling_10(self, monitor):
        assert monitor._determine_state(5.0, None) == "yellow"
        assert monitor._determine_state(8.0, None) == "red"
        assert monitor._determine_state(2.0, None) == "green"

    def test_only_rolling_30min(self, monitor):
        assert monitor._determine_state(None, 5.0) == "yellow"
        assert monitor._determine_state(None, 8.0) == "red"
        assert monitor._determine_state(None, 2.0) == "green"


class TestDetectFlow:

    def test_no_flow_when_no_averages(self, monitor):
        is_flow, duration = monitor._detect_flow(None, None, 10.0, datetime.now(timezone.utc))
        assert is_flow is False
        assert duration is None

    def test_no_flow_when_frustration_too_high(self, monitor):
        is_flow, duration = monitor._detect_flow(5.0, 5.0, 10.0, datetime.now(timezone.utc))
        assert is_flow is False

    def test_no_flow_when_turn_rate_too_low(self, monitor):
        is_flow, duration = monitor._detect_flow(1.0, 1.0, 3.0, datetime.now(timezone.utc))
        assert is_flow is False

    def test_flow_detected_after_min_duration(self, monitor):
        now = datetime.now(timezone.utc)
        # First call starts the flow timer
        monitor._detect_flow(1.0, 1.0, 10.0, now - timedelta(minutes=20))
        # After enough time, flow is detected
        is_flow, duration = monitor._detect_flow(1.0, 1.0, 10.0, now)
        assert is_flow is True
        assert duration >= 15

    def test_flow_resets_on_high_frustration(self, monitor):
        now = datetime.now(timezone.utc)
        # Start flow
        monitor._detect_flow(1.0, 1.0, 10.0, now - timedelta(minutes=20))
        # High frustration resets it
        monitor._detect_flow(5.0, 5.0, 10.0, now)
        assert monitor._flow_start is None

    def test_flow_uses_min_of_averages(self, monitor):
        now = datetime.now(timezone.utc)
        # rolling_10=2, rolling_30min=5 → min is 2 (below max_frustration 3)
        monitor._detect_flow(2.0, 5.0, 10.0, now - timedelta(minutes=20))
        is_flow, _ = monitor._detect_flow(2.0, 5.0, 10.0, now)
        assert is_flow is True


class TestAlertSuppression:

    def test_suppress_alerts(self, monitor):
        assert monitor._is_suppressed() is False
        monitor.suppress_alerts(hours=1)
        assert monitor._is_suppressed() is True

    def test_suppression_expires(self, monitor):
        monitor._suppressed_until = datetime.now(timezone.utc) - timedelta(hours=1)
        assert monitor._is_suppressed() is False


class TestAlertCooldown:

    def test_not_in_cooldown_initially(self, monitor):
        assert monitor._is_in_cooldown(datetime.now(timezone.utc)) is False

    def test_in_cooldown_after_alert(self, monitor):
        now = datetime.now(timezone.utc)
        monitor._last_alert_at = now - timedelta(minutes=5)
        assert monitor._is_in_cooldown(now) is True

    def test_cooldown_expires(self, monitor):
        now = datetime.now(timezone.utc)
        monitor._last_alert_at = now - timedelta(minutes=15)
        assert monitor._is_in_cooldown(now) is False


class TestDailyAlertCount:

    def test_count_increments(self, monitor):
        now = datetime.now(timezone.utc)
        monitor._update_daily_alert_count(now)
        assert monitor._alert_count_today == 1
        monitor._update_daily_alert_count(now)
        assert monitor._alert_count_today == 2

    def test_count_resets_on_new_day(self, monitor):
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        monitor._update_daily_alert_count(yesterday)
        assert monitor._alert_count_today == 1

        today = datetime.now(timezone.utc)
        monitor._update_daily_alert_count(today)
        assert monitor._alert_count_today == 1  # Reset


class TestCalcRollingWindows:

    @patch("src.claude_headspace.services.headspace_monitor.db")
    def test_returns_none_when_no_turns(self, mock_db, monitor):
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        r10, r30, r3h = monitor._calc_rolling_windows(datetime.now(timezone.utc))
        assert r10 is None
        assert r30 is None
        assert r3h is None

    @patch("src.claude_headspace.services.headspace_monitor.db")
    def test_returns_averages_of_scored_turns(self, mock_db, monitor):
        now = datetime.now(timezone.utc)
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (2, now - timedelta(minutes=1)),
            (4, now - timedelta(minutes=5)),
            (6, now - timedelta(minutes=10)),
        ]
        r10, r30, r3h = monitor._calc_rolling_windows(now)
        assert r10 == 4.0
        assert r30 == 4.0
        assert r3h == 4.0

    @patch("src.claude_headspace.services.headspace_monitor.db")
    def test_single_turn(self, mock_db, monitor):
        now = datetime.now(timezone.utc)
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (7, now - timedelta(minutes=1)),
        ]
        r10, r30, r3h = monitor._calc_rolling_windows(now)
        assert r10 == 7.0
        assert r30 == 7.0
        assert r3h == 7.0

    def test_uses_config_window(self, mock_app):
        config = {"headspace": {"session_rolling_window_minutes": 60}}
        m = HeadspaceMonitor(app=mock_app, config=config)
        assert m._session_rolling_window_minutes == 60


class TestRecalculate:

    def test_disabled_monitor_skips(self, mock_app):
        config = {"headspace": {"enabled": False}}
        monitor = HeadspaceMonitor(app=mock_app, config=config)
        turn = MagicMock()
        # Should not raise
        monitor.recalculate(turn)

    @patch("src.claude_headspace.services.headspace_monitor.db")
    def test_recalculate_creates_snapshot(self, mock_db, monitor):
        mock_turn = MagicMock()
        mock_turn.frustration_score = 3

        now = datetime.now(timezone.utc)

        # Mock consolidated rolling windows query (returns (score, timestamp) tuples)
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (3, now - timedelta(minutes=1)),
            (2, now - timedelta(minutes=5)),
            (4, now - timedelta(minutes=10)),
        ]
        # Mock turn rate count
        mock_db.session.query.return_value.filter.return_value.count.return_value = 5
        # Mock rising trend query (limit chain)
        mock_db.session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            (3,), (2,), (4,), (3,), (2,),
        ]

        # Prune returns 0
        mock_db.session.query.return_value.filter.return_value.delete.return_value = 0

        with patch.object(monitor, "_broadcast_state_update"):
            with patch.object(monitor, "_broadcast_alert"):
                with patch.object(monitor, "_maybe_broadcast_flow"):
                    monitor.recalculate(mock_turn)

        # Verify snapshot was added
        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called()


class TestGetCurrentState:

    @patch("src.claude_headspace.services.headspace_monitor.db")
    def test_no_snapshots_returns_default(self, mock_db, monitor):
        mock_db.session.query.return_value.order_by.return_value.first.return_value = None
        state = monitor.get_current_state()
        assert state["state"] == "green"
        assert state["frustration_rolling_10"] is None
        assert state["frustration_rolling_3hr"] is None
        assert state["is_flow_state"] is False

    @patch("src.claude_headspace.services.headspace_monitor.db")
    def test_returns_latest_snapshot(self, mock_db, monitor):
        mock_snapshot = MagicMock()
        mock_snapshot.state = "yellow"
        mock_snapshot.frustration_rolling_10 = 5.0
        mock_snapshot.frustration_rolling_30min = 4.0
        mock_snapshot.frustration_rolling_3hr = 3.5
        mock_snapshot.turn_rate_per_hour = 8.0
        mock_snapshot.is_flow_state = False
        mock_snapshot.flow_duration_minutes = None
        mock_snapshot.last_alert_at = None
        mock_snapshot.alert_count_today = 1
        mock_snapshot.timestamp = datetime.now(timezone.utc)

        mock_db.session.query.return_value.order_by.return_value.first.return_value = mock_snapshot
        state = monitor.get_current_state()
        assert state["state"] == "yellow"
        assert state["frustration_rolling_10"] == 5.0
        assert state["frustration_rolling_3hr"] == 3.5
