"""Tests for agent_lifecycle service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.agent_lifecycle import (
    ContextResult,
    CreateResult,
    ShutdownResult,
    create_agent,
    get_context_usage,
    shutdown_agent,
)


def _make_project(id=1, name="test-project", slug="test-project", path="/tmp/test-project"):
    """Create a mock Project object."""
    p = MagicMock()
    p.id = id
    p.name = name
    p.slug = slug
    p.path = path
    return p


def _make_agent(id=1, tmux_pane_id="%5", ended_at=None, project_id=1):
    """Create a mock Agent object."""
    a = MagicMock()
    a.id = id
    a.tmux_pane_id = tmux_pane_id
    a.ended_at = ended_at
    a.project_id = project_id
    return a


class TestCreateAgent:
    """Tests for create_agent function."""

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_project_not_found(self, mock_db):
        mock_db.session.get.return_value = None
        result = create_agent(99999)
        assert not result.success
        assert "not found" in result.message.lower()

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_project_path_missing(self, mock_db):
        project = _make_project(path="/nonexistent/path/abc123")
        mock_db.session.get.return_value = project
        result = create_agent(1)
        assert not result.success
        assert "does not exist" in result.message

    @patch("claude_headspace.services.agent_lifecycle.shutil.which")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_tmux_not_installed(self, mock_db, mock_which, tmp_path):
        project = _make_project(path=str(tmp_path))
        mock_db.session.get.return_value = project
        mock_which.return_value = None  # tmux not found
        result = create_agent(1)
        assert not result.success
        assert "tmux" in result.message.lower()

    @patch("claude_headspace.services.agent_lifecycle.subprocess.Popen")
    @patch("claude_headspace.services.agent_lifecycle.shutil.which")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_success(self, mock_db, mock_which, mock_popen, tmp_path):
        project = _make_project(path=str(tmp_path))
        mock_db.session.get.return_value = project
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd
        mock_popen.return_value = MagicMock()

        result = create_agent(1)
        assert result.success
        assert result.tmux_session_name is not None
        assert "hs-test-project" in result.tmux_session_name
        mock_popen.assert_called_once()

    @patch("claude_headspace.services.agent_lifecycle.subprocess.Popen")
    @patch("claude_headspace.services.agent_lifecycle.shutil.which")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_subprocess_failure(self, mock_db, mock_which, mock_popen, tmp_path):
        project = _make_project(path=str(tmp_path))
        mock_db.session.get.return_value = project
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd
        mock_popen.side_effect = OSError("spawn failed")

        result = create_agent(1)
        assert not result.success
        assert "Failed" in result.message


class TestShutdownAgent:
    """Tests for shutdown_agent function."""

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_agent_not_found(self, mock_db):
        mock_db.session.get.return_value = None
        result = shutdown_agent(99999)
        assert not result.success
        assert "not found" in result.message.lower()

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_agent_already_ended(self, mock_db):
        agent = _make_agent(ended_at=datetime.now(timezone.utc))
        mock_db.session.get.return_value = agent
        result = shutdown_agent(1)
        assert not result.success
        assert "already ended" in result.message.lower()

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_agent_no_tmux_pane(self, mock_db):
        agent = _make_agent(tmux_pane_id=None)
        mock_db.session.get.return_value = agent
        result = shutdown_agent(1)
        assert not result.success
        assert "no tmux pane" in result.message.lower()

    @patch("claude_headspace.services.agent_lifecycle.tmux_bridge")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_success(self, mock_db, mock_tmux):
        agent = _make_agent()
        mock_db.session.get.return_value = agent
        mock_tmux.send_text.return_value = MagicMock(success=True)
        result = shutdown_agent(1)
        assert result.success
        assert "shutdown" in result.message.lower()
        mock_tmux.send_text.assert_called_once_with(
            pane_id="%5", text="/exit", timeout=5
        )

    @patch("claude_headspace.services.agent_lifecycle.tmux_bridge")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_send_failure(self, mock_db, mock_tmux):
        agent = _make_agent()
        mock_db.session.get.return_value = agent
        mock_tmux.send_text.return_value = MagicMock(
            success=False, error_message="pane not found"
        )
        result = shutdown_agent(1)
        assert not result.success
        assert "pane not found" in result.message


class TestGetContextUsage:
    """Tests for get_context_usage function."""

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_agent_not_found(self, mock_db):
        mock_db.session.get.return_value = None
        result = get_context_usage(99999)
        assert not result.available
        assert result.reason == "agent_not_found"

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_agent_ended(self, mock_db):
        agent = _make_agent(ended_at=datetime.now(timezone.utc))
        mock_db.session.get.return_value = agent
        result = get_context_usage(1)
        assert not result.available
        assert result.reason == "agent_ended"

    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_no_tmux_pane(self, mock_db):
        agent = _make_agent(tmux_pane_id=None)
        mock_db.session.get.return_value = agent
        result = get_context_usage(1)
        assert not result.available
        assert result.reason == "no_tmux_pane"

    @patch("claude_headspace.services.agent_lifecycle.tmux_bridge")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_capture_failed(self, mock_db, mock_tmux):
        agent = _make_agent()
        mock_db.session.get.return_value = agent
        mock_tmux.capture_pane.return_value = None
        result = get_context_usage(1)
        assert not result.available
        assert result.reason == "capture_failed"

    @patch("claude_headspace.services.agent_lifecycle.tmux_bridge")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_statusline_not_found(self, mock_db, mock_tmux):
        agent = _make_agent()
        mock_db.session.get.return_value = agent
        mock_tmux.capture_pane.return_value = "normal terminal output\n$ "
        result = get_context_usage(1)
        assert not result.available
        assert result.reason == "statusline_not_found"

    @patch("claude_headspace.services.agent_lifecycle.tmux_bridge")
    @patch("claude_headspace.services.agent_lifecycle.db")
    def test_success(self, mock_db, mock_tmux):
        agent = _make_agent()
        mock_db.session.get.return_value = agent
        mock_tmux.capture_pane.return_value = (
            "some output\n[ctx: 45% used, 110k remaining]\n$ "
        )
        result = get_context_usage(1)
        assert result.available
        assert result.percent_used == 45
        assert result.remaining_tokens == "110k"
        assert "[ctx:" in result.raw
