"""Unit tests for frustration extraction in SummarisationService."""

from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.services.summarisation_service import SummarisationService
from src.claude_headspace.services.openrouter_client import InferenceResult


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    return service


@pytest.fixture
def service_headspace_enabled(mock_inference):
    config = {"headspace": {"enabled": True}}
    return SummarisationService(inference_service=mock_inference, config=config)


@pytest.fixture
def service_headspace_disabled(mock_inference):
    config = {"headspace": {"enabled": False}}
    return SummarisationService(inference_service=mock_inference, config=config)


@pytest.fixture
def user_turn():
    turn = MagicMock()
    turn.id = 1
    turn.text = "This still isn't working, I've told you three times!!"
    turn.actor.value = "user"
    turn.intent.value = "command"
    turn.summary = None
    turn.summary_generated_at = None
    turn.frustration_score = None
    turn.command_id = 10
    turn.command.agent_id = 5
    turn.command.agent.project_id = 3
    turn.command.instruction = None
    turn.command.agent.project.inference_paused = None
    return turn


@pytest.fixture
def agent_turn():
    turn = MagicMock()
    turn.id = 2
    turn.text = "I've refactored the authentication module"
    turn.actor.value = "agent"
    turn.intent.value = "progress"
    turn.summary = None
    turn.summary_generated_at = None
    turn.frustration_score = None
    turn.command_id = 10
    turn.command.agent_id = 5
    turn.command.agent.project_id = 3
    turn.command.instruction = None
    turn.command.agent.project.inference_paused = None
    return turn


class TestFrustrationPromptSelection:

    def test_user_turn_uses_frustration_prompt(self, service_headspace_enabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text='{"summary": "User frustrated", "frustration_score": 7}',
            input_tokens=50, output_tokens=20, model="model", latency_ms=200,
        )

        with patch.object(service_headspace_enabled, "_trigger_headspace_recalculation"):
            result = service_headspace_enabled.summarise_turn(user_turn)

        call_kwargs = mock_inference.infer.call_args[1]
        assert "frustration" in call_kwargs["input_text"].lower()
        assert "frustration_score" in call_kwargs["input_text"]

    def test_agent_turn_uses_standard_prompt(self, service_headspace_enabled, mock_inference, agent_turn):
        mock_inference.infer.return_value = InferenceResult(
            text="Agent refactored authentication.",
            input_tokens=50, output_tokens=10, model="model", latency_ms=200,
        )

        result = service_headspace_enabled.summarise_turn(agent_turn)

        call_kwargs = mock_inference.infer.call_args[1]
        # Standard prompt does not contain frustration_score
        assert "frustration_score" not in call_kwargs["input_text"]

    def test_headspace_disabled_uses_standard_prompt(self, service_headspace_disabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text="User requested fix.",
            input_tokens=50, output_tokens=10, model="model", latency_ms=200,
        )

        result = service_headspace_disabled.summarise_turn(user_turn)

        call_kwargs = mock_inference.infer.call_args[1]
        assert "frustration_score" not in call_kwargs["input_text"]


class TestFrustrationParsing:

    def test_valid_json_extracts_score(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "User is frustrated", "frustration_score": 7}'
        )
        assert summary == "User is frustrated"
        assert score == 7

    def test_score_zero(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "Calm request", "frustration_score": 0}'
        )
        assert summary == "Calm request"
        assert score == 0

    def test_score_ten(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "Very angry", "frustration_score": 10}'
        )
        assert summary == "Very angry"
        assert score == 10

    def test_score_out_of_range_high(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "text", "frustration_score": 15}'
        )
        assert summary == "text"
        assert score is None

    def test_score_out_of_range_negative(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "text", "frustration_score": -1}'
        )
        assert summary == "text"
        assert score is None

    def test_invalid_json_fallback(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            "Just a plain text response"
        )
        assert summary == "Just a plain text response"
        assert score is None

    def test_json_missing_score_key(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "text without score"}'
        )
        assert summary == "text without score"
        assert score is None

    def test_score_as_float_truncated(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "text", "frustration_score": 5.7}'
        )
        assert summary == "text"
        assert score == 5

    def test_preamble_stripped_from_json_summary(self, service_headspace_enabled):
        summary, score = service_headspace_enabled._parse_frustration_response(
            '{"summary": "Here\'s a concise summary: User is upset", "frustration_score": 6}'
        )
        assert "User is upset" in summary
        assert score == 6


class TestFrustrationIntegration:

    def test_successful_extraction_sets_turn_attributes(self, service_headspace_enabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text='{"summary": "User frustrated about bug", "frustration_score": 7}',
            input_tokens=50, output_tokens=20, model="model", latency_ms=200,
        )

        with patch.object(service_headspace_enabled, "_trigger_headspace_recalculation"):
            result = service_headspace_enabled.summarise_turn(user_turn)

        assert result == "User frustrated about bug"
        assert user_turn.summary == "User frustrated about bug"
        assert user_turn.frustration_score == 7
        assert user_turn.summary_generated_at is not None

    def test_json_parse_failure_sets_summary_only(self, service_headspace_enabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text="Not valid JSON response",
            input_tokens=50, output_tokens=10, model="model", latency_ms=200,
        )

        result = service_headspace_enabled.summarise_turn(user_turn)

        assert result == "Not valid JSON response"
        assert user_turn.summary == "Not valid JSON response"
        assert user_turn.frustration_score is None

    def test_triggers_headspace_recalculation(self, service_headspace_enabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text='{"summary": "User annoyed", "frustration_score": 5}',
            input_tokens=50, output_tokens=20, model="model", latency_ms=200,
        )

        with patch.object(service_headspace_enabled, "_trigger_headspace_recalculation") as mock_trigger:
            service_headspace_enabled.summarise_turn(user_turn)
            mock_trigger.assert_called_once_with(user_turn)

    def test_no_recalculation_when_score_is_none(self, service_headspace_enabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text="Plain text response",
            input_tokens=50, output_tokens=10, model="model", latency_ms=200,
        )

        with patch.object(service_headspace_enabled, "_trigger_headspace_recalculation") as mock_trigger:
            service_headspace_enabled.summarise_turn(user_turn)
            mock_trigger.assert_not_called()

    def test_recalculation_failure_non_fatal(self, service_headspace_enabled, mock_inference, user_turn):
        mock_inference.infer.return_value = InferenceResult(
            text='{"summary": "Annoyed", "frustration_score": 6}',
            input_tokens=50, output_tokens=20, model="model", latency_ms=200,
        )

        with patch.object(
            service_headspace_enabled, "_trigger_headspace_recalculation",
            side_effect=Exception("Monitor error"),
        ):
            # Should not raise
            result = service_headspace_enabled.summarise_turn(user_turn)
            assert result == "Annoyed"
