"""Tests for skill injector service.

Tests the DB-based idempotency approach: agent.prompt_injected_at
controls whether persona skills have been injected.
"""

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.skill_injector import (
    clear_injection_record,
    inject_persona_skills,
    reset_injection_state,
)


def _make_agent(agent_id=1, persona_id=5, tmux_pane_id="%0", slug="developer-con-1", name="Con",
                prompt_injected_at=None):
    """Create a mock agent with persona relationship."""
    agent = MagicMock()
    agent.id = agent_id
    agent.persona_id = persona_id
    agent.tmux_pane_id = tmux_pane_id
    agent.prompt_injected_at = prompt_injected_at
    persona = MagicMock()
    persona.slug = slug
    persona.name = name
    agent.persona = persona
    return agent


class TestInjectPersonaSkills:
    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_successful_injection_both_files(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """Successful injection with both skill.md and experience.md."""
        mock_read_skill.return_value = "# Con — developer\n\nBackend specialist."
        mock_read_exp.return_value = "# Experience Log\n\nLearned Flask patterns."
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        result = inject_persona_skills(agent)

        assert result is True
        mock_read_skill.assert_called_once_with("developer-con-1")
        mock_read_exp.assert_called_once_with("developer-con-1")
        mock_health.assert_called_once()
        mock_send.assert_called_once()
        # Verify the message contains both skill and experience
        sent_text = mock_send.call_args[0][1]
        assert "Backend specialist" in sent_text
        assert "Flask patterns" in sent_text
        assert "You are Con" in sent_text

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_successful_injection_sets_prompt_injected_at(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """Successful injection sets prompt_injected_at on the agent."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        assert agent.prompt_injected_at is None

        inject_persona_skills(agent)

        assert agent.prompt_injected_at is not None
        assert isinstance(agent.prompt_injected_at, datetime)

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_injection_skill_only_no_experience(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """Injection proceeds with skill.md only when experience.md is missing."""
        mock_read_skill.return_value = "# Con — developer\n\nBackend specialist."
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        result = inject_persona_skills(agent)

        assert result is True
        sent_text = mock_send.call_args[0][1]
        assert "Backend specialist" in sent_text
        assert "Experience" not in sent_text

    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_missing_skill_file_skips_injection(self, mock_read_skill, caplog):
        """Missing skill.md skips injection with warning."""
        mock_read_skill.return_value = None

        agent = _make_agent()
        with caplog.at_level(logging.WARNING):
            result = inject_persona_skills(agent)

        assert result is False
        assert "skill.md not found on disk" in caplog.text

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_idempotency_second_call_is_noop(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send, caplog
    ):
        """Second injection call for same agent is a no-op (DB idempotency)."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        result1 = inject_persona_skills(agent)
        assert result1 is True

        # prompt_injected_at is now set, so second call should be blocked
        with caplog.at_level(logging.DEBUG):
            result2 = inject_persona_skills(agent)

        assert result2 is False
        assert "already injected" in caplog.text
        # send_text should only have been called once
        assert mock_send.call_count == 1

    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_unhealthy_tmux_pane_skips_injection(
        self, mock_read_skill, mock_read_exp, mock_health, caplog
    ):
        """Unhealthy tmux pane skips injection with warning."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=False, error_message="pane not found")

        agent = _make_agent()
        with caplog.at_level(logging.WARNING):
            result = inject_persona_skills(agent)

        assert result is False
        assert "unhealthy" in caplog.text

    def test_agent_without_persona_skips(self):
        """Agent without persona_id receives no injection."""
        agent = _make_agent(persona_id=None)
        result = inject_persona_skills(agent)
        assert result is False

    def test_agent_without_tmux_pane_skips(self):
        """Agent without tmux_pane_id is skipped."""
        agent = _make_agent(tmux_pane_id=None)
        result = inject_persona_skills(agent)
        assert result is False

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_send_failure_returns_false(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send, caplog
    ):
        """send_text failure returns False and logs error."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=False, error_message="tmux error")

        agent = _make_agent()
        with caplog.at_level(logging.ERROR):
            result = inject_persona_skills(agent)

        assert result is False
        assert "send_text error" in caplog.text

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_send_failure_does_not_set_prompt_injected_at(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """send_text failure should NOT set prompt_injected_at."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=False, error_message="tmux error")

        agent = _make_agent()
        inject_persona_skills(agent)

        assert agent.prompt_injected_at is None


class TestDBIdempotency:
    """Tests for DB-based idempotency via agent.prompt_injected_at."""

    def test_already_injected_agent_is_skipped(self, caplog):
        """Agent with prompt_injected_at already set is skipped immediately."""
        agent = _make_agent(prompt_injected_at=datetime.now(timezone.utc))

        with caplog.at_level(logging.DEBUG):
            result = inject_persona_skills(agent)

        assert result is False
        assert "already injected" in caplog.text

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_injection_then_reinjection_blocked(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """After successful injection, re-injection is blocked by DB column."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        assert inject_persona_skills(agent) is True
        assert inject_persona_skills(agent) is False
        assert mock_send.call_count == 1

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_resetting_prompt_injected_at_allows_reinjection(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """Setting prompt_injected_at back to None allows re-injection (for tests)."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        assert inject_persona_skills(agent) is True
        assert mock_send.call_count == 1

        # Reset — simulates what tests should do
        agent.prompt_injected_at = None
        assert inject_persona_skills(agent) is True
        assert mock_send.call_count == 2

    def test_clear_injection_record_is_noop(self):
        """clear_injection_record() is a no-op — DB column handles idempotency."""
        # Should not raise
        clear_injection_record(42)

    def test_reset_injection_state_is_noop(self):
        """reset_injection_state() is a no-op — injection state is in DB."""
        # Should not raise
        reset_injection_state()

    @patch("claude_headspace.services.skill_injector.send_text")
    @patch("claude_headspace.services.skill_injector.check_health")
    @patch("claude_headspace.services.skill_injector.read_experience_file")
    @patch("claude_headspace.services.skill_injector.read_skill_file")
    def test_session_end_clear_does_not_enable_reinjection(
        self, mock_read_skill, mock_read_exp, mock_health, mock_send
    ):
        """Session end calling clear_injection_record should NOT allow re-injection."""
        mock_read_skill.return_value = "# skill content"
        mock_read_exp.return_value = None
        mock_health.return_value = MagicMock(available=True)
        mock_send.return_value = MagicMock(success=True)

        agent = _make_agent()
        assert inject_persona_skills(agent) is True

        # Simulate session_end calling clear_injection_record
        clear_injection_record(agent.id)

        # Re-injection should still be blocked (DB column is still set)
        assert inject_persona_skills(agent) is False
