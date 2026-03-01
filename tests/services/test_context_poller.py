"""Tests for ContextPoller service."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.services.context_poller import (
    ContextPoller,
    _compute_tier,
    DEBOUNCE_SECONDS,
)


@contextmanager
def _noop_advisory_lock_or_skip(*args, **kwargs):
    """No-op context manager replacing advisory_lock_or_skip for unit tests."""
    yield True


@pytest.fixture(autouse=True)
def mock_advisory_lock():
    """Mock advisory_lock_or_skip so context poller tests don't need a real database."""
    with patch(
        "src.claude_headspace.services.context_poller.advisory_lock_or_skip",
        side_effect=_noop_advisory_lock_or_skip,
    ):
        yield


# ── Tier computation tests ──────────────────────────────────────────


class TestComputeTier:
    """Test _compute_tier threshold logic."""

    def test_normal_below_warning(self):
        assert _compute_tier(64, 65, 75) == "normal"

    def test_warning_at_threshold(self):
        assert _compute_tier(65, 65, 75) == "warning"

    def test_warning_between_thresholds(self):
        assert _compute_tier(74, 65, 75) == "warning"

    def test_high_at_threshold(self):
        assert _compute_tier(75, 65, 75) == "high"

    def test_high_above_threshold(self):
        assert _compute_tier(90, 65, 75) == "high"

    def test_zero_percent(self):
        assert _compute_tier(0, 65, 75) == "normal"

    def test_100_percent(self):
        assert _compute_tier(100, 65, 75) == "high"


# ── ContextPoller tests ─────────────────────────────────────────────


@pytest.fixture
def mock_app():
    """Create a mock Flask app with app_context."""
    app = MagicMock()
    app.config = {
        "APP_CONFIG": {
            "context_monitor": {
                "enabled": True,
                "poll_interval_seconds": 60,
                "warning_threshold": 65,
                "high_threshold": 75,
            },
        },
    }

    # Create a real context manager for app_context
    class FakeAppContext:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    app.app_context.return_value = FakeAppContext()
    return app


@pytest.fixture
def poller(mock_app):
    """Create a ContextPoller instance (not started)."""
    config = mock_app.config["APP_CONFIG"]
    return ContextPoller(app=mock_app, config=config)


class TestContextPollerInit:
    """Test ContextPoller initialization."""

    def test_defaults(self, poller):
        assert poller._enabled is True
        assert poller._interval == 60
        assert poller._thread is None

    def test_disabled_by_config(self, mock_app):
        config = {"context_monitor": {"enabled": False}}
        p = ContextPoller(app=mock_app, config=config)
        assert p._enabled is False


class TestContextPollerPollOnce:
    """Test poll_once logic."""

    @patch("src.claude_headspace.services.context_poller.tmux_bridge")
    @patch("src.claude_headspace.services.context_poller.parse_context_usage")
    def test_no_active_agents(self, mock_parse, mock_tmux, poller, mock_app):
        """poll_once with no active agents returns 0."""
        with patch.dict("sys.modules", {
            "src.claude_headspace.database": MagicMock(),
            "src.claude_headspace.models.agent": MagicMock(),
        }):
            # Mock the database query to return empty list
            mock_db = MagicMock()
            mock_agent_class = MagicMock()
            mock_db.session.query.return_value.filter.return_value.all.return_value = []

            with patch("src.claude_headspace.services.context_poller.db", mock_db):
                with patch("src.claude_headspace.services.context_poller.Agent", mock_agent_class):
                    result = poller.poll_once()

            assert result == 0

    @patch("src.claude_headspace.services.context_poller.tmux_bridge")
    @patch("src.claude_headspace.services.context_poller.parse_context_usage")
    def test_agent_with_context(self, mock_parse, mock_tmux, poller, mock_app):
        """poll_once with agent that has context data persists to DB."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.tmux_pane_id = "%0"
        mock_agent.ended_at = None
        mock_agent.context_updated_at = None

        mock_tmux.capture_pane.return_value = "[ctx: 42% used, 155k remaining]"
        mock_parse.return_value = {"percent_used": 42, "remaining_tokens": "155k", "raw": "[ctx: 42% used, 155k remaining]"}

        mock_db = MagicMock()
        mock_agent_class = MagicMock()
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]

        with patch("src.claude_headspace.services.context_poller.db", mock_db):
            with patch("src.claude_headspace.services.context_poller.Agent", mock_agent_class):
                result = poller.poll_once()

        assert result == 1
        assert mock_agent.context_percent_used == 42
        assert mock_agent.context_remaining_tokens == "155k"
        assert mock_agent.context_updated_at is not None
        mock_db.session.commit.assert_called_once()

    @patch("src.claude_headspace.services.context_poller.tmux_bridge")
    @patch("src.claude_headspace.services.context_poller.parse_context_usage")
    def test_skips_debounced_agent(self, mock_parse, mock_tmux, poller, mock_app):
        """poll_once skips agent updated less than DEBOUNCE_SECONDS ago."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.tmux_pane_id = "%0"
        mock_agent.ended_at = None
        mock_agent.context_updated_at = datetime.now(timezone.utc) - timedelta(seconds=5)

        mock_db = MagicMock()
        mock_agent_class = MagicMock()
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]

        with patch("src.claude_headspace.services.context_poller.db", mock_db):
            with patch("src.claude_headspace.services.context_poller.Agent", mock_agent_class):
                result = poller.poll_once()

        assert result == 1
        # capture_pane should NOT have been called (debounced)
        mock_tmux.capture_pane.assert_not_called()

    @patch("src.claude_headspace.services.context_poller.tmux_bridge")
    @patch("src.claude_headspace.services.context_poller.parse_context_usage")
    def test_tier_change_triggers_broadcast(self, mock_parse, mock_tmux, poller, mock_app):
        """Tier change from normal to warning triggers card_refresh broadcast."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.tmux_pane_id = "%0"
        mock_agent.ended_at = None
        mock_agent.context_updated_at = None

        # Seed previous tier
        poller._last_tiers[1] = "normal"

        mock_tmux.capture_pane.return_value = "[ctx: 70% used, 80k remaining]"
        mock_parse.return_value = {"percent_used": 70, "remaining_tokens": "80k", "raw": "..."}

        mock_db = MagicMock()
        mock_agent_class = MagicMock()
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]

        with patch("src.claude_headspace.services.context_poller.db", mock_db):
            with patch("src.claude_headspace.services.context_poller.Agent", mock_agent_class):
                with patch("src.claude_headspace.services.context_poller.broadcast_card_refresh") as mock_broadcast:
                    result = poller.poll_once()

        assert result == 1
        mock_broadcast.assert_called_once_with(mock_agent, "context_tier_changed")

    @patch("src.claude_headspace.services.context_poller.tmux_bridge")
    @patch("src.claude_headspace.services.context_poller.parse_context_usage")
    def test_same_tier_no_broadcast(self, mock_parse, mock_tmux, poller, mock_app):
        """Same tier (no change) does NOT trigger card_refresh broadcast."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.tmux_pane_id = "%0"
        mock_agent.ended_at = None
        mock_agent.context_updated_at = None

        # Seed previous tier as warning
        poller._last_tiers[1] = "warning"

        mock_tmux.capture_pane.return_value = "[ctx: 70% used, 80k remaining]"
        mock_parse.return_value = {"percent_used": 70, "remaining_tokens": "80k", "raw": "..."}

        mock_db = MagicMock()
        mock_agent_class = MagicMock()
        mock_db.session.query.return_value.filter.return_value.all.return_value = [mock_agent]

        with patch("src.claude_headspace.services.context_poller.db", mock_db):
            with patch("src.claude_headspace.services.context_poller.Agent", mock_agent_class):
                with patch("src.claude_headspace.services.context_poller.broadcast_card_refresh") as mock_broadcast:
                    poller.poll_once()

        mock_broadcast.assert_not_called()

    @patch("src.claude_headspace.services.context_poller.tmux_bridge")
    @patch("src.claude_headspace.services.context_poller.parse_context_usage")
    def test_config_disabled_skips_polling(self, mock_parse, mock_tmux, poller, mock_app):
        """poll_once returns 0 when config is disabled at runtime."""
        mock_app.config["APP_CONFIG"]["context_monitor"]["enabled"] = False

        mock_db = MagicMock()
        mock_agent_class = MagicMock()

        with patch("src.claude_headspace.services.context_poller.db", mock_db):
            with patch("src.claude_headspace.services.context_poller.Agent", mock_agent_class):
                result = poller.poll_once()

        assert result == 0
        mock_db.session.query.assert_not_called()
