"""Tests for the agent reaper service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.services.agent_reaper import (
    AgentReaper,
    ReapDetail,
    ReapResult,
    DEFAULT_GRACE_PERIOD_SECONDS,
    DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
    DEFAULT_INTERVAL_SECONDS,
)
from claude_headspace.services.iterm_focus import PaneStatus

# Patch targets — these are local imports inside agent_reaper methods,
# so we patch at the source module, not at agent_reaper's namespace.
PATCH_CHECK_PANE = "claude_headspace.services.iterm_focus.check_pane_exists"
PATCH_DB = "claude_headspace.database.db"
PATCH_BROADCASTER = "claude_headspace.services.broadcaster.get_broadcaster"


def _make_agent(
    agent_id=1,
    iterm_pane_id=None,
    tmux_pane_id=None,
    started_at=None,
    last_seen_at=None,
    ended_at=None,
    project_id=1,
):
    """Create a mock Agent object."""
    now = datetime.now(timezone.utc)
    agent = MagicMock()
    agent.id = agent_id
    agent.session_uuid = uuid4()
    agent.iterm_pane_id = iterm_pane_id
    agent.tmux_pane_id = tmux_pane_id
    agent.started_at = started_at or (now - timedelta(minutes=30))
    agent.last_seen_at = last_seen_at or (now - timedelta(minutes=10))
    agent.ended_at = ended_at
    agent.project_id = project_id
    return agent


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config = {"APP_CONFIG": {}}
    app.extensions = {}
    # Make app_context return a context manager
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=None)
    ctx.__exit__ = MagicMock(return_value=False)
    app.app_context.return_value = ctx
    return app


@pytest.fixture
def config():
    return {
        "reaper": {
            "enabled": True,
            "interval_seconds": 60,
            "inactivity_timeout_seconds": 300,
            "grace_period_seconds": 300,
        }
    }


@pytest.fixture
def reaper(mock_app, config):
    return AgentReaper(app=mock_app, config=config)


class TestReaperInit:
    def test_default_config(self, mock_app):
        reaper = AgentReaper(app=mock_app, config={})
        assert reaper._interval == DEFAULT_INTERVAL_SECONDS
        assert reaper._inactivity_timeout == DEFAULT_INACTIVITY_TIMEOUT_SECONDS
        assert reaper._grace_period == DEFAULT_GRACE_PERIOD_SECONDS
        assert reaper._enabled is True

    def test_custom_config(self, mock_app):
        config = {
            "reaper": {
                "enabled": False,
                "interval_seconds": 30,
                "inactivity_timeout_seconds": 120,
                "grace_period_seconds": 60,
            }
        }
        reaper = AgentReaper(app=mock_app, config=config)
        assert reaper._interval == 30
        assert reaper._inactivity_timeout == 120
        assert reaper._grace_period == 60
        assert reaper._enabled is False


class TestReaperStartStop:
    def test_start_creates_thread(self, reaper):
        reaper.start()
        assert reaper._thread is not None
        assert reaper._thread.is_alive()
        reaper.stop()

    def test_start_disabled_does_nothing(self, mock_app):
        config = {"reaper": {"enabled": False}}
        reaper = AgentReaper(app=mock_app, config=config)
        reaper.start()
        assert reaper._thread is None

    def test_stop_sets_event(self, reaper):
        reaper.start()
        assert not reaper._stop_event.is_set()
        reaper.stop()
        assert reaper._stop_event.is_set()

    def test_double_start_warns(self, reaper):
        reaper.start()
        reaper.start()  # should warn, not crash
        reaper.stop()


class TestReapOnce:
    """Tests for the core reap_once() logic."""

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_no_agents_returns_empty_result(self, mock_db, mock_check, reaper):
        mock_db.session.query.return_value.filter.return_value.all.return_value = []

        result = reaper.reap_once()

        assert result.checked == 0
        assert result.reaped == 0

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_grace_period_skips_new_agent(self, mock_db, mock_check, reaper):
        """Agent created 1 minute ago should be skipped."""
        now = datetime.now(timezone.utc)
        agent = _make_agent(started_at=now - timedelta(minutes=1))
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]

        result = reaper.reap_once()

        assert result.checked == 1
        assert result.skipped_grace == 1
        assert result.reaped == 0
        mock_check.assert_not_called()

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_pane_found_skips_agent(self, mock_db, mock_check, reaper):
        """Agent with existing iTerm pane should not be reaped."""
        agent = _make_agent(iterm_pane_id="pty-123")
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]
        mock_check.return_value = PaneStatus.FOUND

        result = reaper.reap_once()

        assert result.checked == 1
        assert result.skipped_alive == 1
        assert result.reaped == 0

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_pane_not_found_reaps_agent(self, mock_db, mock_check, reaper):
        """Agent whose iTerm pane is gone should be reaped."""
        agent = _make_agent(iterm_pane_id="pty-123")
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]
        mock_check.return_value = PaneStatus.NOT_FOUND

        result = reaper.reap_once()

        assert result.checked == 1
        assert result.reaped == 1
        assert result.details[0].reason == "pane_not_found"
        assert agent.ended_at is not None
        mock_db.session.commit.assert_called_once()

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_iterm_not_running_falls_back_to_inactivity(self, mock_db, mock_check, reaper):
        """When iTerm isn't running, fall through to inactivity check."""
        now = datetime.now(timezone.utc)
        agent = _make_agent(
            iterm_pane_id="pty-123",
            last_seen_at=now - timedelta(minutes=10),  # 10min > 5min timeout
        )
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]
        mock_check.return_value = PaneStatus.ITERM_NOT_RUNNING

        result = reaper.reap_once()

        assert result.reaped == 1
        assert result.details[0].reason == "inactivity_timeout"

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_iterm_not_running_recent_activity_skips(self, mock_db, mock_check, reaper):
        """When iTerm isn't running but agent was recently active, skip."""
        now = datetime.now(timezone.utc)
        agent = _make_agent(
            iterm_pane_id="pty-123",
            last_seen_at=now - timedelta(minutes=1),  # 1min < 5min timeout
        )
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]
        mock_check.return_value = PaneStatus.ITERM_NOT_RUNNING

        result = reaper.reap_once()

        assert result.reaped == 0
        assert result.skipped_alive == 1

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_error_status_skips_agent(self, mock_db, mock_check, reaper):
        """On pane check error, don't reap (conservative)."""
        agent = _make_agent(iterm_pane_id="pty-123")
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]
        mock_check.return_value = PaneStatus.ERROR

        result = reaper.reap_once()

        assert result.reaped == 0
        assert result.skipped_error == 1

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_no_pane_id_uses_inactivity(self, mock_db, mock_check, reaper):
        """Agent without pane_id should use inactivity timeout only."""
        now = datetime.now(timezone.utc)
        agent = _make_agent(
            iterm_pane_id=None,
            last_seen_at=now - timedelta(minutes=10),  # over threshold
        )
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]

        result = reaper.reap_once()

        assert result.reaped == 1
        assert result.details[0].reason == "inactivity_timeout"
        mock_check.assert_not_called()

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_no_pane_id_recent_activity_skips(self, mock_db, mock_check, reaper):
        """Agent without pane_id but recent activity should be skipped."""
        now = datetime.now(timezone.utc)
        agent = _make_agent(
            iterm_pane_id=None,
            last_seen_at=now - timedelta(minutes=1),
        )
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]

        result = reaper.reap_once()

        assert result.reaped == 0
        assert result.skipped_alive == 1

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_multiple_agents_mixed_results(self, mock_db, mock_check, reaper):
        """Test a mix of agents: one alive, one dead, one in grace period."""
        now = datetime.now(timezone.utc)

        alive = _make_agent(agent_id=1, iterm_pane_id="pty-1")
        dead = _make_agent(agent_id=2, iterm_pane_id="pty-2")
        new = _make_agent(agent_id=3, started_at=now - timedelta(minutes=1))

        mock_db.session.query.return_value.filter.return_value.all.return_value = [
            alive, dead, new
        ]
        mock_check.side_effect = [PaneStatus.FOUND, PaneStatus.NOT_FOUND]

        result = reaper.reap_once()

        assert result.checked == 3
        assert result.reaped == 1
        assert result.skipped_alive == 1
        assert result.skipped_grace == 1

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_stale_pane_reaps_older_agent(self, mock_db, mock_check, reaper):
        """Two agents share same pane ID, pane exists → older agent reaped as stale_pane."""
        old_agent = _make_agent(agent_id=1, iterm_pane_id="pty-shared")
        new_agent = _make_agent(agent_id=2, iterm_pane_id="pty-shared")

        mock_db.session.query.return_value.filter.return_value.all.return_value = [
            old_agent, new_agent
        ]
        mock_check.return_value = PaneStatus.FOUND

        result = reaper.reap_once()

        assert result.checked == 2
        assert result.reaped == 1
        assert result.skipped_alive == 1
        assert result.details[0].agent_id == 1
        assert result.details[0].reason == "stale_pane"
        assert old_agent.ended_at is not None
        assert new_agent.ended_at is None

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_different_tmux_panes_same_iterm_pane_both_survive(self, mock_db, mock_check, reaper):
        """Two agents share same iTerm pane but have different tmux panes → both survive."""
        agent_a = _make_agent(agent_id=1, iterm_pane_id="pty-shared", tmux_pane_id="%0")
        agent_b = _make_agent(agent_id=2, iterm_pane_id="pty-shared", tmux_pane_id="%1")

        mock_db.session.query.return_value.filter.return_value.all.return_value = [
            agent_a, agent_b
        ]
        mock_check.return_value = PaneStatus.FOUND

        result = reaper.reap_once()

        assert result.checked == 2
        assert result.reaped == 0
        assert result.skipped_alive == 2
        assert agent_a.ended_at is None
        assert agent_b.ended_at is None

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_same_tmux_pane_same_iterm_pane_reaps_older(self, mock_db, mock_check, reaper):
        """Two agents share same iTerm pane AND same tmux pane → older agent reaped."""
        old_agent = _make_agent(agent_id=1, iterm_pane_id="pty-shared", tmux_pane_id="%0")
        new_agent = _make_agent(agent_id=2, iterm_pane_id="pty-shared", tmux_pane_id="%0")

        mock_db.session.query.return_value.filter.return_value.all.return_value = [
            old_agent, new_agent
        ]
        mock_check.return_value = PaneStatus.FOUND

        result = reaper.reap_once()

        assert result.checked == 2
        assert result.reaped == 1
        assert result.skipped_alive == 1
        assert result.details[0].agent_id == 1
        assert result.details[0].reason == "stale_pane"

    @patch(PATCH_CHECK_PANE)
    @patch(PATCH_DB)
    def test_no_commit_when_nothing_reaped(self, mock_db, mock_check, reaper):
        """db.session.commit() should not be called if nothing was reaped."""
        agent = _make_agent(iterm_pane_id="pty-123")
        mock_db.session.query.return_value.filter.return_value.all.return_value = [agent]
        mock_check.return_value = PaneStatus.FOUND

        reaper.reap_once()

        mock_db.session.commit.assert_not_called()


class TestReapAgent:
    """Tests for the _reap_agent method."""

    @patch(PATCH_BROADCASTER)
    @patch(PATCH_DB)
    def test_sets_ended_at(self, mock_db, mock_get_bc, reaper):
        agent = _make_agent()
        now = datetime.now(timezone.utc)

        reaper._reap_agent(agent, "pane_not_found", now)

        assert agent.ended_at == now
        assert agent.last_seen_at == now

    @patch(PATCH_BROADCASTER)
    @patch(PATCH_DB)
    def test_broadcasts_session_ended(self, mock_db, mock_get_bc, reaper):
        broadcaster = MagicMock()
        mock_get_bc.return_value = broadcaster
        agent = _make_agent()
        now = datetime.now(timezone.utc)

        reaper._reap_agent(agent, "pane_not_found", now)

        broadcaster.broadcast.assert_called_once()
        call_args = broadcaster.broadcast.call_args
        assert call_args[0][0] == "session_ended"
        assert call_args[0][1]["agent_id"] == agent.id
        assert call_args[0][1]["reason"] == "reaper:pane_not_found"

    @patch(PATCH_BROADCASTER)
    @patch(PATCH_DB)
    def test_broadcast_failure_is_non_fatal(self, mock_db, mock_get_bc, reaper):
        mock_get_bc.side_effect = RuntimeError("no broadcaster")
        agent = _make_agent()
        now = datetime.now(timezone.utc)

        # Should not raise
        reaper._reap_agent(agent, "inactivity_timeout", now)
        assert agent.ended_at == now

    @patch(PATCH_BROADCASTER)
    @patch(PATCH_DB)
    def test_event_writer_called(self, mock_db, mock_get_bc, reaper):
        mock_get_bc.return_value = MagicMock()
        event_writer = MagicMock()
        reaper._app.extensions = {"event_writer": event_writer}
        agent = _make_agent()
        now = datetime.now(timezone.utc)

        reaper._reap_agent(agent, "pane_not_found", now)

        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args[1]
        assert call_kwargs["event_type"] == "reaper_ended"
        assert call_kwargs["agent_id"] == agent.id

    @patch(PATCH_BROADCASTER)
    @patch(PATCH_DB)
    def test_event_writer_failure_is_non_fatal(self, mock_db, mock_get_bc, reaper):
        mock_get_bc.return_value = MagicMock()
        event_writer = MagicMock()
        event_writer.write_event.side_effect = Exception("write failed")
        reaper._app.extensions = {"event_writer": event_writer}
        agent = _make_agent()
        now = datetime.now(timezone.utc)

        # Should not raise
        reaper._reap_agent(agent, "inactivity_timeout", now)
        assert agent.ended_at == now


class TestReapResult:
    def test_default_values(self):
        result = ReapResult()
        assert result.checked == 0
        assert result.reaped == 0
        assert result.skipped_grace == 0
        assert result.skipped_alive == 0
        assert result.skipped_error == 0
        assert result.details == []


class TestReapDetail:
    def test_creation(self):
        detail = ReapDetail(
            agent_id=42,
            session_uuid="abc-123",
            reason="pane_not_found",
        )
        assert detail.agent_id == 42
        assert detail.session_uuid == "abc-123"
        assert detail.reason == "pane_not_found"
