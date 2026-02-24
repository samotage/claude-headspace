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
    turn.is_internal = False
    turn.command_id = 10
    turn.command.agent_id = 5
    turn.command.agent.project_id = 3
    return turn


@pytest.fixture
def mock_command():
    cmd = MagicMock()
    cmd.id = 10
    cmd.started_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
    cmd.completed_at = datetime(2026, 1, 31, 10, 30, 0, tzinfo=timezone.utc)
    cmd.completion_summary = None
    cmd.completion_summary_generated_at = None
    cmd.instruction = "Refactor the authentication middleware and ensure tests pass"
    cmd.instruction_generated_at = None
    cmd.agent_id = 5
    cmd.agent.project_id = 3

    # Create mock turns
    mock_turn_1 = MagicMock()
    mock_turn_1.text = "Started refactoring auth"
    mock_turn_2 = MagicMock()
    mock_turn_2.text = "All 12 tests passing"
    cmd.turns = [mock_turn_1, mock_turn_2]

    return cmd


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
        assert call_kwargs["command_id"] == 10
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


class TestCommandSummarisation:

    def test_successful_command_summarisation(self, service, mock_inference, mock_command):
        mock_inference.infer.return_value = InferenceResult(
            text="Completed auth refactoring with 12 tests passing.",
            input_tokens=80,
            output_tokens=15,
            model="anthropic/claude-3-haiku",
            latency_ms=300,
        )

        result = service.summarise_command(mock_command)

        assert result == "Completed auth refactoring with 12 tests passing."
        assert mock_command.completion_summary == "Completed auth refactoring with 12 tests passing."
        assert mock_command.completion_summary_generated_at is not None
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["level"] == "command"
        assert call_kwargs["purpose"] == "summarise_command"
        assert call_kwargs["command_id"] == 10
        assert call_kwargs["agent_id"] == 5
        assert call_kwargs["project_id"] == 3

    def test_existing_command_summary_returned(self, service, mock_inference, mock_command):
        mock_command.completion_summary = "Already summarised"

        result = service.summarise_command(mock_command)

        assert result == "Already summarised"
        mock_inference.infer.assert_not_called()

    def test_inference_unavailable_for_command(self, mock_inference, mock_command):
        mock_inference.is_available = False
        service = SummarisationService(inference_service=mock_inference)

        result = service.summarise_command(mock_command)

        assert result is None

    def test_command_inference_error_returns_none(self, service, mock_inference, mock_command):
        mock_inference.infer.side_effect = Exception("API failure")

        result = service.summarise_command(mock_command)

        assert result is None
        assert mock_command.completion_summary is None

    def test_command_prompt_includes_context(self, service, mock_command):
        prompt = service._resolve_command_prompt(mock_command)

        assert "18 tokens" in prompt
        assert "All 12 tests passing" in prompt
        assert "Refactor the authentication middleware" in prompt
        assert "Command:" in prompt

    def test_command_summary_persisted_with_db_session(self, service, mock_inference, mock_command):
        mock_inference.infer.return_value = InferenceResult(
            text="Task summary",
            input_tokens=80,
            output_tokens=15,
            model="model",
            latency_ms=300,
        )
        mock_session = MagicMock()

        result = service.summarise_command(mock_command, db_session=mock_session)

        assert result == "Task summary"
        mock_session.add.assert_called_once_with(mock_command)
        mock_session.commit.assert_called_once()


class TestInstructionSummarisation:
    """Tests for summarise_instruction() — prompt building, persistence, empty text guard."""

    def test_successful_instruction_summarisation(self, service, mock_inference, mock_command):
        mock_command.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Refactor authentication middleware and verify tests.",
            input_tokens=40,
            output_tokens=10,
            model="anthropic/claude-3-haiku",
            latency_ms=150,
        )

        result = service.summarise_instruction(mock_command, "Please refactor the auth middleware and make sure all tests pass")

        assert result == "Refactor authentication middleware and verify tests."
        assert mock_command.instruction == "Refactor authentication middleware and verify tests."
        assert mock_command.instruction_generated_at is not None
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["level"] == "turn"
        assert call_kwargs["purpose"] == "summarise_instruction"
        assert call_kwargs["command_id"] == 10

    def test_existing_instruction_returned(self, service, mock_inference, mock_command):
        mock_command.instruction = "Already set instruction"

        result = service.summarise_instruction(mock_command, "Some command text")

        assert result == "Already set instruction"
        mock_inference.infer.assert_not_called()

    def test_empty_command_text_returns_none(self, service, mock_inference, mock_command):
        mock_command.instruction = None

        result = service.summarise_instruction(mock_command, "")

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_whitespace_only_command_text_returns_none(self, service, mock_inference, mock_command):
        mock_command.instruction = None

        result = service.summarise_instruction(mock_command, "   \n  ")

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_none_command_text_returns_none(self, service, mock_inference, mock_command):
        mock_command.instruction = None

        result = service.summarise_instruction(mock_command, None)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_inference_unavailable_returns_none(self, mock_inference, mock_command):
        mock_inference.is_available = False
        mock_command.instruction = None
        service = SummarisationService(inference_service=mock_inference)

        result = service.summarise_instruction(mock_command, "Some command")

        assert result is None

    def test_inference_error_returns_none(self, service, mock_inference, mock_command):
        mock_command.instruction = None
        mock_inference.infer.side_effect = Exception("API failure")

        result = service.summarise_instruction(mock_command, "Some command")

        assert result is None
        assert mock_command.instruction is None

    def test_instruction_persisted_with_db_session(self, service, mock_inference, mock_command):
        mock_command.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Instruction summary",
            input_tokens=40,
            output_tokens=10,
            model="model",
            latency_ms=150,
        )
        mock_session = MagicMock()

        result = service.summarise_instruction(mock_command, "Some command", db_session=mock_session)

        assert result == "Instruction summary"
        mock_session.add.assert_called_once_with(mock_command)
        mock_session.commit.assert_called_once()

    def test_instruction_prompt_includes_command_text(self, service, mock_inference, mock_command):
        mock_command.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Summary",
            input_tokens=40,
            output_tokens=10,
            model="model",
            latency_ms=150,
        )

        service.summarise_instruction(mock_command, "Fix the login page CSS styling")

        call_kwargs = mock_inference.infer.call_args[1]
        assert "Fix the login page CSS styling" in call_kwargs["input_text"]
        assert "stating the goal" in call_kwargs["input_text"]


class TestExecutePending:
    """Tests for execute_pending() — synchronous post-commit summarisation."""

    def test_execute_pending_turn(self, service, mock_inference):
        """execute_pending should call summarise_turn for turn requests."""
        from src.claude_headspace.services.command_lifecycle import SummarisationRequest

        mock_turn = MagicMock()
        mock_turn.id = 1
        mock_turn.text = "Working on fix"
        mock_turn.summary = None
        mock_turn.is_internal = False
        mock_turn.command.agent_id = 5
        mock_turn.command.agent.project_id = 3

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
        from src.claude_headspace.services.command_lifecycle import SummarisationRequest

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.instruction = None
        mock_command.agent_id = 5
        mock_command.agent.project_id = 3

        mock_inference.infer.return_value = InferenceResult(
            text="Instruction summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        mock_session = MagicMock()
        requests = [SummarisationRequest(type="instruction", command=mock_command, command_text="Fix the bug")]

        with patch.object(service, "_broadcast_summary_update") as mock_broadcast:
            service.execute_pending(requests, mock_session)

            assert mock_command.instruction == "Instruction summary"
            mock_broadcast.assert_called_once()
            call_kwargs = mock_broadcast.call_args[1]
            assert call_kwargs["event_type"] == "instruction_summary"
            assert call_kwargs["entity_id"] == 10

    def test_execute_pending_command_completion(self, service, mock_inference):
        """execute_pending should call summarise_command for command_completion requests."""
        from src.claude_headspace.services.command_lifecycle import SummarisationRequest

        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.completion_summary = None
        mock_command.instruction = "Fix the bug"
        mock_command.agent_id = 5
        mock_command.agent.project_id = 3
        mock_turn = MagicMock()
        mock_turn.text = "All done"
        mock_command.turns = [mock_turn]

        mock_inference.infer.return_value = InferenceResult(
            text="Task completion summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        mock_session = MagicMock()
        requests = [SummarisationRequest(type="command_completion", command=mock_command)]

        with patch.object(service, "_broadcast_summary_update") as mock_broadcast:
            service.execute_pending(requests, mock_session)

            assert mock_command.completion_summary == "Task completion summary"
            mock_broadcast.assert_called_once()
            call_kwargs = mock_broadcast.call_args[1]
            assert call_kwargs["event_type"] == "command_summary"
            assert call_kwargs["extra"] == {"is_completion": True}

    def test_execute_pending_error_non_fatal(self, service, mock_inference):
        """execute_pending should continue processing after an error."""
        from src.claude_headspace.services.command_lifecycle import SummarisationRequest

        mock_turn_1 = MagicMock()
        mock_turn_1.id = 1
        mock_turn_1.text = "First"
        mock_turn_1.summary = None
        mock_turn_1.is_internal = False
        mock_turn_1.command.agent_id = 5
        mock_turn_1.command.agent.project_id = 3

        mock_turn_2 = MagicMock()
        mock_turn_2.id = 2
        mock_turn_2.text = "Second"
        mock_turn_2.summary = None
        mock_turn_2.is_internal = False
        mock_turn_2.command.agent_id = 5
        mock_turn_2.command.agent.project_id = 3

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


class TestResolveCommandPrompt:
    """Tests for _resolve_command_prompt() — correct inputs, no timestamps/turn counts."""

    def test_command_prompt_uses_instruction_and_final_turn(self, service, mock_command):
        prompt = service._resolve_command_prompt(mock_command)

        assert "Refactor the authentication middleware" in prompt
        assert "All 12 tests passing" in prompt

    def test_command_prompt_does_not_include_timestamps(self, service, mock_command):
        prompt = service._resolve_command_prompt(mock_command)

        assert "2026" not in prompt
        assert "started_at" not in prompt
        assert "completed_at" not in prompt

    def test_command_prompt_does_not_include_turn_counts(self, service, mock_command):
        prompt = service._resolve_command_prompt(mock_command)

        assert "Turns:" not in prompt
        assert "turns:" not in prompt

    def test_command_prompt_with_no_instruction(self, service, mock_command):
        mock_command.instruction = None

        prompt = service._resolve_command_prompt(mock_command)

        assert "No instruction recorded" in prompt

    def test_command_prompt_with_no_turns_uses_instruction_fallback(self, service, mock_command):
        mock_command.turns = []

        prompt = service._resolve_command_prompt(mock_command)

        assert prompt is not None
        assert "Refactor the authentication middleware" in prompt
        assert "no agent output was captured" in prompt


class TestResolveTurnPrompt:
    """Tests for _resolve_turn_prompt() — intent-aware templates, command instruction context, empty text guard."""

    def test_command_intent_uses_command_template(self, service):
        turn = MagicMock()
        turn.text = "Fix the login page"
        turn.actor.value = "user"
        turn.intent.value = "command"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "command" in prompt.lower()
        assert "Fix the login page" in prompt

    def test_question_intent_uses_question_template(self, service):
        turn = MagicMock()
        turn.text = "Which database should I use?"
        turn.actor.value = "agent"
        turn.intent.value = "question"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "what the agent needs to know" in prompt
        assert "Which database should I use?" in prompt

    def test_completion_intent_uses_completion_template(self, service):
        turn = MagicMock()
        turn.text = "All tests are now passing"
        turn.actor.value = "agent"
        turn.intent.value = "completion"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "what was accomplished" in prompt
        assert "All tests are now passing" in prompt

    def test_progress_intent_uses_progress_template(self, service):
        turn = MagicMock()
        turn.text = "Refactoring the auth middleware"
        turn.actor.value = "agent"
        turn.intent.value = "progress"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "progress" in prompt
        assert "Refactoring the auth middleware" in prompt

    def test_answer_intent_uses_answer_template(self, service):
        turn = MagicMock()
        turn.text = "Use PostgreSQL for the database"
        turn.actor.value = "user"
        turn.intent.value = "answer"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "what was confirmed or provided" in prompt
        assert "Use PostgreSQL" in prompt

    def test_end_of_command_intent_uses_end_template(self, service):
        turn = MagicMock()
        turn.text = "Task complete, all requirements met"
        turn.actor.value = "agent"
        turn.intent.value = "end_of_command"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "final outcome" in prompt
        assert "Task complete" in prompt

    def test_unknown_intent_uses_default_template(self, service):
        turn = MagicMock()
        turn.text = "Some text"
        turn.actor.value = "agent"
        turn.intent.value = "unknown_intent"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "18 tokens" in prompt
        assert "Some text" in prompt
        assert "agent" in prompt

    def test_turn_prompt_includes_command_instruction_context(self, service):
        turn = MagicMock()
        turn.text = "Working on auth refactoring"
        turn.actor.value = "agent"
        turn.intent.value = "progress"
        turn.command.instruction = "Refactor the authentication module"

        prompt = service._resolve_turn_prompt(turn)

        assert "Command instruction: Refactor the authentication module" in prompt

    def test_turn_prompt_without_command_instruction(self, service):
        turn = MagicMock()
        turn.text = "Some work"
        turn.actor.value = "agent"
        turn.intent.value = "progress"
        turn.command.instruction = None

        prompt = service._resolve_turn_prompt(turn)

        assert "Command instruction:" not in prompt


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


class TestCommandEmptyFinalTurnFallback:
    """Tests for fallback when final turn text is empty — uses turn activity or instruction-only."""

    def test_empty_final_turn_falls_back_to_activity(self, service, mock_inference, mock_command):
        """When final turn text is empty but earlier turns have text, use activity fallback."""
        mock_command.completion_summary = None
        mock_command.turns[-1].text = ""
        mock_inference.infer.return_value = InferenceResult(
            text="Task completed successfully.", input_tokens=50,
            output_tokens=10, model="model", latency_ms=200,
        )

        result = service.summarise_command(mock_command)

        assert result == "Task completed successfully."
        mock_inference.infer.assert_called_once()
        call_kwargs = mock_inference.infer.call_args[1]
        assert call_kwargs["purpose"] == "summarise_command"

    def test_none_final_turn_falls_back_to_activity(self, service, mock_inference, mock_command):
        """When final turn text is None but earlier turns have text, use activity fallback."""
        mock_command.completion_summary = None
        mock_command.turns[-1].text = None
        mock_inference.infer.return_value = InferenceResult(
            text="Task completed successfully.", input_tokens=50,
            output_tokens=10, model="model", latency_ms=200,
        )

        result = service.summarise_command(mock_command)

        assert result == "Task completed successfully."
        mock_inference.infer.assert_called_once()

    def test_whitespace_final_turn_falls_back_to_activity(self, service, mock_inference, mock_command):
        """When final turn text is whitespace-only, use activity fallback."""
        mock_command.completion_summary = None
        mock_command.turns[-1].text = "   "
        mock_inference.infer.return_value = InferenceResult(
            text="Task completed successfully.", input_tokens=50,
            output_tokens=10, model="model", latency_ms=200,
        )

        result = service.summarise_command(mock_command)

        assert result == "Task completed successfully."
        mock_inference.infer.assert_called_once()

    def test_all_turns_empty_uses_instruction_fallback(self, service, mock_inference, mock_command):
        """When all turns have empty text, falls back to instruction-only prompt."""
        mock_command.completion_summary = None
        for t in mock_command.turns:
            t.text = ""
            t.summary = None

        result = service.summarise_command(mock_command)

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

    def test_slash_command_sets_instruction_directly(self, service, mock_inference, mock_command):
        mock_command.instruction = None

        result = service.summarise_instruction(mock_command, "/start-queue")

        assert result == "/start-queue"
        assert mock_command.instruction == "/start-queue"
        assert mock_command.instruction_generated_at is not None
        mock_inference.infer.assert_not_called()

    def test_slash_command_with_args(self, service, mock_inference, mock_command):
        mock_command.instruction = None

        result = service.summarise_instruction(mock_command, "/opsx:apply task1 task2")

        assert result == "/opsx:apply"
        assert mock_command.instruction == "/opsx:apply"
        mock_inference.infer.assert_not_called()

    def test_slash_command_persisted_with_db_session(self, service, mock_inference, mock_command):
        mock_command.instruction = None
        mock_session = MagicMock()

        result = service.summarise_instruction(mock_command, "/commit-push", db_session=mock_session)

        assert result == "/commit-push"
        mock_session.add.assert_called_once_with(mock_command)
        mock_session.commit.assert_called_once()

    def test_normal_command_still_uses_llm(self, service, mock_inference, mock_command):
        mock_command.instruction = None
        mock_inference.infer.return_value = InferenceResult(
            text="Fix login page styling",
            input_tokens=40, output_tokens=10,
            model="model", latency_ms=150,
        )

        service.summarise_instruction(mock_command, "Fix the login page CSS")

        mock_inference.infer.assert_called_once()


class TestResolveCommandPromptResilience:
    """Tests for _resolve_command_prompt resilience against DetachedInstanceError."""

    def test_detached_command_turns_graceful_fallback(self, service):
        """Accessing command.turns raising an exception should fall back to empty turns."""
        mock_command = MagicMock()
        mock_command.id = 99
        mock_command.instruction = "Fix the auth module"

        # Simulate DetachedInstanceError when accessing .turns
        type(mock_command).turns = property(
            lambda self: (_ for _ in ()).throw(Exception("DetachedInstanceError"))
        )

        # Should not raise — falls back to empty turns
        result = SummarisationService._resolve_command_prompt(mock_command)

        # With instruction but no turns, should return instruction-only prompt
        assert result is not None
        assert "Fix the auth module" in result


class TestInternalTurnSkip:
    """Tests for is_internal=True turn skipping — prevents inference waste on system plumbing turns."""

    def test_summarise_turn_skips_internal(self, service, mock_inference):
        """summarise_turn() should return None for is_internal=True turns."""
        turn = MagicMock()
        turn.id = 1
        turn.text = "You are Con. Read the following skill and experience..."
        turn.summary = None
        turn.is_internal = True

        result = service.summarise_turn(turn)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_summarise_turn_processes_non_internal(self, service, mock_inference, mock_turn):
        """summarise_turn() should process turns with is_internal=False."""
        mock_turn.is_internal = False
        mock_inference.infer.return_value = InferenceResult(
            text="Summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        result = service.summarise_turn(mock_turn)

        assert result == "Summary"
        mock_inference.infer.assert_called_once()

    def test_summarise_turn_processes_missing_is_internal(self, service, mock_inference, mock_turn):
        """summarise_turn() should process turns without is_internal attribute."""
        # MagicMock will return a truthy MagicMock for any attribute by default,
        # so we need to explicitly delete it to test getattr fallback
        del mock_turn.is_internal
        mock_inference.infer.return_value = InferenceResult(
            text="Summary", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        result = service.summarise_turn(mock_turn)

        assert result == "Summary"

    def test_summarise_command_skips_all_internal_user_turns(self, service, mock_inference):
        """summarise_command() should skip when all user turns are internal."""
        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.completion_summary = None
        mock_command.instruction = "Internal instruction"
        mock_command.agent_id = 5
        mock_command.agent.project_id = 3

        # Create mock turns — all user turns are internal
        user_turn = MagicMock()
        user_turn.actor.value = "user"
        user_turn.is_internal = True
        user_turn.text = "persona priming text"
        agent_turn = MagicMock()
        agent_turn.actor.value = "agent"
        agent_turn.is_internal = False
        agent_turn.text = "Hello, I'm Con"
        mock_command.turns = [user_turn, agent_turn]

        result = service.summarise_command(mock_command)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_summarise_command_processes_mixed_turns(self, service, mock_inference):
        """summarise_command() should process when at least one user turn is NOT internal."""
        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.completion_summary = None
        mock_command.instruction = "Fix the bug"
        mock_command.agent_id = 5
        mock_command.agent.project_id = 3

        internal_turn = MagicMock()
        internal_turn.actor.value = "user"
        internal_turn.is_internal = True
        real_turn = MagicMock()
        real_turn.actor.value = "user"
        real_turn.is_internal = False
        agent_turn = MagicMock()
        agent_turn.actor.value = "agent"
        agent_turn.text = "Done fixing"
        mock_command.turns = [internal_turn, real_turn, agent_turn]

        mock_inference.infer.return_value = InferenceResult(
            text="Fixed the bug", input_tokens=50, output_tokens=10,
            model="model", latency_ms=200,
        )

        result = service.summarise_command(mock_command)

        assert result == "Fixed the bug"
        mock_inference.infer.assert_called_once()

    def test_summarise_instruction_skips_all_internal_user_turns(self, service, mock_inference):
        """summarise_instruction() should skip when all user turns are internal."""
        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.instruction = None

        user_turn = MagicMock()
        user_turn.actor.value = "user"
        user_turn.is_internal = True
        mock_command.turns = [user_turn]

        result = service.summarise_instruction(mock_command, "persona priming text")

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_summarise_instruction_processes_non_internal(self, service, mock_inference):
        """summarise_instruction() should process when user turns are not internal."""
        mock_command = MagicMock()
        mock_command.id = 10
        mock_command.instruction = None
        mock_command.agent_id = 5
        mock_command.agent.project_id = 3

        user_turn = MagicMock()
        user_turn.actor.value = "user"
        user_turn.is_internal = False
        mock_command.turns = [user_turn]

        mock_inference.infer.return_value = InferenceResult(
            text="Fix the login bug", input_tokens=10, output_tokens=5,
            model="model", latency_ms=100,
        )

        result = service.summarise_instruction(mock_command, "Fix the login bug")

        assert result == "Fix the login bug"
        mock_inference.infer.assert_called_once()
