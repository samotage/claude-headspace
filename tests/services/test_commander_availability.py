"""Tests for commander availability service."""

from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.commander_availability import CommanderAvailability
from claude_headspace.services.tmux_bridge import HealthResult


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
