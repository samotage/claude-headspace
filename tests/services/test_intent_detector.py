"""Tests for intent detector service."""

import pytest

from claude_headspace.models.task import TaskState
from claude_headspace.models.turn import TurnActor, TurnIntent
from claude_headspace.services.intent_detector import (
    COMPLETION_PATTERNS,
    QUESTION_PATTERNS,
    IntentResult,
    detect_agent_intent,
    detect_intent,
    detect_user_intent,
)


class TestDetectAgentIntent:
    """Tests for detect_agent_intent function."""

    # Question detection tests
    def test_question_mark_at_end(self):
        """Question mark at end should detect as question."""
        result = detect_agent_intent("Would you like me to continue?")
        assert result.intent == TurnIntent.QUESTION
        assert result.confidence == 1.0

    def test_would_you_like_phrase(self):
        """'Would you like' phrase should detect as question."""
        result = detect_agent_intent("Would you like me to add error handling?")
        assert result.intent == TurnIntent.QUESTION

    def test_should_i_phrase(self):
        """'Should I' phrase should detect as question."""
        result = detect_agent_intent("Should I proceed with the refactoring?")
        assert result.intent == TurnIntent.QUESTION

    def test_do_you_want_phrase(self):
        """'Do you want' phrase should detect as question."""
        result = detect_agent_intent("Do you want me to run the tests now?")
        assert result.intent == TurnIntent.QUESTION

    def test_can_i_phrase(self):
        """'Can I' phrase should detect as question."""
        result = detect_agent_intent("Can I help you with anything else?")
        assert result.intent == TurnIntent.QUESTION

    def test_clarifying_question_is_that_correct(self):
        """'Is that correct' phrase should detect as question."""
        result = detect_agent_intent("I'll update the config file. Is that correct?")
        assert result.intent == TurnIntent.QUESTION

    def test_clarifying_question_does_that_work(self):
        """'Does that work' phrase should detect as question."""
        result = detect_agent_intent("I can use Redis for caching. Does that work?")
        assert result.intent == TurnIntent.QUESTION

    def test_question_mark_in_code_block_not_detected(self):
        """Question mark inside code should not trigger question detection."""
        # Question mark inside quotes (simulating code)
        result = detect_agent_intent('The regex pattern is "foo?"')
        assert result.intent == TurnIntent.PROGRESS

    # Completion detection tests
    def test_done_standalone(self):
        """'Done' by itself should detect as completion."""
        result = detect_agent_intent("Done.")
        assert result.intent == TurnIntent.COMPLETION
        assert result.confidence == 1.0

    def test_complete_standalone(self):
        """'Complete' by itself should detect as completion."""
        result = detect_agent_intent("Complete!")
        assert result.intent == TurnIntent.COMPLETION

    def test_finished_standalone(self):
        """'Finished' by itself should detect as completion."""
        result = detect_agent_intent("Finished")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_done(self):
        """'All done' should detect as completion."""
        result = detect_agent_intent("All done!")
        assert result.intent == TurnIntent.COMPLETION

    def test_ive_finished(self):
        """'I've finished' should detect as completion."""
        result = detect_agent_intent("I've finished implementing the feature.")
        assert result.intent == TurnIntent.COMPLETION

    def test_task_complete(self):
        """'Task complete' should detect as completion."""
        result = detect_agent_intent("Task complete. The tests are now passing.")
        assert result.intent == TurnIntent.COMPLETION

    def test_successfully_completed(self):
        """'Successfully completed' should detect as completion."""
        result = detect_agent_intent("Successfully completed the migration.")
        assert result.intent == TurnIntent.COMPLETION

    def test_changes_have_been_applied(self):
        """'Changes have been applied' should detect as completion."""
        result = detect_agent_intent("All changes have been applied.")
        assert result.intent == TurnIntent.COMPLETION

    def test_implementation_complete(self):
        """'Implementation complete' should detect as completion."""
        result = detect_agent_intent("Implementation is complete.")
        assert result.intent == TurnIntent.COMPLETION

    # Progress detection tests (default fallback)
    def test_progress_default(self):
        """Non-question, non-completion text should default to progress."""
        result = detect_agent_intent("I'm now updating the configuration file.")
        assert result.intent == TurnIntent.PROGRESS
        assert result.confidence == 1.0

    def test_progress_with_code_output(self):
        """Code output should default to progress."""
        result = detect_agent_intent("Here's the updated function:\n\ndef foo():\n    return 42")
        assert result.intent == TurnIntent.PROGRESS

    def test_progress_with_explanation(self):
        """Technical explanation should default to progress."""
        result = detect_agent_intent(
            "The error occurs because the database connection times out after 30 seconds."
        )
        assert result.intent == TurnIntent.PROGRESS

    # Edge cases
    def test_empty_text(self):
        """Empty text should default to progress with lower confidence."""
        result = detect_agent_intent("")
        assert result.intent == TurnIntent.PROGRESS
        assert result.confidence == 0.5

    def test_none_text(self):
        """None text should default to progress with lower confidence."""
        result = detect_agent_intent(None)
        assert result.intent == TurnIntent.PROGRESS
        assert result.confidence == 0.5

    def test_whitespace_only(self):
        """Whitespace-only text should default to progress with lower confidence."""
        result = detect_agent_intent("   \n\t  ")
        assert result.intent == TurnIntent.PROGRESS
        assert result.confidence == 0.5

    def test_question_priority_over_completion(self):
        """When both patterns match, question should take priority."""
        # Text has both "done" and ends with "?"
        result = detect_agent_intent("I'm done. Should I continue?")
        assert result.intent == TurnIntent.QUESTION


class TestDetectUserIntent:
    """Tests for detect_user_intent function."""

    def test_user_command_from_idle(self):
        """User turn from IDLE state should be COMMAND."""
        result = detect_user_intent("Please fix the bug in the login page.", TaskState.IDLE)
        assert result.intent == TurnIntent.COMMAND
        assert result.confidence == 1.0

    def test_user_answer_from_awaiting_input(self):
        """User turn from AWAITING_INPUT state should be ANSWER."""
        result = detect_user_intent("Yes, please proceed with that approach.", TaskState.AWAITING_INPUT)
        assert result.intent == TurnIntent.ANSWER
        assert result.confidence == 1.0

    def test_user_command_from_processing(self):
        """User turn from PROCESSING state should be COMMAND (interruption)."""
        result = detect_user_intent("Stop that, do this instead.", TaskState.PROCESSING)
        assert result.intent == TurnIntent.COMMAND

    def test_user_command_from_commanded(self):
        """User turn from COMMANDED state should be COMMAND."""
        result = detect_user_intent("Also add logging.", TaskState.COMMANDED)
        assert result.intent == TurnIntent.COMMAND

    def test_user_with_none_text(self):
        """User turn with None text should still detect intent based on state."""
        result = detect_user_intent(None, TaskState.AWAITING_INPUT)
        assert result.intent == TurnIntent.ANSWER


class TestDetectIntent:
    """Tests for the unified detect_intent function."""

    def test_user_actor_routes_to_user_detector(self):
        """USER actor should use user intent detection."""
        result = detect_intent("Do something", TurnActor.USER, TaskState.IDLE)
        assert result.intent == TurnIntent.COMMAND

    def test_agent_actor_routes_to_agent_detector(self):
        """AGENT actor should use agent intent detection."""
        result = detect_intent("Should I continue?", TurnActor.AGENT, TaskState.PROCESSING)
        assert result.intent == TurnIntent.QUESTION

    def test_agent_completion_detection(self):
        """Agent completion should be detected regardless of state."""
        result = detect_intent("Done.", TurnActor.AGENT, TaskState.PROCESSING)
        assert result.intent == TurnIntent.COMPLETION


class TestIntentResultDataclass:
    """Tests for IntentResult dataclass."""

    def test_intent_result_creation(self):
        """IntentResult should store all fields correctly."""
        result = IntentResult(
            intent=TurnIntent.QUESTION,
            confidence=0.9,
            matched_pattern=r"\?$",
        )
        assert result.intent == TurnIntent.QUESTION
        assert result.confidence == 0.9
        assert result.matched_pattern == r"\?$"

    def test_intent_result_optional_pattern(self):
        """IntentResult should allow None for matched_pattern."""
        result = IntentResult(intent=TurnIntent.PROGRESS, confidence=1.0)
        assert result.matched_pattern is None


class TestPatternAccuracy:
    """Tests for overall pattern accuracy (>90% target)."""

    # These test cases represent realistic agent outputs
    QUESTION_TEST_CASES = [
        ("Would you like me to add tests?", True),
        ("Should I refactor this code?", True),
        ("Do you want me to continue?", True),
        ("Can I proceed with the changes?", True),
        ("What do you think?", True),
        ("Is that correct?", True),
        ("Does that look good?", True),
        ("Shall I run the tests now?", True),
        ("May I delete the old file?", True),
        ("Let me know if you have questions?", True),
        # False positives we want to avoid
        ("The query uses SELECT * WHERE id=?", False),  # Code
        ('pattern = r"foo?"', False),  # Regex in code
    ]

    COMPLETION_TEST_CASES = [
        ("Done.", True),
        ("Complete!", True),
        ("Finished", True),
        ("All done!", True),
        ("I've finished the implementation.", True),
        ("Task complete.", True),
        ("Successfully completed.", True),
        ("Changes have been applied.", True),
        ("Implementation is complete.", True),
        ("Feature is ready.", True),
        # False positives we want to avoid
        ("The task is not done yet.", False),  # Negative
        ("I'm working on completing it.", False),  # In progress
    ]

    def test_question_pattern_accuracy(self):
        """Question detection should have >90% accuracy."""
        correct = 0
        total = len(self.QUESTION_TEST_CASES)

        for text, expected_question in self.QUESTION_TEST_CASES:
            result = detect_agent_intent(text)
            is_question = result.intent == TurnIntent.QUESTION
            if is_question == expected_question:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.9, f"Question accuracy {accuracy:.1%} < 90%"

    def test_completion_pattern_accuracy(self):
        """Completion detection should have >90% accuracy."""
        correct = 0
        total = len(self.COMPLETION_TEST_CASES)

        for text, expected_completion in self.COMPLETION_TEST_CASES:
            result = detect_agent_intent(text)
            is_completion = result.intent == TurnIntent.COMPLETION
            if is_completion == expected_completion:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.9, f"Completion accuracy {accuracy:.1%} < 90%"
