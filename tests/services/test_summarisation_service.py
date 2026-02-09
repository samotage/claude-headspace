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
    task.completion_summary = None
    task.completion_summary_generated_at = None
    task.instruction = "Refactor the authentication middleware and ensure tests pass"
    task.instruction_generated_at = None
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
            model="anthropic/claude-3-haiku",
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
        prompt = service._resolve_turn_prompt(mock_turn)

        assert "Refactoring the authentication middleware" in prompt
        assert "agent" in prompt
        assert "progress" in prompt
        assert "18 tokens" in prompt


class TestTaskSummarisation:

    def test_successful_task_summarisation(self, service, mock_inference, mock_task):
        mock_inference.infer.return_value = InferenceResult(
            text="Completed auth refactoring with 12 tests passing.",
            input_tokens=80,
            output_tokens=15,
            model="anthropic/claude-3-haiku",
            latency_ms=300,
        )

        result = service.summarise_task(mock_task)

        assert result == "Completed auth refactoring with 12 tests passing."
        assert mock_task.completion_summary == "Completed auth refactoring with 12 tests passing."
        assert mock_task.completion_summary_generated_at is not None
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["level"] == "task"
        assert call_kwargs["purpose"] == "summarise_task"
        assert call_kwargs["task_id"] == 10
        assert call_kwargs["agent_id"] == 5
        assert call_kwargs["project_id"] == 3

    def test_existing_task_summary_returned(self, service, mock_inference, mock_task):
        mock_task.completion_summary = "Already summarised"

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
        assert mock_task.completion_summary is None

    def test_task_prompt_includes_context(self, service, mock_task):
        prompt = service._resolve_task_prompt(mock_task)

        assert "18 tokens" in prompt
        assert "All 12 tests passing" in prompt
        assert "Refactor the authentication middleware" in prompt
        assert "Task:" in prompt

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


class TestInstructionSummarisation:
    """Tests for summarise_instruction() — prompt building, persistence, empty text guard."""

    def test_successful_instruction_summarisation(self, service, mock_inference, mock_task):
        mock_task.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Refactor authentication middleware and verify tests.",
            input_tokens=40,
            output_tokens=10,
            model="anthropic/claude-3-haiku",
            latency_ms=150,
        )

        result = service.summarise_instruction(mock_task, "Please refactor the auth middleware and make sure all tests pass")

        assert result == "Refactor authentication middleware and verify tests."
        assert mock_task.instruction == "Refactor authentication middleware and verify tests."
        assert mock_task.instruction_generated_at is not None
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["level"] == "turn"
        assert call_kwargs["purpose"] == "summarise_instruction"
        assert call_kwargs["task_id"] == 10

    def test_existing_instruction_returned(self, service, mock_inference, mock_task):
        mock_task.instruction = "Already set instruction"

        result = service.summarise_instruction(mock_task, "Some command text")

        assert result == "Already set instruction"
        mock_inference.infer.assert_not_called()

    def test_empty_command_text_returns_none(self, service, mock_inference, mock_task):
        mock_task.instruction = None

        result = service.summarise_instruction(mock_task, "")

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_whitespace_only_command_text_returns_none(self, service, mock_inference, mock_task):
        mock_task.instruction = None

        result = service.summarise_instruction(mock_task, "   \n  ")

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_none_command_text_returns_none(self, service, mock_inference, mock_task):
        mock_task.instruction = None

        result = service.summarise_instruction(mock_task, None)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_inference_unavailable_returns_none(self, mock_inference, mock_task):
        mock_inference.is_available = False
        mock_task.instruction = None
        service = SummarisationService(inference_service=mock_inference)

        result = service.summarise_instruction(mock_task, "Some command")

        assert result is None

    def test_inference_error_returns_none(self, service, mock_inference, mock_task):
        mock_task.instruction = None
        mock_inference.infer.side_effect = Exception("API failure")

        result = service.summarise_instruction(mock_task, "Some command")

        assert result is None
        assert mock_task.instruction is None

    def test_instruction_persisted_with_db_session(self, service, mock_inference, mock_task):
        mock_task.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Instruction summary",
            input_tokens=40,
            output_tokens=10,
            model="model",
            latency_ms=150,
        )
        mock_session = MagicMock()

        result = service.summarise_instruction(mock_task, "Some command", db_session=mock_session)

        assert result == "Instruction summary"
        mock_session.add.assert_called_once_with(mock_task)
        mock_session.commit.assert_called_once()

    def test_instruction_prompt_includes_command_text(self, service, mock_inference, mock_task):
        mock_task.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Summary",
            input_tokens=40,
            output_tokens=10,
            model="model",
            latency_ms=150,
        )

        service.summarise_instruction(mock_task, "Fix the login page CSS styling")

        call_kwargs = mock_inference.infer.call_args[1]
        assert "Fix the login page CSS styling" in call_kwargs["input_text"]
        assert "stating the goal" in call_kwargs["input_text"]


class TestExecutePending:
    """Tests for execute_pending() — synchronous post-commit summarisation."""

    def test_execute_pending_turn(self, service, mock_inference):
        """execute_pending should call summarise_turn for turn requests."""
        from src.claude_headspace.services.task_lifecycle import SummarisationRequest

        mock_turn = MagicMock()
        mock_turn.id = 1
        mock_turn.text = "Working on fix"
        mock_turn.summary = None
        mock_turn.task.agent_id = 5
        mock_turn.task.agent.project_id = 3

        mock_inference.infer.return_value = InferenceResult(
            text="Turn summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        mock_session = MagicMock()
        requests = [SummarisationRequest(type="turn", turn=mock_turn)]

        with patch.object(service, "_broadcast_summary_update") as mock_broadcast:
            service.execute_pending(requests, mock_session)

            assert mock_turn.summary == "Turn summary"
            mock_broadcast.assert_called_once()
            call_kwargs = mock_broadcast.call_args[1]
            assert call_kwargs["event_type"] == "turn_summary"
            assert call_kwargs["entity_id"] == 1

    def test_execute_pending_instruction(self, service, mock_inference):
        """execute_pending should call summarise_instruction for instruction requests."""
        from src.claude_headspace.services.task_lifecycle import SummarisationRequest

        mock_task = MagicMock()
        mock_task.id = 10
        mock_task.instruction = None
        mock_task.agent_id = 5
        mock_task.agent.project_id = 3

        mock_inference.infer.return_value = InferenceResult(
            text="Instruction summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        mock_session = MagicMock()
        requests = [SummarisationRequest(type="instruction", task=mock_task, command_text="Fix the bug")]

        with patch.object(service, "_broadcast_summary_update") as mock_broadcast:
            service.execute_pending(requests, mock_session)

            assert mock_task.instruction == "Instruction summary"
            mock_broadcast.assert_called_once()
            call_kwargs = mock_broadcast.call_args[1]
            assert call_kwargs["event_type"] == "instruction_summary"
            assert call_kwargs["entity_id"] == 10

    def test_execute_pending_task_completion(self, service, mock_inference):
        """execute_pending should call summarise_task for task_completion requests."""
        from src.claude_headspace.services.task_lifecycle import SummarisationRequest

        mock_task = MagicMock()
        mock_task.id = 10
        mock_task.completion_summary = None
        mock_task.instruction = "Fix the bug"
        mock_task.agent_id = 5
        mock_task.agent.project_id = 3
        mock_turn = MagicMock()
        mock_turn.text = "All done"
        mock_task.turns = [mock_turn]

        mock_inference.infer.return_value = InferenceResult(
            text="Task completion summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        mock_session = MagicMock()
        requests = [SummarisationRequest(type="task_completion", task=mock_task)]

        with patch.object(service, "_broadcast_summary_update") as mock_broadcast:
            service.execute_pending(requests, mock_session)

            assert mock_task.completion_summary == "Task completion summary"
            mock_broadcast.assert_called_once()
            call_kwargs = mock_broadcast.call_args[1]
            assert call_kwargs["event_type"] == "task_summary"
            assert call_kwargs["extra"] == {"is_completion": True}

    def test_execute_pending_error_non_fatal(self, service, mock_inference):
        """execute_pending should continue processing after an error."""
        from src.claude_headspace.services.task_lifecycle import SummarisationRequest

        mock_turn_1 = MagicMock()
        mock_turn_1.id = 1
        mock_turn_1.text = "First"
        mock_turn_1.summary = None
        mock_turn_1.task.agent_id = 5
        mock_turn_1.task.agent.project_id = 3

        mock_turn_2 = MagicMock()
        mock_turn_2.id = 2
        mock_turn_2.text = "Second"
        mock_turn_2.summary = None
        mock_turn_2.task.agent_id = 5
        mock_turn_2.task.agent.project_id = 3

        # First call fails, second succeeds
        mock_inference.infer.side_effect = [
            Exception("API error"),
            InferenceResult(text="Summary 2", input_tokens=10, output_tokens=5, model="model", latency_ms=100),
        ]

        mock_session = MagicMock()
        requests = [
            SummarisationRequest(type="turn", turn=mock_turn_1),
            SummarisationRequest(type="turn", turn=mock_turn_2),
        ]

        # Should not raise
        service.execute_pending(requests, mock_session)

        # Second turn should still be processed
        assert mock_turn_2.summary == "Summary 2"

    def test_execute_pending_empty_list(self, service):
        """execute_pending should handle empty list gracefully."""
        mock_session = MagicMock()
        # Should not raise
        service.execute_pending([], mock_session)


class TestResolveTaskPrompt:
    """Tests for _resolve_task_prompt() — correct inputs, no timestamps/turn counts."""

    def test_task_prompt_uses_instruction_and_final_turn(self, service, mock_task):
        prompt = service._resolve_task_prompt(mock_task)

        assert "Refactor the authentication middleware" in prompt
        assert "All 12 tests passing" in prompt

    def test_task_prompt_does_not_include_timestamps(self, service, mock_task):
        prompt = service._resolve_task_prompt(mock_task)

        assert "2026" not in prompt
        assert "started_at" not in prompt
        assert "completed_at" not in prompt

    def test_task_prompt_does_not_include_turn_counts(self, service, mock_task):
        prompt = service._resolve_task_prompt(mock_task)

        assert "Turns:" not in prompt
        assert "turns:" not in prompt

    def test_task_prompt_with_no_instruction(self, service, mock_task):
        mock_task.instruction = None

        prompt = service._resolve_task_prompt(mock_task)

        assert "No instruction recorded" in prompt

    def test_task_prompt_with_no_turns_uses_instruction_fallback(self, service, mock_task):
        mock_task.turns = []

        prompt = service._resolve_task_prompt(mock_task)

        assert prompt is not None
        assert "Refactor the authentication middleware" in prompt
        assert "no agent output was captured" in prompt


class TestResolveTurnPrompt:
    """Tests for _resolve_turn_prompt() — intent-aware templates, task instruction context, empty text guard."""

    def test_command_intent_uses_command_template(self, service):
        turn = MagicMock()
        turn.text = "Fix the login page"
        turn.actor.value = "user"
        turn.intent.value = "command"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "command" in prompt.lower()
        assert "Fix the login page" in prompt

    def test_question_intent_uses_question_template(self, service):
        turn = MagicMock()
        turn.text = "Which database should I use?"
        turn.actor.value = "agent"
        turn.intent.value = "question"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "what the agent needs to know" in prompt
        assert "Which database should I use?" in prompt

    def test_completion_intent_uses_completion_template(self, service):
        turn = MagicMock()
        turn.text = "All tests are now passing"
        turn.actor.value = "agent"
        turn.intent.value = "completion"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "what was accomplished" in prompt
        assert "All tests are now passing" in prompt

    def test_progress_intent_uses_progress_template(self, service):
        turn = MagicMock()
        turn.text = "Refactoring the auth middleware"
        turn.actor.value = "agent"
        turn.intent.value = "progress"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "progress" in prompt
        assert "Refactoring the auth middleware" in prompt

    def test_answer_intent_uses_answer_template(self, service):
        turn = MagicMock()
        turn.text = "Use PostgreSQL for the database"
        turn.actor.value = "user"
        turn.intent.value = "answer"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "what was confirmed or provided" in prompt
        assert "Use PostgreSQL" in prompt

    def test_end_of_task_intent_uses_end_template(self, service):
        turn = MagicMock()
        turn.text = "Task complete, all requirements met"
        turn.actor.value = "agent"
        turn.intent.value = "end_of_task"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "final outcome" in prompt
        assert "Task complete" in prompt

    def test_unknown_intent_uses_default_template(self, service):
        turn = MagicMock()
        turn.text = "Some text"
        turn.actor.value = "agent"
        turn.intent.value = "unknown_intent"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "18 tokens" in prompt
        assert "Some text" in prompt
        assert "agent" in prompt

    def test_turn_prompt_includes_task_instruction_context(self, service):
        turn = MagicMock()
        turn.text = "Working on auth refactoring"
        turn.actor.value = "agent"
        turn.intent.value = "progress"
        turn.task.instruction = "Refactor the authentication module"

        prompt = service._resolve_turn_prompt(turn)

        assert "Task instruction: Refactor the authentication module" in prompt

    def test_turn_prompt_without_task_instruction(self, service):
        turn = MagicMock()
        turn.text = "Some work"
        turn.actor.value = "agent"
        turn.intent.value = "progress"
        turn.task.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "Task instruction:" not in prompt


class TestTurnEmptyTextGuard:
    """Tests for empty text guard in summarise_turn()."""

    def test_empty_text_returns_none(self, service, mock_inference):
        turn = MagicMock()
        turn.text = ""
        turn.summary = None

        result = service.summarise_turn(turn)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_none_text_returns_none(self, service, mock_inference):
        turn = MagicMock()
        turn.text = None
        turn.summary = None

        result = service.summarise_turn(turn)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_whitespace_text_returns_none(self, service, mock_inference):
        turn = MagicMock()
        turn.text = "   \n  "
        turn.summary = None

        result = service.summarise_turn(turn)

        assert result is None
        mock_inference.infer.assert_not_called()


class TestTaskEmptyFinalTurnFallback:
    """Tests for fallback when final turn text is empty — uses turn activity or instruction-only."""

    def test_empty_final_turn_falls_back_to_activity(self, service, mock_inference, mock_task):
        """When final turn text is empty but earlier turns have text, use activity fallback."""
        mock_task.completion_summary = None
        mock_task.turns[-1].text = ""
        mock_inference.infer.return_value = InferenceResult(
            text="Task completed successfully.", input_tokens=50,
            output_tokens=10, model="model", latency_ms=200,
        )

        result = service.summarise_task(mock_task)

        assert result == "Task completed successfully."
        mock_inference.infer.assert_called_once()
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["purpose"] == "summarise_task"

    def test_none_final_turn_falls_back_to_activity(self, service, mock_inference, mock_task):
        """When final turn text is None but earlier turns have text, use activity fallback."""
        mock_task.completion_summary = None
        mock_task.turns[-1].text = None
        mock_inference.infer.return_value = InferenceResult(
            text="Task completed successfully.", input_tokens=50,
            output_tokens=10, model="model", latency_ms=200,
        )

        result = service.summarise_task(mock_task)

        assert result == "Task completed successfully."
        mock_inference.infer.assert_called_once()

    def test_whitespace_final_turn_falls_back_to_activity(self, service, mock_inference, mock_task):
        """When final turn text is whitespace-only, use activity fallback."""
        mock_task.completion_summary = None
        mock_task.turns[-1].text = "   "
        mock_inference.infer.return_value = InferenceResult(
            text="Task completed successfully.", input_tokens=50,
            output_tokens=10, model="model", latency_ms=200,
        )

        result = service.summarise_task(mock_task)

        assert result == "Task completed successfully."
        mock_inference.infer.assert_called_once()

    def test_all_turns_empty_uses_instruction_fallback(self, service, mock_inference, mock_task):
        """When all turns have empty text, falls back to instruction-only prompt."""
        mock_task.completion_summary = None
        for t in mock_task.turns:
            t.text = ""
            t.summary = None

        result = service.summarise_task(mock_task)

        # Should call inference with instruction-only prompt
        mock_inference.infer.assert_called_once()
        call_args = mock_inference.infer.call_args
        assert "no agent output was captured" in call_args.kwargs["input_text"]


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


class TestTrivialInputFilter:
    """Tests for _check_trivial_input() — slash commands and short confirmations."""

    def test_slash_command_returns_command(self):
        turn = MagicMock()
        turn.text = "/start-queue"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "/start-queue"

    def test_slash_command_with_args_returns_command_only(self):
        turn = MagicMock()
        turn.text = "/opsx:apply some args"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "/opsx:apply"

    def test_slash_command_with_equals(self):
        turn = MagicMock()
        turn.text = "/orch:10-queue-add"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "/orch:10-queue-add"

    def test_yes_returns_confirmed(self):
        turn = MagicMock()
        turn.text = "yes"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "Confirmed"

    def test_ok_returns_confirmed(self):
        turn = MagicMock()
        turn.text = "ok"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "Confirmed"

    def test_go_ahead_returns_confirmed(self):
        turn = MagicMock()
        turn.text = "go ahead"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "Confirmed"

    def test_confirmation_case_insensitive(self):
        turn = MagicMock()
        turn.text = "YES"

        result = SummarisationService._check_trivial_input(turn)

        assert result == "Confirmed"

    def test_confirmation_with_trailing_punctuation(self):
        turn = MagicMock()
        turn.text = "yes."

        result = SummarisationService._check_trivial_input(turn)

        assert result == "Confirmed"

    def test_long_text_returns_none(self):
        turn = MagicMock()
        turn.text = "Please refactor the authentication middleware to use JWT tokens instead of sessions"

        result = SummarisationService._check_trivial_input(turn)

        assert result is None

    def test_normal_command_returns_none(self):
        turn = MagicMock()
        turn.text = "Fix the login page"

        result = SummarisationService._check_trivial_input(turn)

        assert result is None

    def test_empty_text_returns_none(self):
        turn = MagicMock()
        turn.text = ""

        result = SummarisationService._check_trivial_input(turn)

        assert result is None

    def test_none_text_returns_none(self):
        turn = MagicMock()
        turn.text = None

        result = SummarisationService._check_trivial_input(turn)

        assert result is None


class TestTrivialInputBypassIntegration:
    """Tests that trivial inputs bypass LLM in summarise_turn()."""

    def test_slash_command_bypasses_llm(self, service, mock_inference):
        turn = MagicMock()
        turn.id = 1
        turn.text = "/start-queue"
        turn.summary = None

        result = service.summarise_turn(turn)

        assert result == "/start-queue"
        assert turn.summary == "/start-queue"
        assert turn.summary_generated_at is not None
        mock_inference.infer.assert_not_called()

    def test_confirmation_bypasses_llm(self, service, mock_inference):
        turn = MagicMock()
        turn.id = 1
        turn.text = "yes"
        turn.summary = None

        result = service.summarise_turn(turn)

        assert result == "Confirmed"
        assert turn.summary == "Confirmed"
        mock_inference.infer.assert_not_called()

    def test_trivial_persisted_with_db_session(self, service, mock_inference):
        turn = MagicMock()
        turn.id = 1
        turn.text = "ok"
        turn.summary = None
        mock_session = MagicMock()

        result = service.summarise_turn(turn, db_session=mock_session)

        assert result == "Confirmed"
        mock_session.add.assert_called_once_with(turn)
        mock_session.commit.assert_called_once()
        mock_inference.infer.assert_not_called()


class TestSlashCommandInstructionBypass:
    """Tests that slash commands bypass LLM in summarise_instruction()."""

    def test_slash_command_sets_instruction_directly(self, service, mock_inference, mock_task):
        mock_task.instruction = None

        result = service.summarise_instruction(mock_task, "/start-queue")

        assert result == "/start-queue"
        assert mock_task.instruction == "/start-queue"
        assert mock_task.instruction_generated_at is not None
        mock_inference.infer.assert_not_called()

    def test_slash_command_with_args(self, service, mock_inference, mock_task):
        mock_task.instruction = None

        result = service.summarise_instruction(mock_task, "/opsx:apply task1 task2")

        assert result == "/opsx:apply"
        assert mock_task.instruction == "/opsx:apply"
        mock_inference.infer.assert_not_called()

    def test_slash_command_persisted_with_db_session(self, service, mock_inference, mock_task):
        mock_task.instruction = None
        mock_session = MagicMock()

        result = service.summarise_instruction(mock_task, "/commit-push", db_session=mock_session)

        assert result == "/commit-push"
        mock_session.add.assert_called_once_with(mock_task)
        mock_session.commit.assert_called_once()

    def test_normal_command_still_uses_llm(self, service, mock_inference, mock_task):
        mock_task.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Fix login page styling",
            input_tokens=40, output_tokens=10,
            model="model", latency_ms=150,
        )

        service.summarise_instruction(mock_task, "Fix the login page CSS")

        mock_inference.infer.assert_called_once()
