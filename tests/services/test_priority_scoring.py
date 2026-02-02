"""Unit tests for priority scoring service."""

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.claude_headspace.services.priority_scoring import PriorityScoringService
from src.claude_headspace.services.openrouter_client import InferenceResult


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    return service


@pytest.fixture
def service(mock_inference):
    return PriorityScoringService(inference_service=mock_inference)


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = 1
    agent.project.name = "test-project"
    agent.project.path = "/test/path"
    agent.state.value = "processing"
    agent.ended_at = None
    agent.priority_score = None
    agent.priority_reason = None
    agent.priority_updated_at = None
    # Mock get_current_task
    mock_task = MagicMock()
    mock_task.started_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
    mock_task.turns = []
    agent.get_current_task.return_value = mock_task
    return agent


@pytest.fixture
def mock_agent_2():
    agent = MagicMock()
    agent.id = 2
    agent.project.name = "other-project"
    agent.project.path = "/other/path"
    agent.state.value = "awaiting_input"
    agent.ended_at = None
    agent.priority_score = None
    agent.priority_reason = None
    agent.priority_updated_at = None
    mock_task = MagicMock()
    mock_task.started_at = datetime(2026, 1, 31, 9, 30, 0, tzinfo=timezone.utc)
    mock_task.turns = []
    agent.get_current_task.return_value = mock_task
    return agent


class TestScoringContextFallback:

    def test_objective_context_when_set(self, service):
        mock_session = MagicMock()
        mock_objective = MagicMock()
        mock_objective.current_text = "Ship auth feature by Friday"
        mock_objective.constraints = "Must pass security review"
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_objective

        context = service._get_scoring_context(mock_session, [])

        assert context["context_type"] == "objective"
        assert context["text"] == "Ship auth feature by Friday"
        assert context["constraints"] == "Must pass security review"

    def test_waypoint_fallback_when_no_objective(self, service, mock_agent):
        mock_session = MagicMock()
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        wp_result = MagicMock()
        wp_result.exists = True
        wp_result.content = "# Waypoint\n\n## Next Up\n\nFix login bug\n\n## Upcoming\n\nAdd search"

        with patch("src.claude_headspace.services.waypoint_editor.load_waypoint", return_value=wp_result):
            context = service._get_scoring_context(mock_session, [mock_agent])

        assert context["context_type"] == "waypoint"
        assert "Fix login bug" in context["text"]

    def test_default_context_when_no_objective_or_waypoint(self, service, mock_agent):
        mock_session = MagicMock()
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        wp_result = MagicMock()
        wp_result.exists = False

        with patch("src.claude_headspace.services.waypoint_editor.load_waypoint", return_value=wp_result):
            context = service._get_scoring_context(mock_session, [mock_agent])

        assert context["context_type"] == "default"


class TestBuildScoringPrompt:

    def test_prompt_includes_objective_context(self, service, mock_agent):
        context = {
            "context_type": "objective",
            "text": "Ship auth by Friday",
            "constraints": "Security review required",
        }

        prompt = service._build_scoring_prompt(context, [mock_agent])

        assert "Current Objective: Ship auth by Friday" in prompt
        assert "Constraints: Security review required" in prompt
        assert "Agent ID: 1" in prompt
        assert "test-project" in prompt

    def test_prompt_includes_waypoint_context(self, service, mock_agent):
        context = {
            "context_type": "waypoint",
            "text": "Project (/test):\n  Next Up: Fix bug\n  Upcoming: Add search",
            "constraints": "",
        }

        prompt = service._build_scoring_prompt(context, [mock_agent])

        assert "Project Priorities:" in prompt
        assert "Fix bug" in prompt

    def test_prompt_includes_scoring_factors(self, service, mock_agent):
        context = {"context_type": "objective", "text": "Test", "constraints": ""}

        prompt = service._build_scoring_prompt(context, [mock_agent])

        assert "Objective/waypoint alignment (40%)" in prompt
        assert "Agent state (25%)" in prompt
        assert "Task duration (15%)" in prompt
        assert "JSON array" in prompt

    def test_prompt_includes_task_summary(self, service, mock_agent):
        mock_turn = MagicMock()
        mock_turn.summary = "Refactoring auth middleware"
        mock_turn.text = "Working on auth"
        mock_agent.get_current_task.return_value.turns = [mock_turn]

        context = {"context_type": "objective", "text": "Test", "constraints": ""}
        prompt = service._build_scoring_prompt(context, [mock_agent])

        assert "Refactoring auth middleware" in prompt


class TestParseResponse:

    def test_valid_json_parsed(self, service):
        response = json.dumps([
            {"agent_id": 1, "score": 85, "reason": "High alignment"},
            {"agent_id": 2, "score": 40, "reason": "Low alignment"},
        ])

        results = service._parse_scoring_response(response, [1, 2])

        assert len(results) == 2
        assert results[0]["agent_id"] == 1
        assert results[0]["score"] == 85
        assert results[0]["reason"] == "High alignment"

    def test_score_clamped_to_range(self, service):
        response = json.dumps([
            {"agent_id": 1, "score": 150, "reason": "Over max"},
            {"agent_id": 2, "score": -10, "reason": "Under min"},
        ])

        results = service._parse_scoring_response(response, [1, 2])

        assert results[0]["score"] == 100
        assert results[1]["score"] == 0

    def test_malformed_json_returns_empty(self, service):
        results = service._parse_scoring_response("not json at all", [1, 2])
        assert results == []

    def test_no_array_returns_empty(self, service):
        results = service._parse_scoring_response('{"score": 50}', [1, 2])
        assert results == []

    def test_unknown_agent_ids_filtered(self, service):
        response = json.dumps([
            {"agent_id": 1, "score": 85, "reason": "Known"},
            {"agent_id": 999, "score": 40, "reason": "Unknown"},
        ])

        results = service._parse_scoring_response(response, [1, 2])

        assert len(results) == 1
        assert results[0]["agent_id"] == 1

    def test_json_embedded_in_text(self, service):
        response = 'Here are the scores:\n[{"agent_id": 1, "score": 75, "reason": "Good"}]\nDone.'

        results = service._parse_scoring_response(response, [1])

        assert len(results) == 1
        assert results[0]["score"] == 75

    def test_non_numeric_score_defaults_to_50(self, service):
        response = json.dumps([{"agent_id": 1, "score": "high", "reason": "Test"}])

        results = service._parse_scoring_response(response, [1])

        assert results[0]["score"] == 50


class TestPriorityDisabledGuard:

    def test_scoring_skipped_when_disabled(self, service, mock_agent):
        """Scoring returns early with context_type 'disabled' when priority_enabled is False."""
        mock_session = MagicMock()

        mock_objective = MagicMock()
        mock_objective.priority_enabled = False
        mock_session.query.return_value.first.return_value = mock_objective

        result = service.score_all_agents(mock_session)

        assert result["scored"] == 0
        assert result["context_type"] == "disabled"
        assert result["agents"] == []

    def test_scoring_proceeds_when_no_objective(self, service, mock_agent):
        """No objective means not disabled — scoring should proceed (existing fallback)."""
        mock_session = MagicMock()
        # First query (Objective) returns None
        # Second query (Agent filter) returns agents
        # Third query (Objective order_by) for context also returns None
        mock_session.query.return_value.first.return_value = None
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_agent]
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        wp_result = MagicMock()
        wp_result.exists = False

        with patch("src.claude_headspace.services.waypoint_editor.load_waypoint", return_value=wp_result):
            result = service.score_all_agents(mock_session)

        # Should not be "disabled" — it should proceed to default scoring
        assert result["context_type"] == "default"
        assert result["scored"] == 1


class TestScoreAllAgents:

    def test_no_agents_returns_empty(self, service):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = service.score_all_agents(mock_session)

        assert result["scored"] == 0
        assert result["agents"] == []
        assert result["context_type"] == "none"

    def test_default_context_assigns_50(self, service, mock_agent):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_agent]
        # No objective
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        wp_result = MagicMock()
        wp_result.exists = False

        with patch("src.claude_headspace.services.waypoint_editor.load_waypoint", return_value=wp_result):
            result = service.score_all_agents(mock_session)

        assert result["scored"] == 1
        assert result["context_type"] == "default"
        assert mock_agent.priority_score == 50
        assert mock_agent.priority_reason == "No scoring context available"

    def test_successful_scoring_persists(self, service, mock_inference, mock_agent, mock_agent_2):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_agent, mock_agent_2]

        mock_objective = MagicMock()
        mock_objective.current_text = "Ship auth"
        mock_objective.constraints = ""
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_objective

        mock_inference.infer.return_value = InferenceResult(
            text=json.dumps([
                {"agent_id": 1, "score": 85, "reason": "Aligned with auth"},
                {"agent_id": 2, "score": 60, "reason": "Waiting for input"},
            ]),
            input_tokens=200,
            output_tokens=50,
            model="anthropic/claude-3-haiku",
            latency_ms=500,
        )

        result = service.score_all_agents(mock_session)

        assert result["scored"] == 2
        assert result["context_type"] == "objective"
        assert mock_agent.priority_score == 85
        assert mock_agent_2.priority_score == 60
        mock_session.commit.assert_called()

    def test_inference_error_preserves_scores(self, service, mock_inference, mock_agent):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_agent]

        mock_objective = MagicMock()
        mock_objective.current_text = "Test"
        mock_objective.constraints = ""
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_objective

        mock_inference.infer.side_effect = Exception("API error")

        result = service.score_all_agents(mock_session)

        assert result["scored"] == 0
        # Original score should not be modified
        assert mock_agent.priority_score is None


class TestDebounceTrigger:

    def test_trigger_scoring_debounces(self, service, mock_inference):
        with patch.object(service, "score_all_agents_async") as mock_async:
            service.trigger_scoring()
            # Timer set but not fired yet
            mock_async.assert_not_called()

    def test_trigger_immediate_bypasses_debounce(self, service, mock_inference):
        with patch.object(service, "score_all_agents_async") as mock_async:
            service.trigger_scoring_immediate()
            mock_async.assert_called_once()

    def test_trigger_immediate_cancels_pending(self, service, mock_inference):
        with patch.object(service, "score_all_agents_async") as mock_async:
            service.trigger_scoring()  # Set debounce timer
            service.trigger_scoring_immediate()  # Should cancel and fire immediately
            assert mock_async.call_count == 1

    def test_trigger_skipped_when_unavailable(self, mock_inference):
        mock_inference.is_available = False
        service = PriorityScoringService(inference_service=mock_inference)

        with patch.object(service, "score_all_agents_async") as mock_async:
            service.trigger_scoring()
            mock_async.assert_not_called()


class TestAsyncScoring:

    def test_async_skipped_when_unavailable(self, mock_inference):
        mock_inference.is_available = False
        service = PriorityScoringService(inference_service=mock_inference)
        service.score_all_agents_async()  # Should not raise

    def test_async_skipped_without_app(self, mock_inference):
        service = PriorityScoringService(inference_service=mock_inference, app=None)
        service.score_all_agents_async()  # Should not raise


class TestExtractSection:

    def test_extract_next_up(self):
        content = "# Waypoint\n\n## Next Up\n\nFix login bug\nAdd tests\n\n## Upcoming\n\nSearch feature"
        result = PriorityScoringService._extract_section(content, "Next Up")
        assert "Fix login bug" in result
        assert "Add tests" in result

    def test_extract_missing_section(self):
        content = "# Waypoint\n\n## Later\n\nSome stuff"
        result = PriorityScoringService._extract_section(content, "Next Up")
        assert result == "None"

    def test_extract_removes_html_comments(self):
        content = "# Waypoint\n\n## Next Up\n\n<!-- placeholder -->\n\n## Upcoming\n\nStuff"
        result = PriorityScoringService._extract_section(content, "Next Up")
        assert result == "None"


class TestSSEBroadcast:

    def test_broadcast_score_update(self, service):
        with patch("src.claude_headspace.services.broadcaster.get_broadcaster") as mock_get:
            mock_broadcaster = MagicMock()
            mock_get.return_value = mock_broadcaster

            service._broadcast_score_update([
                {"agent_id": 1, "score": 85, "reason": "Test"},
            ])

            mock_broadcaster.broadcast.assert_called_once()
            call_args = mock_broadcaster.broadcast.call_args
            assert call_args[0][0] == "priority_update"
            assert call_args[0][1]["agents"][0]["score"] == 85

    def test_broadcast_failure_non_fatal(self, service):
        with patch("src.claude_headspace.services.broadcaster.get_broadcaster") as mock_get:
            mock_get.side_effect = RuntimeError("No broadcaster")
            # Should not raise
            service._broadcast_score_update([{"agent_id": 1, "score": 85, "reason": "Test"}])
