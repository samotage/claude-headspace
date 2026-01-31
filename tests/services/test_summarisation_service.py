"""Unit tests for summarisation service."""

from datetime import datetime, timezone
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
def service(mock_inference):
    return SummarisationService(inference_service=mock_inference)


@pytest.fixture
def mock_turn():
    turn = MagicMock()
    turn.id = 1
    turn.text = "Refactoring the authentication middleware"
    turn.actor.value = "agent"
    turn.intent.value = "progress"
    turn.summary = None
    turn.summary_generated_at = None
    turn.task_id = 10
    turn.task.agent_id = 5
    turn.task.agent.project_id = 3
    return turn


@pytest.fixture
def mock_task():
    task = MagicMock()
    task.id = 10
    task.started_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
    task.completed_at = datetime(2026, 1, 31, 10, 30, 0, tzinfo=timezone.utc)
    task.summary = None
    task.summary_generated_at = None
    task.agent_id = 5
    task.agent.project_id = 3

    # Create mock turns
    mock_turn_1 = MagicMock()
    mock_turn_1.text = "Started refactoring auth"
    mock_turn_2 = MagicMock()
    mock_turn_2.text = "All 12 tests passing"
    task.turns = [mock_turn_1, mock_turn_2]

    return task


class TestTurnSummarisation:

    def test_successful_turn_summarisation(self, service, mock_inference, mock_turn):
        mock_inference.infer.return_value = InferenceResult(
            text="Agent refactored authentication middleware.",
            input_tokens=50,
            output_tokens=10,
            model="anthropic/claude-3-5-haiku-20241022",
            latency_ms=200,
        )

        result = service.summarise_turn(mock_turn)

        assert result == "Agent refactored authentication middleware."
        assert mock_turn.summary == "Agent refactored authentication middleware."
        assert mock_turn.summary_generated_at is not None
        mock_inference.infer.assert_called_once()
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["level"] == "turn"
        assert call_kwargs["purpose"] == "summarise_turn"
        assert call_kwargs["turn_id"] == 1
        assert call_kwargs["task_id"] == 10
        assert call_kwargs["agent_id"] == 5
        assert call_kwargs["project_id"] == 3

    def test_existing_summary_returned_without_inference(self, service, mock_inference, mock_turn):
        mock_turn.summary = "Existing summary"

        result = service.summarise_turn(mock_turn)

        assert result == "Existing summary"
        mock_inference.infer.assert_not_called()

    def test_inference_unavailable_returns_none(self, mock_inference, mock_turn):
        mock_inference.is_available = False
        service = SummarisationService(inference_service=mock_inference)

        result = service.summarise_turn(mock_turn)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_inference_error_returns_none(self, service, mock_inference, mock_turn):
        mock_inference.infer.side_effect = Exception("API error")

        result = service.summarise_turn(mock_turn)

        assert result is None
        assert mock_turn.summary is None

    def test_summary_persisted_with_db_session(self, service, mock_inference, mock_turn):
        mock_inference.infer.return_value = InferenceResult(
            text="Summary text",
            input_tokens=50,
            output_tokens=10,
            model="model",
            latency_ms=200,
        )
        mock_session = MagicMock()

        result = service.summarise_turn(mock_turn, db_session=mock_session)

        assert result == "Summary text"
        mock_session.add.assert_called_once_with(mock_turn)
        mock_session.commit.assert_called_once()

    def test_turn_prompt_includes_context(self, service, mock_turn):
        prompt = service._build_turn_prompt(mock_turn)

        assert "Refactoring the authentication middleware" in prompt
        assert "agent" in prompt
        assert "progress" in prompt
        assert "1-2 concise sentences" in prompt


class TestTaskSummarisation:

    def test_successful_task_summarisation(self, service, mock_inference, mock_task):
        mock_inference.infer.return_value = InferenceResult(
            text="Completed auth refactoring with 12 tests passing.",
            input_tokens=80,
            output_tokens=15,
            model="anthropic/claude-3-5-haiku-20241022",
            latency_ms=300,
        )

        result = service.summarise_task(mock_task)

        assert result == "Completed auth refactoring with 12 tests passing."
        assert mock_task.summary == "Completed auth refactoring with 12 tests passing."
        assert mock_task.summary_generated_at is not None
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["level"] == "task"
        assert call_kwargs["purpose"] == "summarise_task"
        assert call_kwargs["task_id"] == 10
        assert call_kwargs["agent_id"] == 5
        assert call_kwargs["project_id"] == 3

    def test_existing_task_summary_returned(self, service, mock_inference, mock_task):
        mock_task.summary = "Already summarised"

        result = service.summarise_task(mock_task)

        assert result == "Already summarised"
        mock_inference.infer.assert_not_called()

    def test_inference_unavailable_for_task(self, mock_inference, mock_task):
        mock_inference.is_available = False
        service = SummarisationService(inference_service=mock_inference)

        result = service.summarise_task(mock_task)

        assert result is None

    def test_task_inference_error_returns_none(self, service, mock_inference, mock_task):
        mock_inference.infer.side_effect = Exception("API failure")

        result = service.summarise_task(mock_task)

        assert result is None
        assert mock_task.summary is None

    def test_task_prompt_includes_context(self, service, mock_task):
        prompt = service._build_task_prompt(mock_task)

        assert "2-3 sentences" in prompt
        assert "All 12 tests passing" in prompt
        assert "Turns: 2" in prompt

    def test_task_summary_persisted_with_db_session(self, service, mock_inference, mock_task):
        mock_inference.infer.return_value = InferenceResult(
            text="Task summary",
            input_tokens=80,
            output_tokens=15,
            model="model",
            latency_ms=300,
        )
        mock_session = MagicMock()

        result = service.summarise_task(mock_task, db_session=mock_session)

        assert result == "Task summary"
        mock_session.add.assert_called_once_with(mock_task)
        mock_session.commit.assert_called_once()


class TestAsyncSummarisation:

    def test_async_turn_skipped_when_unavailable(self, mock_inference):
        mock_inference.is_available = False
        service = SummarisationService(inference_service=mock_inference)

        # Should not raise or start a thread
        service.summarise_turn_async(1)

    def test_async_turn_skipped_without_app(self, mock_inference):
        service = SummarisationService(inference_service=mock_inference, app=None)

        # Should not raise
        service.summarise_turn_async(1)

    def test_async_task_skipped_when_unavailable(self, mock_inference):
        mock_inference.is_available = False
        service = SummarisationService(inference_service=mock_inference)

        service.summarise_task_async(1)

    def test_async_task_skipped_without_app(self, mock_inference):
        service = SummarisationService(inference_service=mock_inference, app=None)

        service.summarise_task_async(1)


class TestSSEBroadcast:

    def test_broadcast_summary_update(self, service):
        with patch("src.claude_headspace.services.broadcaster.get_broadcaster") as mock_get:
            mock_broadcaster = MagicMock()
            mock_get.return_value = mock_broadcaster

            service._broadcast_summary_update(
                event_type="turn_summary",
                entity_id=1,
                summary="Test summary",
                agent_id=5,
                project_id=3,
            )

            mock_broadcaster.broadcast.assert_called_once()
            call_args = mock_broadcaster.broadcast.call_args
            assert call_args[0][0] == "turn_summary"
            assert call_args[0][1]["summary"] == "Test summary"
            assert call_args[0][1]["agent_id"] == 5
            assert call_args[0][1]["project_id"] == 3

    def test_broadcast_failure_non_fatal(self, service):
        with patch("src.claude_headspace.services.broadcaster.get_broadcaster") as mock_get:
            mock_get.side_effect = RuntimeError("No broadcaster")

            # Should not raise
            service._broadcast_summary_update(
                event_type="turn_summary",
                entity_id=1,
                summary="Test",
            )
