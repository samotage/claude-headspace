"""Tests for card_state service module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.models.task import TaskState
from claude_headspace.services.card_state import (
    TIMED_OUT,
    broadcast_card_refresh,
    build_card_state,
    format_last_seen,
    format_uptime,
    get_effective_state,
    get_question_options,
    get_state_info,
    get_task_completion_summary,
    get_task_instruction,
    get_task_summary,
    is_agent_active,
)


def _make_agent(
    state=TaskState.IDLE,
    last_seen_minutes_ago=0,
    started_hours_ago=1,
    ended=False,
    priority_score=None,
    priority_reason=None,
):
    """Create a mock agent with specified properties."""
    agent = MagicMock()
    agent.id = 42
    agent.session_uuid = uuid4()
    agent.state = state
    agent.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=last_seen_minutes_ago)
    agent.started_at = datetime.now(timezone.utc) - timedelta(hours=started_hours_ago)
    agent.ended_at = datetime.now(timezone.utc) if ended else None
    agent.priority_score = priority_score
    agent.priority_reason = priority_reason
    agent.project_id = 10
    agent.project = MagicMock()
    agent.project.name = "test-project"
    agent.get_current_task.return_value = None
    agent.tasks = []
    return agent


class TestBuildCardState:
    """Tests for build_card_state()."""

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_returns_all_expected_keys(self, mock_config):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        agent = _make_agent()

        result = build_card_state(agent)

        expected_keys = {
            "id", "session_uuid", "hero_chars", "hero_trail",
            "is_active", "uptime", "last_seen",
            "state", "state_info", "task_summary", "task_instruction",
            "task_completion_summary", "priority", "priority_reason",
            "turn_count", "elapsed", "current_task_id", "is_bridge_connected",
            "project_name", "project_slug", "project_id",
            "has_plan", "tmux_session", "context",
        }
        assert set(result.keys()) == expected_keys

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_idle_agent_no_task(self, mock_config):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        agent = _make_agent(state=TaskState.IDLE)

        result = build_card_state(agent)

        assert result["id"] == 42
        assert result["state"] == "IDLE"
        assert result["is_active"] is True
        assert result["task_summary"] == "No active task"
        assert result["priority"] == 50  # default

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_tmux_session_included(self, mock_config):
        """Test that tmux_session is included in card state."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        agent = _make_agent()
        agent.tmux_session = "hs-test-123"

        result = build_card_state(agent)

        assert result["tmux_session"] == "hs-test-123"

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_tmux_session_none_when_not_set(self, mock_config):
        """Test that tmux_session is None when agent has no tmux session."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        agent = _make_agent()
        agent.tmux_session = None

        result = build_card_state(agent)

        assert result["tmux_session"] is None

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_with_task_and_turns(self, mock_config):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        mock_turn = MagicMock()
        mock_turn.text = "Working on auth"
        mock_turn.summary = "Implementing OAuth2"
        mock_turn.actor = MagicMock()
        mock_turn.actor.value = "agent"
        mock_turn.intent = MagicMock()
        mock_turn.intent.value = "progress"

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_task.instruction = "Add OAuth2 support"
        mock_task.turns = [mock_turn]
        mock_task.completion_summary = None

        agent = _make_agent(state=TaskState.PROCESSING)
        agent.get_current_task.return_value = mock_task
        agent.tasks = [mock_task]

        result = build_card_state(agent)

        assert result["state"] == "PROCESSING"
        assert result["task_instruction"] == "Add OAuth2 support"
        assert result["task_summary"] == "Implementing OAuth2"

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_timed_out_detection(self, mock_config):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        agent = _make_agent(state=TaskState.PROCESSING, last_seen_minutes_ago=15)

        result = build_card_state(agent)

        assert result["state"] == "TIMED_OUT"
        assert result["state_info"]["color"] == "red"

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_priority_score_included(self, mock_config):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        agent = _make_agent(priority_score=85, priority_reason="High alignment")

        result = build_card_state(agent)

        assert result["priority"] == 85
        assert result["priority_reason"] == "High alignment"

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_complete_state_includes_turn_count_and_elapsed(self, mock_config):
        """COMPLETE state includes turn_count and elapsed for condensed card."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        mock_task = MagicMock()
        mock_task.state = TaskState.COMPLETE
        mock_task.instruction = "Fix the bug"
        mock_task.completion_summary = "Bug fixed"
        mock_task.started_at = datetime.now(timezone.utc) - timedelta(hours=1, minutes=30)
        mock_task.completed_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_task.turns = [MagicMock(), MagicMock(), MagicMock()]

        agent = _make_agent(state=TaskState.IDLE)
        agent.tasks = [mock_task]

        result = build_card_state(agent)

        assert result["state"] == "COMPLETE"
        assert result["turn_count"] == 3
        assert "1h" in result["elapsed"]
        assert "turn_count" in result
        assert "elapsed" in result

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_idle_state_includes_turn_count_and_elapsed(self, mock_config):
        """All states include turn_count and elapsed (0/None for IDLE with no task)."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        agent = _make_agent(state=TaskState.IDLE)

        result = build_card_state(agent)

        assert "turn_count" in result
        assert "elapsed" in result
        assert result["turn_count"] == 0
        assert result["elapsed"] is None

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_state_serialised_as_string(self, mock_config):
        """State is always a string (not a TaskState enum) for JSON serialisation."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        agent = _make_agent(state=TaskState.AWAITING_INPUT)

        result = build_card_state(agent)

        assert isinstance(result["state"], str)
        assert result["state"] == "AWAITING_INPUT"


class TestBroadcastCardRefresh:
    """Tests for broadcast_card_refresh()."""

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_calls_broadcaster(self, mock_config, mock_get_broadcaster):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        agent = _make_agent()
        broadcast_card_refresh(agent, "test_reason")

        mock_broadcaster.broadcast.assert_called_once()
        call_args = mock_broadcaster.broadcast.call_args
        assert call_args[0][0] == "card_refresh"

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_includes_agent_id_and_reason(self, mock_config, mock_get_broadcaster):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        agent = _make_agent()
        broadcast_card_refresh(agent, "session_start")

        call_args = mock_broadcaster.broadcast.call_args
        payload = call_args[0][1]
        assert payload["agent_id"] == 42
        assert payload["reason"] == "session_start"
        assert "timestamp" in payload
        assert payload["id"] == 42
        assert payload["project_id"] == 10

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_noop_when_broadcaster_raises(self, mock_config, mock_get_broadcaster):
        """broadcast_card_refresh should not raise even if broadcaster fails."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
        mock_get_broadcaster.side_effect = RuntimeError("No broadcaster")

        agent = _make_agent()
        # Should not raise
        broadcast_card_refresh(agent, "test")

    def test_noop_without_broadcaster(self):
        """broadcast_card_refresh should not raise when no broadcaster is available."""
        agent = _make_agent()
        # Should not raise even without any mocking
        broadcast_card_refresh(agent, "test")


class TestGetQuestionOptions:
    """Tests for get_question_options()."""

    def test_returns_tool_input_for_awaiting_input(self):
        from claude_headspace.models.turn import TurnActor, TurnIntent

        tool_input = {
            "questions": [{
                "question": "Which database?",
                "options": [
                    {"label": "PostgreSQL", "description": "Relational"},
                    {"label": "MongoDB", "description": "Document"},
                ],
            }]
        }

        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.tool_input = tool_input

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [mock_turn]

        agent = _make_agent(state=TaskState.AWAITING_INPUT)
        agent.get_current_task.return_value = mock_task

        result = get_question_options(agent)
        assert result == tool_input

    def test_returns_none_when_not_awaiting_input(self):
        agent = _make_agent(state=TaskState.PROCESSING)
        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        agent.get_current_task.return_value = mock_task

        result = get_question_options(agent)
        assert result is None

    def test_returns_none_when_no_task(self):
        agent = _make_agent()
        agent.get_current_task.return_value = None

        result = get_question_options(agent)
        assert result is None

    def test_returns_none_when_turn_has_no_tool_input(self):
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.tool_input = None

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [mock_turn]

        agent = _make_agent(state=TaskState.AWAITING_INPUT)
        agent.get_current_task.return_value = mock_task

        result = get_question_options(agent)
        assert result is None

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_build_card_state_includes_question_options(self, mock_config):
        from claude_headspace.models.turn import TurnActor, TurnIntent

        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        tool_input = {
            "questions": [{
                "question": "Which?",
                "options": [{"label": "A", "description": "Option A"}],
            }]
        }

        mock_turn = MagicMock()
        mock_turn.actor = TurnActor.AGENT
        mock_turn.intent = TurnIntent.QUESTION
        mock_turn.tool_input = tool_input
        mock_turn.summary = None
        mock_turn.text = "Which?"

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [mock_turn]
        mock_task.instruction = "Test task"
        mock_task.completion_summary = None
        mock_task.started_at = None

        agent = _make_agent(state=TaskState.AWAITING_INPUT)
        agent.get_current_task.return_value = mock_task

        result = build_card_state(agent)
        assert result["question_options"] == tool_input

    @patch("claude_headspace.services.card_state._get_dashboard_config")
    def test_build_card_state_omits_question_options_when_none(self, mock_config):
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}

        agent = _make_agent(state=TaskState.IDLE)
        result = build_card_state(agent)
        assert "question_options" not in result
