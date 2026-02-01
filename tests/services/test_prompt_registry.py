"""Unit tests for the centralised prompt registry."""

import pytest

from src.claude_headspace.services.prompt_registry import build_prompt, _PROMPT_TEMPLATES


class TestBuildPrompt:
    """Tests for build_prompt() — registry lookup and template rendering."""

    def test_unknown_type_raises_key_error(self):
        with pytest.raises(KeyError):
            build_prompt("nonexistent_prompt_type")

    def test_all_registered_types_exist(self):
        expected_types = [
            "turn_command",
            "turn_question",
            "turn_completion",
            "turn_progress",
            "turn_answer",
            "turn_end_of_task",
            "turn_default",
            "task_completion",
            "task_completion_from_activity",
            "instruction",
            "priority_scoring",
            "progress_summary",
            "completion_classification",
            "question_classification",
        ]
        for prompt_type in expected_types:
            assert prompt_type in _PROMPT_TEMPLATES, f"{prompt_type} missing from registry"


class TestTurnPrompts:
    """Tests for turn-level prompt templates."""

    def test_turn_command(self):
        result = build_prompt(
            "turn_command",
            instruction_context="Task instruction: Do X\n\n",
            text="Fix the login page",
        )
        assert "command" in result.lower()
        assert "Fix the login page" in result
        assert "Task instruction: Do X" in result

    def test_turn_question(self):
        result = build_prompt(
            "turn_question",
            instruction_context="",
            text="Which database?",
        )
        assert "what the agent is asking" in result
        assert "Which database?" in result

    def test_turn_completion(self):
        result = build_prompt(
            "turn_completion",
            instruction_context="",
            text="All tests pass",
        )
        assert "what the agent accomplished" in result
        assert "All tests pass" in result

    def test_turn_progress(self):
        result = build_prompt(
            "turn_progress",
            instruction_context="",
            text="Refactoring module",
        )
        assert "progress" in result
        assert "Refactoring module" in result

    def test_turn_answer(self):
        result = build_prompt(
            "turn_answer",
            instruction_context="",
            text="Use PostgreSQL",
        )
        assert "information the user provided" in result
        assert "Use PostgreSQL" in result

    def test_turn_end_of_task(self):
        result = build_prompt(
            "turn_end_of_task",
            instruction_context="",
            text="Task complete",
        )
        assert "final outcome" in result
        assert "Task complete" in result

    def test_turn_default(self):
        result = build_prompt(
            "turn_default",
            instruction_context="",
            text="Some text",
            actor="agent",
            intent="unknown",
        )
        assert "1-2 concise sentences" in result
        assert "Some text" in result
        assert "agent" in result
        assert "unknown" in result


class TestTaskPrompts:
    """Tests for task-level prompt templates."""

    def test_task_completion(self):
        result = build_prompt(
            "task_completion",
            instruction="Refactor auth middleware",
            final_turn_text="All 12 tests passing",
        )
        assert "2-3 sentences" in result
        assert "Refactor auth middleware" in result
        assert "All 12 tests passing" in result
        assert "Original instruction" in result

    def test_task_completion_from_activity(self):
        result = build_prompt(
            "task_completion_from_activity",
            instruction="Refactor auth middleware",
            turn_activity="- [AGENT/progress] Working on middleware\n- [AGENT/question] Which pattern?",
        )
        assert "2-3 sentences" in result
        assert "Refactor auth middleware" in result
        assert "Activity during this task" in result
        assert "Working on middleware" in result

    def test_instruction(self):
        result = build_prompt(
            "instruction",
            command_text="Fix the login page CSS",
        )
        assert "core task or goal" in result
        assert "Fix the login page CSS" in result


class TestScoringPrompt:
    """Tests for priority scoring prompt template."""

    def test_priority_scoring(self):
        result = build_prompt(
            "priority_scoring",
            context_section="Current Objective: Ship auth",
            agents_text="- Agent ID: 1\n  Project: test",
        )
        assert "prioritising agents" in result
        assert "Current Objective: Ship auth" in result
        assert "Agent ID: 1" in result
        assert "Scoring factors" in result
        assert "JSON array" in result


class TestProgressSummaryPrompt:
    """Tests for progress summary prompt template."""

    def test_progress_summary(self):
        result = build_prompt(
            "progress_summary",
            project_name="my-project",
            analysis_text="Date range: 2026-01-01 to 2026-01-31\nTotal commits: 42",
        )
        assert "my-project" in result
        assert "Date range: 2026-01-01 to 2026-01-31" in result
        assert "3-5 paragraph" in result


class TestClassificationPrompts:
    """Tests for classification prompt templates."""

    def test_completion_classification(self):
        result = build_prompt(
            "completion_classification",
            tail="Done. All tests passing.",
        )
        assert "Classify this agent output" in result
        assert "Done. All tests passing." in result
        assert "Respond with only the letter" in result

    def test_question_classification(self):
        result = build_prompt(
            "question_classification",
            content="Should I proceed with the refactoring?",
        )
        assert "classifying Claude Code agent output" in result
        assert "Should I proceed with the refactoring?" in result
        assert "yes" in result
        assert "no" in result


class TestMissingPlaceholders:
    """Verify that templates raise on missing placeholders rather than silently dropping them."""

    def test_turn_command_missing_text_raises(self):
        with pytest.raises(KeyError):
            build_prompt("turn_command", instruction_context="")

    def test_task_completion_missing_instruction_raises(self):
        with pytest.raises(KeyError):
            build_prompt("task_completion", final_turn_text="done")

    def test_priority_scoring_missing_agents_raises(self):
        with pytest.raises(KeyError):
            build_prompt("priority_scoring", context_section="obj")
