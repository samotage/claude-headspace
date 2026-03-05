"""Shared fixtures and helpers for CLI tests."""

from unittest.mock import MagicMock, patch


def mock_tmux_resolves_agent(agent):
    """Mock tmux to resolve to a specific agent (agent context).

    Returns a context manager that patches subprocess.run to return the
    agent's tmux_pane_id, simulating a call from within the agent's tmux pane.
    """
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = f"{agent.tmux_pane_id}\n"

    return patch(
        "claude_headspace.services.caller_identity.subprocess.run",
        return_value=mock_run,
    )


def mock_tmux_fails():
    """Mock tmux to fail (operator context -- no agent bound to pane).

    Returns a context manager that patches subprocess.run to raise
    FileNotFoundError, simulating a call from outside any agent tmux session.
    """
    return patch(
        "claude_headspace.services.caller_identity.subprocess.run",
        side_effect=FileNotFoundError,
    )
