"""Tests for the remote agent service."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.remote_agent_service import (
    RemoteAgentService,
    RemoteAgentResult,
)
from claude_headspace.services.session_token import SessionTokenService


@contextmanager
def _noop_advisory_lock(*args, **kwargs):
    """No-op context manager replacing advisory_lock for unit tests."""
    yield


@pytest.fixture(autouse=True)
def mock_advisory_lock():
    """Mock advisory_lock so remote agent tests don't need a real database."""
    with patch(
        "claude_headspace.services.remote_agent_service.advisory_lock",
        side_effect=_noop_advisory_lock,
    ):
        yield


@pytest.fixture
def token_service():
    return SessionTokenService()


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config = {
        "APP_CONFIG": {
            "remote_agents": {
                "creation_timeout_seconds": 2,
            },
            "tmux_bridge": {
                "subprocess_timeout": 5,
                "text_enter_delay_ms": 100,
            },
            "server": {
                "application_url": "https://test.example.com:5055",
            },
        }
    }
    return app


@pytest.fixture
def service(mock_app, token_service):
    return RemoteAgentService(app=mock_app, session_token_service=token_service)


class TestCreateBlocking:
    """Tests for blocking agent creation."""

    @patch("claude_headspace.services.remote_agent_service.db")
    @patch("claude_headspace.services.remote_agent_service.create_agent")
    def test_project_not_found(self, mock_create, mock_db, service):
        mock_db.session.query.return_value.filter.return_value.first.return_value = None

        result = service.create_blocking(
            project_slug="nonexistent",
            persona_slug="test",
            initial_prompt="hello",
        )

        assert not result.success
        assert result.error_code == "project_not_found"

    @patch("claude_headspace.services.remote_agent_service.db")
    @patch("claude_headspace.services.remote_agent_service.create_agent")
    def test_persona_not_found(self, mock_create, mock_db, service):
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.slug = "test-project"
        mock_db.session.query.return_value.filter.return_value.first.return_value = mock_project

        from claude_headspace.services.agent_lifecycle import CreateResult
        mock_create.return_value = CreateResult(
            success=False,
            message="Persona 'bad' not found or not active.",
        )

        result = service.create_blocking(
            project_slug="test-project",
            persona_slug="bad",
            initial_prompt="hello",
        )

        assert not result.success
        assert result.error_code == "persona_not_found"

    @patch("claude_headspace.services.remote_agent_service.db")
    @patch("claude_headspace.services.remote_agent_service.create_agent")
    @patch("claude_headspace.services.remote_agent_service.time")
    def test_creation_timeout(self, mock_time, mock_create, mock_db, service):
        """Agent never becomes ready — should timeout."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.slug = "test-project"

        from claude_headspace.services.agent_lifecycle import CreateResult
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent starting",
            tmux_session_name="hs-test-abc123",
        )

        # Use a dispatcher that returns project for first call, None for polls
        call_count = [0]
        def query_side_effect(model):
            mock_chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Project lookup
                mock_chain.filter.return_value.first.return_value = mock_project
            else:
                # Agent polling — never found
                mock_chain.filter.return_value.first.return_value = None
            return mock_chain
        mock_db.session.query.side_effect = query_side_effect

        # Use a counter that increments past timeout after a few calls
        time_counter = [0.0]
        def fake_time():
            val = time_counter[0]
            time_counter[0] += 0.6  # Each call advances 0.6s, timeout is 2s
            return val
        mock_time.time.side_effect = fake_time
        mock_time.sleep = MagicMock()

        result = service.create_blocking(
            project_slug="test-project",
            persona_slug="test",
            initial_prompt="hello",
        )

        assert not result.success
        assert result.error_code == "agent_creation_timeout"

    @patch("claude_headspace.services.remote_agent_service.db")
    @patch("claude_headspace.services.remote_agent_service.create_agent")
    @patch("claude_headspace.services.remote_agent_service.time")
    def test_successful_creation(self, mock_time, mock_create, mock_db, service, token_service):
        """Agent becomes ready — should return full result."""
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.slug = "test-project"

        mock_agent = MagicMock()
        mock_agent.id = 42
        mock_agent.prompt_injected_at = datetime.now(timezone.utc)
        mock_agent.tmux_pane_id = "%5"
        mock_agent.project = mock_project

        from claude_headspace.services.agent_lifecycle import CreateResult
        mock_create.return_value = CreateResult(
            success=True,
            message="Agent starting",
            tmux_session_name="hs-test-abc123",
        )

        # Use a dispatcher: first query returns project, subsequent return agent
        call_count = [0]
        def query_side_effect(model):
            mock_chain = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Project lookup
                mock_chain.filter.return_value.first.return_value = mock_project
            elif call_count[0] == 2:
                # First agent poll — not found yet
                mock_chain.filter.return_value.first.return_value = None
            else:
                # Second agent poll — agent is ready
                mock_chain.filter.return_value.first.return_value = mock_agent
            return mock_chain
        mock_db.session.query.side_effect = query_side_effect

        # Use a counter — returns small values (well within 2s timeout)
        time_counter = [0.0]
        def fake_time():
            val = time_counter[0]
            time_counter[0] += 0.3
            return val
        mock_time.time.side_effect = fake_time
        mock_time.sleep = MagicMock()

        # Patch tmux_bridge at the module level where it's lazily imported
        with patch("claude_headspace.services.tmux_bridge") as mock_tmux:
            mock_send_result = MagicMock()
            mock_send_result.success = True
            mock_tmux.send_text.return_value = mock_send_result

            result = service.create_blocking(
                project_slug="test-project",
                persona_slug="test",
                initial_prompt="hello",
                feature_flags={"file_upload": True},
            )

        assert result.success
        assert result.agent_id == 42
        assert result.status == "ready"
        assert result.session_token is not None
        assert "embed/42" in result.embed_url
        assert result.project_slug == "test-project"
        assert result.persona_slug == "test"

        # Verify token was stored
        assert token_service.token_count == 1


class TestCheckAlive:
    """Tests for liveness check."""

    @patch("claude_headspace.services.remote_agent_service.db")
    def test_agent_not_found(self, mock_db, service):
        mock_db.session.get.return_value = None
        result = service.check_alive(999)
        assert result["alive"] is False
        assert result["reason"] == "agent_not_found"

    @patch("claude_headspace.services.remote_agent_service.db")
    def test_agent_ended(self, mock_db, service):
        agent = MagicMock()
        agent.ended_at = datetime.now(timezone.utc)
        mock_db.session.get.return_value = agent

        result = service.check_alive(1)
        assert result["alive"] is False
        assert result["reason"] == "agent_ended"

    @patch("claude_headspace.services.remote_agent_service.db")
    def test_agent_alive(self, mock_db, service):
        agent = MagicMock()
        agent.id = 1
        agent.ended_at = None
        agent.project.name = "test-project"
        cmd = MagicMock()
        cmd.state.value = "processing"
        agent.get_current_command.return_value = cmd
        mock_db.session.get.return_value = agent

        result = service.check_alive(1)
        assert result["alive"] is True
        assert result["state"] == "processing"


class TestShutdown:
    """Tests for agent shutdown (non-blocking, S5 FR3 contract)."""

    @patch("claude_headspace.services.remote_agent_service.shutdown_agent")
    @patch("claude_headspace.services.remote_agent_service.db")
    def test_initiated_shutdown(self, mock_db, mock_shutdown, service, token_service):
        """Active agent → result='initiated', tokens revoked, async shutdown fired."""
        agent = MagicMock()
        agent.ended_at = None
        mock_db.session.get.return_value = agent

        token_service.generate(agent_id=1)
        assert token_service.token_count == 1

        result = service.shutdown(1)
        assert result["result"] == "initiated"
        assert result["agent_id"] == 1
        assert token_service.token_count == 0  # Token revoked

        # Give the daemon thread a moment to fire
        import time
        time.sleep(0.1)
        mock_shutdown.assert_called_once_with(1)

    @patch("claude_headspace.services.remote_agent_service.shutdown_agent")
    @patch("claude_headspace.services.remote_agent_service.db")
    def test_already_terminated(self, mock_db, mock_shutdown, service):
        """Agent with ended_at set → result='already_terminated', no shutdown call."""
        agent = MagicMock()
        agent.ended_at = datetime.now(timezone.utc)
        mock_db.session.get.return_value = agent

        result = service.shutdown(1)
        assert result["result"] == "already_terminated"
        assert result["agent_id"] == 1
        mock_shutdown.assert_not_called()

    @patch("claude_headspace.services.remote_agent_service.shutdown_agent")
    @patch("claude_headspace.services.remote_agent_service.db")
    def test_agent_not_found(self, mock_db, mock_shutdown, service):
        """No agent record → result='not_found'."""
        mock_db.session.get.return_value = None

        result = service.shutdown(999)
        assert result["result"] == "not_found"
        assert result["agent_id"] == 999
        mock_shutdown.assert_not_called()
