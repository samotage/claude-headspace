"""Tests for the revival service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.revival_service import (
    RevivalResult,
    compose_revival_instruction,
    is_revival_successor,
    revive_agent,
)


class TestReviveAgent:
    """Tests for revive_agent()."""

    @patch("claude_headspace.services.revival_service.db")
    def test_agent_not_found(self, mock_db):
        mock_db.session.get.return_value = None
        result = revive_agent(999)
        assert not result.success
        assert result.error_code == "not_found"
        assert "not found" in result.message.lower()

    @patch("claude_headspace.services.revival_service.db")
    def test_agent_still_alive(self, mock_db):
        agent = MagicMock()
        agent.ended_at = None
        mock_db.session.get.return_value = agent
        result = revive_agent(1)
        assert not result.success
        assert result.error_code == "still_alive"
        assert "still alive" in result.message.lower()

    @patch("claude_headspace.services.revival_service.db")
    def test_agent_no_project(self, mock_db):
        agent = MagicMock()
        agent.ended_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        agent.project_id = None
        mock_db.session.get.return_value = agent
        result = revive_agent(1)
        assert not result.success
        assert result.error_code == "no_project"

    @patch("claude_headspace.services.agent_lifecycle.create_agent")
    @patch("claude_headspace.services.revival_service.db")
    def test_success_anonymous_agent(self, mock_db, mock_create):
        agent = MagicMock()
        agent.id = 5
        agent.ended_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        agent.project_id = 10
        agent.persona = None
        mock_db.session.get.return_value = agent

        mock_create.return_value = MagicMock(
            success=True,
            message="Agent starting",
            tmux_session_name="hs-test-abc123",
        )

        result = revive_agent(5)
        assert result.success
        assert result.successor_agent_tmux_session == "hs-test-abc123"
        mock_create.assert_called_once_with(
            project_id=10,
            persona_slug=None,
            previous_agent_id=5,
        )

    @patch("claude_headspace.services.agent_lifecycle.create_agent")
    @patch("claude_headspace.services.revival_service.db")
    def test_success_persona_agent(self, mock_db, mock_create):
        agent = MagicMock()
        agent.id = 7
        agent.ended_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        agent.project_id = 10
        persona = MagicMock()
        persona.slug = "dev-persona"
        agent.persona = persona
        mock_db.session.get.return_value = agent

        mock_create.return_value = MagicMock(
            success=True,
            message="Agent starting",
            tmux_session_name="hs-test-def456",
        )

        result = revive_agent(7)
        assert result.success
        mock_create.assert_called_once_with(
            project_id=10,
            persona_slug="dev-persona",
            previous_agent_id=7,
        )

    @patch("claude_headspace.services.agent_lifecycle.create_agent")
    @patch("claude_headspace.services.revival_service.db")
    def test_creation_failure(self, mock_db, mock_create):
        agent = MagicMock()
        agent.id = 5
        agent.ended_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        agent.project_id = 10
        agent.persona = None
        mock_db.session.get.return_value = agent

        mock_create.return_value = MagicMock(
            success=False,
            message="tmux is not installed",
        )

        result = revive_agent(5)
        assert not result.success
        assert result.error_code == "creation_failed"


class TestIsRevivalSuccessor:
    """Tests for is_revival_successor()."""

    @patch("claude_headspace.services.revival_service.db")
    def test_no_previous_agent(self, mock_db):
        agent = MagicMock()
        agent.previous_agent_id = None
        assert not is_revival_successor(agent)

    @patch("claude_headspace.services.revival_service.db")
    def test_predecessor_has_handoff(self, mock_db):
        """Agent with a predecessor that has a handoff record is NOT a revival."""
        agent = MagicMock()
        agent.previous_agent_id = 5
        # Query returns a Handoff record
        mock_db.session.query.return_value.filter.return_value.first.return_value = MagicMock()
        assert not is_revival_successor(agent)

    @patch("claude_headspace.services.revival_service.db")
    def test_predecessor_no_handoff(self, mock_db):
        """Agent with a predecessor that has NO handoff record IS a revival."""
        agent = MagicMock()
        agent.previous_agent_id = 5
        # Query returns None (no Handoff record)
        mock_db.session.query.return_value.filter.return_value.first.return_value = None
        assert is_revival_successor(agent)


class TestComposeRevivalInstruction:
    """Tests for compose_revival_instruction()."""

    def test_includes_predecessor_id(self):
        msg = compose_revival_instruction(42)
        assert "42" in msg
        assert "claude-headspace transcript 42" in msg

    def test_includes_context_recovery_instructions(self):
        msg = compose_revival_instruction(1)
        assert "predecessor" in msg.lower()
        assert "transcript" in msg.lower()
        assert "continue" in msg.lower()
