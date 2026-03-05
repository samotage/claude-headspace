"""Tests for caller identity resolution.

After the agent-channel-security change, resolve_caller() uses tmux pane
detection only. The HEADSPACE_AGENT_ID env var override has been removed.
"""

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


class TestResolveCallerTmux:
    """Test tmux pane detection strategy (sole resolution method)."""

    def test_tmux_pane_resolves_agent(self, app, mock_agent):
        """tmux display-message resolves to an active agent."""
        with app.app_context():
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
                    MockAgent.query.filter_by.return_value.first.return_value = (
                        mock_agent
                    )
                    result = resolve_caller()
                    assert result.id == 42

    def test_tmux_pane_no_matching_agent(self, app):
        """tmux pane found but no agent bound to it raises error."""
        with app.app_context():
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
                    MockAgent.query.filter_by.return_value.first.return_value = None
                    with pytest.raises(CallerResolutionError):
                        resolve_caller()

    def test_tmux_empty_pane_id(self, app):
        """tmux returns empty pane ID raises error."""
        with app.app_context():
            mock_run_result = MagicMock()
            mock_run_result.returncode = 0
            mock_run_result.stdout = "\n"
            with patch(
                "claude_headspace.services.caller_identity.subprocess.run",
                return_value=mock_run_result,
            ):
                with pytest.raises(CallerResolutionError):
                    resolve_caller()

    def test_tmux_nonzero_returncode(self, app):
        """tmux returning non-zero exit code raises error."""
        with app.app_context():
            mock_run_result = MagicMock()
            mock_run_result.returncode = 1
            mock_run_result.stdout = ""
            with patch(
                "claude_headspace.services.caller_identity.subprocess.run",
                return_value=mock_run_result,
            ):
                with pytest.raises(CallerResolutionError):
                    resolve_caller()


class TestResolveCallerEnvVarIgnored:
    """Verify HEADSPACE_AGENT_ID env var is ignored after security hardening."""

    def test_env_var_is_ignored(self, app):
        """HEADSPACE_AGENT_ID env var does NOT resolve to an agent.

        After the agent-channel-security change, the env var override was
        removed. Even if the env var is set, resolve_caller() only uses
        tmux pane detection.
        """
        with app.app_context():
            with patch.dict(os.environ, {"HEADSPACE_AGENT_ID": "42"}):
                # tmux fails -> CallerResolutionError should be raised
                # (env var is NOT used as fallback)
                with patch(
                    "claude_headspace.services.caller_identity.subprocess.run",
                    side_effect=FileNotFoundError,
                ):
                    with pytest.raises(CallerResolutionError):
                        resolve_caller()


class TestResolveCallerError:
    """Test error case when no strategy resolves."""

    def test_no_resolution_raises_error(self, app):
        """CallerResolutionError raised when tmux detection fails."""
        with app.app_context():
            with patch(
                "claude_headspace.services.caller_identity.subprocess.run",
                side_effect=FileNotFoundError,
            ):
                with pytest.raises(CallerResolutionError) as exc_info:
                    resolve_caller()
                assert "Cannot identify calling agent" in str(exc_info.value)

    def test_tmux_timeout_raises_error(self, app):
        """CallerResolutionError raised on tmux timeout."""
        import subprocess

        with app.app_context():
            with patch(
                "claude_headspace.services.caller_identity.subprocess.run",
                side_effect=subprocess.TimeoutExpired("tmux", 5),
            ):
                with pytest.raises(CallerResolutionError):
                    resolve_caller()
