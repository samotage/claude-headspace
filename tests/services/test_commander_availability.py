"""Tests for commander availability service."""

from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.commander_availability import CommanderAvailability
from claude_headspace.services.tmux_bridge import HealthResult, PaneInfo


class TestCommanderAvailability:
    """Tests for CommanderAvailability class."""

    def test_initial_state(self):
        svc = CommanderAvailability()
        assert svc.is_available(1) is False
        assert svc.is_available(999) is False

    def test_register_agent(self):
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")
        # After registration, still not available (no health check yet)
        assert svc.is_available(1) is False

    def test_register_agent_none_pane_id(self):
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")
        svc._availability[1] = True
        # Re-register with None pane_id clears availability
        svc.register_agent(1, None)
        assert svc.is_available(1) is False

    def test_unregister_agent(self):
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")
        svc._availability[1] = True
        svc.unregister_agent(1)
        assert svc.is_available(1) is False

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    def test_check_agent_available(self, mock_health):
        mock_health.return_value = HealthResult(available=True, running=True)
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")

        result = svc.check_agent(1)

        assert result is True
        assert svc.is_available(1) is True
        mock_health.assert_called_once()

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    def test_check_agent_unavailable(self, mock_health):
        mock_health.return_value = HealthResult(available=False)
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")

        result = svc.check_agent(1)

        assert result is False
        assert svc.is_available(1) is False

    def test_check_agent_no_pane_id(self):
        svc = CommanderAvailability()
        result = svc.check_agent(1)
        assert result is False

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    def test_check_agent_with_pane_id_override(self, mock_health):
        mock_health.return_value = HealthResult(available=True, running=True)
        svc = CommanderAvailability()

        result = svc.check_agent(1, tmux_pane_id="%10")

        assert result is True
        # Should have registered the agent
        assert "%10" == svc._pane_ids.get(1)

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    def test_availability_change_broadcasts(self, mock_health):
        """Test that availability changes trigger SSE broadcast."""
        mock_health.return_value = HealthResult(available=True, running=True)
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")

        # Set initial availability to False
        svc._availability[1] = False

        with patch.object(svc, "_broadcast_change") as mock_broadcast:
            svc.check_agent(1)
            mock_broadcast.assert_called_once_with(1, True)

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    def test_no_broadcast_when_unchanged(self, mock_health):
        """Test that no broadcast when availability doesn't change."""
        mock_health.return_value = HealthResult(available=True, running=True)
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")

        # Set initial availability to True (same as check result)
        svc._availability[1] = True

        with patch.object(svc, "_broadcast_change") as mock_broadcast:
            svc.check_agent(1)
            mock_broadcast.assert_not_called()

    def test_config_overrides(self):
        config = {
            "tmux_bridge": {
                "health_check_interval": 60,
                "subprocess_timeout": 10,
            }
        }
        svc = CommanderAvailability(config=config)
        assert svc._health_check_interval == 60
        assert svc._subprocess_timeout == 10

    def test_start_stop(self):
        svc = CommanderAvailability(health_check_interval=100)
        svc.start()
        assert svc._thread is not None
        assert svc._thread.is_alive()
        svc.stop()
        assert svc._thread is None

    def test_start_idempotent(self):
        svc = CommanderAvailability(health_check_interval=100)
        svc.start()
        thread1 = svc._thread
        svc.start()  # Second start should be no-op
        assert svc._thread is thread1
        svc.stop()

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    def test_unregister_releases_send_lock(self, mock_health):
        """unregister_agent calls release_send_lock for the pane."""
        svc = CommanderAvailability()
        svc.register_agent(1, "%5")
        with patch("claude_headspace.services.commander_availability.tmux_bridge.release_send_lock") as mock_release:
            svc.unregister_agent(1)
            mock_release.assert_called_once_with("%5")


class TestAttemptReconnection:
    """Tests for _attempt_reconnection in CommanderAvailability (WU6)."""

    def _make_app_context(self, agent, panes, health_result=None):
        """Helper to set up mocked app context for reconnection tests."""
        mock_app = MagicMock()
        mock_db = MagicMock()
        mock_db.session.get.return_value = agent

        if health_result is None:
            health_result = HealthResult(available=True, running=True, pid=123)

        patches = {
            "db": mock_db,
            "list_panes": panes,
            "check_health": health_result,
        }
        return mock_app, patches

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    @patch("claude_headspace.services.commander_availability.tmux_bridge.list_panes")
    @patch("claude_headspace.database.db")
    def test_reconnection_found(self, mock_db, mock_list_panes, mock_check_health):
        """Agent reconnects to a new pane in the same project directory."""
        mock_app = MagicMock()
        svc = CommanderAvailability(app=mock_app)
        svc.register_agent(1, "%5")

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.ended_at = None
        mock_agent.project.path = "/home/user/project"
        mock_db.session.get.return_value = mock_agent

        # New pane running claude in same directory
        mock_list_panes.return_value = [
            PaneInfo(pane_id="%10", session_name="hs-proj-new", current_command="claude", working_directory="/home/user/project"),
        ]
        mock_check_health.return_value = HealthResult(available=True, running=True, pid=456)

        result = svc._attempt_reconnection(1, "%5")

        assert result is True
        assert mock_agent.tmux_pane_id == "%10"
        mock_db.session.commit.assert_called_once()

    @patch("claude_headspace.services.commander_availability.tmux_bridge.list_panes")
    @patch("claude_headspace.database.db")
    def test_reconnection_no_candidates(self, mock_db, mock_list_panes):
        """No matching pane found — reconnection fails."""
        mock_app = MagicMock()
        svc = CommanderAvailability(app=mock_app)

        mock_agent = MagicMock()
        mock_agent.ended_at = None
        mock_agent.project.path = "/home/user/project"
        mock_db.session.get.return_value = mock_agent

        # Only non-hs sessions
        mock_list_panes.return_value = [
            PaneInfo(pane_id="%10", session_name="main", current_command="bash", working_directory="/home/user/project"),
        ]

        result = svc._attempt_reconnection(1, "%5")

        assert result is False

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    @patch("claude_headspace.services.commander_availability.tmux_bridge.list_panes")
    @patch("claude_headspace.database.db")
    def test_reconnection_skips_dead_candidate(self, mock_db, mock_list_panes, mock_check_health):
        """Candidate pane where claude is not running is skipped."""
        mock_app = MagicMock()
        svc = CommanderAvailability(app=mock_app)

        mock_agent = MagicMock()
        mock_agent.ended_at = None
        mock_agent.project.path = "/proj"
        mock_db.session.get.return_value = mock_agent

        mock_list_panes.return_value = [
            PaneInfo(pane_id="%10", session_name="hs-proj-x", current_command="bash", working_directory="/proj"),
        ]
        mock_check_health.return_value = HealthResult(available=True, running=False)

        result = svc._attempt_reconnection(1, "%5")

        assert result is False

    def test_reconnection_no_app(self):
        """No app configured — reconnection fails gracefully."""
        svc = CommanderAvailability(app=None)
        assert svc._attempt_reconnection(1, "%5") is False

    @patch("claude_headspace.services.commander_availability.tmux_bridge.check_health")
    @patch("claude_headspace.services.commander_availability.tmux_bridge.list_panes")
    @patch("claude_headspace.database.db")
    def test_reconnection_skips_old_pane(self, mock_db, mock_list_panes, mock_check_health):
        """The old dead pane is skipped even if it appears in list_panes."""
        mock_app = MagicMock()
        svc = CommanderAvailability(app=mock_app)

        mock_agent = MagicMock()
        mock_agent.ended_at = None
        mock_agent.project.path = "/proj"
        mock_db.session.get.return_value = mock_agent

        # Only the old pane shows up
        mock_list_panes.return_value = [
            PaneInfo(pane_id="%5", session_name="hs-proj-old", current_command="claude", working_directory="/proj"),
        ]
        mock_check_health.return_value = HealthResult(available=True, running=True, pid=123)

        result = svc._attempt_reconnection(1, "%5")

        assert result is False
        # check_health should NOT be called for the skipped pane
        mock_check_health.assert_not_called()
