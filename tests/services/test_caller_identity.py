"""Tests for caller identity resolution."""

import os
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.caller_identity import (
    CallerResolutionError,
    resolve_caller,
)


@pytest.fixture
def mock_agent():
    """Create a mock agent with ended_at=None."""
    agent = MagicMock()
    agent.id = 42
    agent.ended_at = None
    agent.tmux_pane_id = "%99"
    return agent


class TestResolveCallerEnvVar:
    """Test HEADSPACE_AGENT_ID env var strategy."""

    def test_env_var_resolves_active_agent(self, app, mock_agent):
        """HEADSPACE_AGENT_ID resolves to an active agent."""
        with app.app_context():
            with patch.dict(os.environ, {"HEADSPACE_AGENT_ID": "42"}):
                with patch(
                    "claude_headspace.services.caller_identity.db.session.get",
                    return_value=mock_agent,
                ):
                    result = resolve_caller()
                    assert result.id == 42

    def test_env_var_skips_ended_agent(self, app):
        """HEADSPACE_AGENT_ID agent with ended_at set is skipped."""
        ended_agent = MagicMock()
        ended_agent.id = 42
        ended_agent.ended_at = "2026-01-01"

        with app.app_context():
            with patch.dict(os.environ, {"HEADSPACE_AGENT_ID": "42"}):
                with patch(
                    "claude_headspace.services.caller_identity.db.session.get",
                    return_value=ended_agent,
                ):
                    with patch(
                        "claude_headspace.services.caller_identity.subprocess.run",
                        side_effect=FileNotFoundError,
                    ):
                        with pytest.raises(CallerResolutionError):
                            resolve_caller()

    def test_env_var_invalid_value(self, app):
        """Non-integer HEADSPACE_AGENT_ID falls through."""
        with app.app_context():
            with patch.dict(os.environ, {"HEADSPACE_AGENT_ID": "not-a-number"}):
                with patch(
                    "claude_headspace.services.caller_identity.subprocess.run",
                    side_effect=FileNotFoundError,
                ):
                    with pytest.raises(CallerResolutionError):
                        resolve_caller()


class TestResolveCallerTmux:
    """Test tmux pane detection strategy."""

    def test_tmux_pane_resolves_agent(self, app, mock_agent):
        """tmux display-message resolves to an active agent."""
        with app.app_context():
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("HEADSPACE_AGENT_ID", None)
                mock_run_result = MagicMock()
                mock_run_result.returncode = 0
                mock_run_result.stdout = "%99\n"
                with patch(
                    "claude_headspace.services.caller_identity.subprocess.run",
                    return_value=mock_run_result,
                ):
                    with patch(
                        "claude_headspace.services.caller_identity.Agent"
                    ) as MockAgent:
                        MockAgent.query.filter_by.return_value.first.return_value = mock_agent
                        result = resolve_caller()
                        assert result.id == 42


class TestResolveCallerError:
    """Test error case when no strategy resolves."""

    def test_no_resolution_raises_error(self, app):
        """CallerResolutionError raised when neither strategy works."""
        with app.app_context():
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("HEADSPACE_AGENT_ID", None)
                with patch(
                    "claude_headspace.services.caller_identity.subprocess.run",
                    side_effect=FileNotFoundError,
                ):
                    with pytest.raises(CallerResolutionError) as exc_info:
                        resolve_caller()
                    assert "Cannot identify calling agent" in str(exc_info.value)
