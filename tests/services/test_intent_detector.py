"""Tests for intent detector service."""

import pytest

from claude_headspace.models.command import CommandState
from claude_headspace.models.turn import TurnActor, TurnIntent
from unittest.mock import MagicMock

from claude_headspace.services.intent_detector import (
    BARE_AFFIRMATIVES,
    BLOCKED_PATTERNS,
    COMPLETION_OPENER_PATTERNS,
    COMPLETION_PATTERNS,
    CONTINUATION_PATTERNS,
    END_OF_COMMAND_HANDOFF_PATTERNS,
    END_OF_COMMAND_SOFT_CLOSE_PATTERNS,
    END_OF_COMMAND_SUMMARY_PATTERNS,
    HANDOFF_NEGATIVE_PATTERNS,
    HANDOFF_PATTERNS,
    PLAN_APPROVAL_PATTERN,
    QUESTION_PATTERNS,
    IntentResult,
    _detect_completion_opener,
    _detect_end_of_command,
    _detect_trailing_question,
    _extract_tail,
    _infer_completion_classification,
    _is_confirmation,
    _match_patterns,
    _strip_code_blocks,
    detect_agent_intent,
    detect_handoff_intent,
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
        assert result.confidence >= 0.95

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

    def test_command_complete(self):
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
        """Non-question, non-completion text should default to progress with lower confidence."""
        result = detect_agent_intent("I'm now updating the configuration file.")
        assert result.intent == TurnIntent.PROGRESS
        assert result.confidence == 0.5  # Lower confidence for fallback (no pattern match)

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
        result = detect_user_intent("Please fix the bug in the login page.", CommandState.IDLE)
        assert result.intent == TurnIntent.COMMAND
        assert result.confidence == 1.0

    def test_user_answer_from_awaiting_input(self):
        """User turn from AWAITING_INPUT state should be ANSWER."""
        result = detect_user_intent("Yes, please proceed with that approach.", CommandState.AWAITING_INPUT)
        assert result.intent == TurnIntent.ANSWER
        assert result.confidence == 1.0

    def test_user_command_from_processing(self):
        """Substantive user turn from PROCESSING state should be COMMAND (interruption)."""
        result = detect_user_intent("Stop that, do this instead.", CommandState.PROCESSING)
        assert result.intent == TurnIntent.COMMAND

    def test_user_confirmation_from_processing(self):
        """Confirmation during PROCESSING should be ANSWER (not a new command)."""
        result = detect_user_intent("Yes", CommandState.PROCESSING)
        assert result.intent == TurnIntent.ANSWER
        assert result.confidence == 0.9

    def test_user_command_from_commanded(self):
        """User turn from COMMANDED state should be COMMAND."""
        result = detect_user_intent("Also add logging.", CommandState.COMMANDED)
        assert result.intent == TurnIntent.COMMAND

    def test_user_with_none_text(self):
        """User turn with None text should still detect intent based on state."""
        result = detect_user_intent(None, CommandState.AWAITING_INPUT)
        assert result.intent == TurnIntent.ANSWER


class TestDetectIntent:
    """Tests for the unified detect_intent function."""

    def test_user_actor_routes_to_user_detector(self):
        """USER actor should use user intent detection."""
        result = detect_intent("Do something", TurnActor.USER, CommandState.IDLE)
        assert result.intent == TurnIntent.COMMAND

    def test_agent_actor_routes_to_agent_detector(self):
        """AGENT actor should use agent intent detection."""
        result = detect_intent("Should I continue?", TurnActor.AGENT, CommandState.PROCESSING)
        assert result.intent == TurnIntent.QUESTION

    def test_agent_completion_detection(self):
        """Agent completion should be detected regardless of state."""
        result = detect_intent("Done.", TurnActor.AGENT, CommandState.PROCESSING)
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
        # New expanded patterns
        ("How would you like me to handle this?", True),
        ("Which approach would you prefer?", True),
        ("Before I proceed, should I back up?", True),
        ("I need your confirmation on this.", True),
        ("I don't have permission to access that.", True),  # Blocked → QUESTION
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
        # New expanded patterns
        ("All tests are passing.", True),
        ("The PR is ready for review.", True),
        ("Here's a summary of what was done:\n- Fixed bug", True),
        # Completion opener cases
        ("Done. All files now consistently use anthropic/claude-3-haiku.", True),
        ("Complete. The feature is ready for review.", True),
        ("Finished. Here's what changed in the codebase.", True),
        ("All done! The tests pass and coverage is at 95%.", True),
        # Artifact creation/delivery
        ("PRD created at docs/prds/core/prd.md.", True),
        ("File written to src/routes/projects.py.", True),
        ("I've created the config at ./config.yaml.", True),
        # False positives we want to avoid
        ("The task is not done yet.", False),  # Negative
        ("I'm working on completing it.", False),  # In progress
        ("All changes will be applied after review.", False),  # Future tense
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


class TestStripCodeBlocks:
    """Tests for _strip_code_blocks preprocessing."""

    def test_removes_fenced_code_block(self):
        """Fenced code blocks should be stripped."""
        text = "Here's the code:\n```python\ndef foo():\n    return 42\n```\nDone."
        result = _strip_code_blocks(text)
        assert "def foo" not in result
        assert "Done." in result

    def test_removes_multiple_code_blocks(self):
        """Multiple code blocks should all be stripped."""
        text = "Block 1:\n```js\nconst x = 1;\n```\nBlock 2:\n```py\ny = 2\n```\nEnd."
        result = _strip_code_blocks(text)
        assert "const x" not in result
        assert "y = 2" not in result
        assert "End." in result

    def test_preserves_inline_backticks(self):
        """Inline backticks (`code`) should not be stripped."""
        text = "Use `foo()` to call it."
        result = _strip_code_blocks(text)
        assert result == text

    def test_preserves_text_without_code_blocks(self):
        """Text with no code blocks should pass through unchanged."""
        text = "Just a normal sentence."
        result = _strip_code_blocks(text)
        assert result == text

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert _strip_code_blocks("") == ""


class TestExtractTail:
    """Tests for _extract_tail preprocessing."""

    def test_extracts_last_n_lines(self):
        """Should return last N non-empty lines."""
        lines = "\n".join(f"line {i}" for i in range(30))
        result = _extract_tail(lines, max_lines=5)
        assert "line 25" in result
        assert "line 29" in result
        assert "line 10" not in result

    def test_skips_empty_lines(self):
        """Empty lines should not count toward the limit."""
        text = "first\n\n\nsecond\n\n\nthird"
        result = _extract_tail(text, max_lines=2)
        assert "second" in result
        assert "third" in result
        assert "first" not in result

    def test_short_text_returns_all(self):
        """Text shorter than max_lines returns all non-empty lines."""
        text = "one\ntwo\nthree"
        result = _extract_tail(text, max_lines=15)
        assert "one" in result
        assert "three" in result

    def test_empty_text(self):
        """Empty text returns empty string."""
        assert _extract_tail("") == ""


class TestCodeBlockFalsePositives:
    """Tests that code block content doesn't trigger false positives."""

    def test_question_mark_in_code_block(self):
        """Ternary ? in code block should not trigger QUESTION."""
        text = "Here's the fix:\n```js\nconst x = y ? 1 : 0;\n```\nI've applied the change."
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.QUESTION

    def test_should_i_in_code_comment(self):
        """'Should I' inside a code block comment should not trigger QUESTION."""
        text = "Updated the code:\n```python\n# Should I refactor this later?\ndef foo(): pass\n```\nChanges applied."
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.QUESTION

    def test_done_in_code_block(self):
        """'done' inside a code block should not trigger COMPLETION by itself."""
        text = "Here's the output:\n```\ndone\nprocessing complete\n```\nI'm still working on the next part."
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.PROGRESS

    def test_please_confirm_in_code_block(self):
        """'please confirm' in a code block should not trigger QUESTION."""
        text = 'Updated:\n```yaml\nmessage: "please confirm your email"\n```\nApplied the config.'
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.QUESTION


class TestTailExtractionIntegration:
    """Tests for tail extraction affecting detection confidence."""

    def test_question_in_tail_gets_high_confidence(self):
        """Question at end of long output should get confidence=1.0."""
        # Build long text with question at end
        lines = ["Working on the implementation..."] * 20
        lines.append("Would you like me to continue?")
        text = "\n".join(lines)
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.QUESTION
        assert result.confidence == 1.0

    def test_question_outside_tail_gets_lower_confidence(self):
        """Question buried early in long output should get confidence=0.8."""
        lines = ["Should I refactor this?"]  # Question at top
        lines.extend(["Processing line..."] * 20)  # 20 progress lines after
        text = "\n".join(lines)
        result = detect_agent_intent(text)
        # "Should I" at position 0 won't be in tail (last 15 of 21 lines)
        # But it WILL match in full-text scan at 0.8
        assert result.intent == TurnIntent.QUESTION
        assert result.confidence == 0.8


class TestBlockedErrorPatterns:
    """Tests for blocked/error pattern detection (mapped to QUESTION)."""

    def test_permission_denied(self):
        """Permission denied should map to QUESTION."""
        result = detect_agent_intent("I don't have permission to access that file.")
        assert result.intent == TurnIntent.QUESTION

    def test_cant_access(self):
        """Can't access should map to QUESTION."""
        result = detect_agent_intent("I can't access the repository.")
        assert result.intent == TurnIntent.QUESTION

    def test_requires_authentication(self):
        """Requires authentication should map to QUESTION."""
        result = detect_agent_intent("This requires authentication to proceed.")
        assert result.intent == TurnIntent.QUESTION

    def test_error_prefix(self):
        """Error: prefix should map to QUESTION."""
        result = detect_agent_intent("Error: Unable to connect to the database.")
        assert result.intent == TurnIntent.QUESTION

    def test_failed_to(self):
        """Failed to should map to QUESTION."""
        result = detect_agent_intent("Failed to install the dependency.")
        assert result.intent == TurnIntent.QUESTION

    def test_unable_to(self):
        """I'm unable to should map to QUESTION."""
        result = detect_agent_intent("I'm unable to find the file you mentioned.")
        assert result.intent == TurnIntent.QUESTION

    def test_couldnt(self):
        """I couldn't should map to QUESTION."""
        result = detect_agent_intent("I couldn't locate the configuration file.")
        assert result.intent == TurnIntent.QUESTION

    def test_was_unable_to(self):
        """I was unable to should map to QUESTION."""
        result = detect_agent_intent("I was unable to parse the JSON response.")
        assert result.intent == TurnIntent.QUESTION

    def test_error_in_code_block_not_detected(self):
        """Error pattern inside a code block should not trigger QUESTION."""
        text = "Here's the log:\n```\nError: something failed\n```\nI've fixed the issue and applied the changes."
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.QUESTION


class TestExpandedQuestionPatterns:
    """Tests for newly added question patterns."""

    def test_want_me_to(self):
        result = detect_agent_intent("Do you want me to refactor this module?")
        assert result.intent == TurnIntent.QUESTION

    def test_how_would_you_like(self):
        result = detect_agent_intent("How would you like me to handle the error case?")
        assert result.intent == TurnIntent.QUESTION

    def test_whats_your_preference(self):
        result = detect_agent_intent("What's your preference for the naming convention?")
        assert result.intent == TurnIntent.QUESTION

    def test_which_approach_prefer(self):
        result = detect_agent_intent("Which approach would you prefer for the caching layer?")
        assert result.intent == TurnIntent.QUESTION

    def test_before_i_proceed(self):
        result = detect_agent_intent("Before I proceed, I wanted to check something.")
        assert result.intent == TurnIntent.QUESTION

    def test_i_need_your_input(self):
        result = detect_agent_intent("I need your input on the database schema.")
        assert result.intent == TurnIntent.QUESTION

    def test_i_need_your_confirmation(self):
        result = detect_agent_intent("I need your confirmation before making changes.")
        assert result.intent == TurnIntent.QUESTION

    def test_do_you_have_a_preference(self):
        result = detect_agent_intent("Do you have a preference between Redis and Memcached?")
        assert result.intent == TurnIntent.QUESTION

    def test_here_are_options(self):
        result = detect_agent_intent("Here are a few options:\n1. Option A\n2. Option B")
        assert result.intent == TurnIntent.QUESTION

    def test_there_are_two_approaches(self):
        result = detect_agent_intent("There are two approaches:\n- Approach A\n- Approach B")
        assert result.intent == TurnIntent.QUESTION

    def test_i_have_a_few_questions(self):
        result = detect_agent_intent("I have a few questions:\n1. What's the target?\n2. Which DB?")
        assert result.intent == TurnIntent.QUESTION


class TestExpandedCompletionPatterns:
    """Tests for newly added completion patterns."""

    def test_made_following_changes(self):
        result = detect_agent_intent("I've made the following changes:\n- Updated config\n- Fixed bug")
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_all_tests_passing(self):
        result = detect_agent_intent("All tests are passing.")
        assert result.intent == TurnIntent.COMPLETION

    def test_pr_ready_for_review(self):
        result = detect_agent_intent("The PR is ready for review.")
        assert result.intent == TurnIntent.COMPLETION

    def test_committed_to_branch(self):
        result = detect_agent_intent("Committed to branch feature/new-feature.")
        assert result.intent == TurnIntent.COMPLETION

    def test_changes_have_been_pushed(self):
        result = detect_agent_intent("Changes have been pushed to the remote.")
        assert result.intent == TurnIntent.COMPLETION

    def test_summary_of_what_was_done(self):
        result = detect_agent_intent("Here's a summary of what was done:\n- Item 1\n- Item 2")
        # Now detected as END_OF_COMMAND (structured summary) rather than COMPLETION
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_all_68_tests_pass(self):
        """'All 68 tests pass' with a number should be COMPLETION."""
        result = detect_agent_intent("All 68 tests pass.")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_12_tests_passed(self):
        """'All 12 tests passed' past tense with number should be COMPLETION."""
        result = detect_agent_intent("All 12 tests passed.")
        assert result.intent == TurnIntent.COMPLETION

    def test_68_passed(self):
        """'68 passed' should be COMPLETION."""
        result = detect_agent_intent("68 passed.")
        assert result.intent == TurnIntent.COMPLETION

    def test_real_world_test_summary_with_changes(self):
        """Real-world output: test results + summary of changes → END_OF_COMMAND."""
        text = (
            "All 68 tests pass. Here's a summary of what was changed:\n\n"
            "prompt_registry.py — 9 prompts updated:\n"
            "- turn_question changed from 1-2 sentences to 18 tokens\n"
            "- task_completion changed from 2-3 sentences to 18 tokens\n\n"
            "Tests updated in test_prompt_registry.py (3 assertions) to match."
        )
        result = detect_agent_intent(text)
        assert result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION)

    def test_summary_of_what_was_changed(self):
        """'Here's a summary of what was changed' should be END_OF_COMMAND."""
        result = detect_agent_intent(
            "Here's a summary of what was changed:\n- Item 1\n- Item 2"
        )
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_heres_what_i_did(self):
        """'Here's what I did' should be END_OF_COMMAND."""
        result = detect_agent_intent(
            "Here's what I did:\n- Updated the config\n- Fixed tests"
        )
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_numbered_change_summary(self):
        """'9 prompts updated' change count should be END_OF_COMMAND."""
        result = detect_agent_intent(
            "9 prompts updated:\n- turn_question\n- turn_completion"
        )
        assert result.intent == TurnIntent.END_OF_COMMAND


class TestCompletionFalsePositiveFix:
    """Tests that the tightened completion pattern rejects mid-sentence matches."""

    def test_all_changes_will_be_applied_is_progress(self):
        """Future tense 'all changes will be applied' should NOT be completion."""
        result = detect_agent_intent("All changes will be applied after review.")
        assert result.intent == TurnIntent.PROGRESS

    def test_all_changes_have_been_applied_is_completion(self):
        """Past tense 'all changes have been applied' should be completion."""
        result = detect_agent_intent("All changes have been applied.")
        assert result.intent == TurnIntent.COMPLETION

    def test_ready_to_start_is_progress(self):
        """'ready to start' should NOT be completion (was previously matched)."""
        result = detect_agent_intent("I'm ready to start working on the feature.")
        assert result.intent == TurnIntent.PROGRESS

    def test_ready_for_deployment_is_progress(self):
        """'ready for deployment' alone should NOT be completion."""
        result = detect_agent_intent("The system is ready for deployment review.")
        assert result.intent == TurnIntent.PROGRESS

    def test_everything_is_set_is_completion(self):
        """'everything is set' should be completion."""
        result = detect_agent_intent("Everything is set.")
        assert result.intent == TurnIntent.COMPLETION


class TestEndOfCommandDetection:
    """Tests for end-of-command detection."""

    def test_summary_with_soft_close(self):
        """Multi-paragraph summary + soft close -> END_OF_COMMAND with high confidence."""
        text = (
            "Here's a summary of the changes I made:\n"
            "- Updated the config module\n"
            "- Fixed the login bug\n"
            "- Added new tests\n\n"
            "Let me know if you'd like any adjustments."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.95

    def test_summary_with_handoff(self):
        """Summary + handoff -> END_OF_COMMAND with high confidence."""
        text = (
            "Here's a summary of everything:\n"
            "- Refactored the service layer\n"
            "- Updated database schema\n\n"
            "Everything should be working now."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.95

    def test_summary_with_continuation_downgrades(self):
        """Summary + 'Next I'll update tests' -> not END_OF_COMMAND (continuation guard)."""
        text = (
            "Here's a summary of the changes I made:\n"
            "- Updated the config module\n"
            "- Fixed the login bug\n\n"
            "Next I'll update the tests to match."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_soft_close_alone(self):
        """'Let me know if you'd like any changes' alone -> END_OF_COMMAND."""
        text = (
            "I've updated the configuration as requested.\n"
            "Let me know if you'd like any changes."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.7

    def test_specific_question_not_end_of_command(self):
        """'Should I proceed with the database migration?' -> QUESTION, not END_OF_COMMAND."""
        result = detect_agent_intent("Should I proceed with the database migration?")
        assert result.intent == TurnIntent.QUESTION

    def test_open_ended_offer(self):
        """'Let me know if there's anything else' -> END_OF_COMMAND."""
        text = (
            "The feature is implemented.\n"
            "Let me know if there's anything else."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_summary_in_code_block_ignored(self):
        """Code block with 'here's a summary' should not trigger end-of-task."""
        text = (
            "Here's the updated code:\n"
            '```python\n# here\'s a summary of the changes\ndef foo(): pass\n```\n'
            "I'm still working on the remaining pieces."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_short_done_is_completion_not_eot(self):
        """Short 'Done.' -> COMPLETION, not END_OF_COMMAND."""
        result = detect_agent_intent("Done.")
        assert result.intent == TurnIntent.COMPLETION
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_feel_free_to_test(self):
        """'Feel free to test' -> END_OF_COMMAND."""
        text = (
            "I've implemented the changes.\n"
            "Feel free to test it out."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_handoff_alone(self):
        """'You can now use the new API' -> END_OF_COMMAND."""
        text = (
            "The migration is complete.\n"
            "You can now use the new endpoint."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.7

    def test_real_world_structured_summary(self):
        """Real-world Claude Code output with structured summary -> END_OF_COMMAND."""
        text = (
            "I've implemented the end-of-task detection feature. Here's a summary of the changes:\n\n"
            "**Files modified:**\n"
            "- `src/services/intent_detector.py` - Added END_OF_COMMAND patterns and detection\n"
            "- `src/models/turn.py` - Added END_OF_COMMAND enum value\n"
            "- `src/services/state_machine.py` - Added transitions\n\n"
            "**Test results:**\n"
            "All 47 targeted tests pass.\n\n"
            "Let me know if you'd like any adjustments."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence >= 0.7

    def test_everything_is_in_place(self):
        """'Everything is in place' -> END_OF_COMMAND via handoff pattern."""
        text = (
            "I've applied all the changes.\n"
            "Everything is in place and ready to go."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_to_recap(self):
        """'To recap' summary -> END_OF_COMMAND."""
        text = (
            "To recap, I made the following changes:\n"
            "- Fixed the login flow\n"
            "- Updated the tests"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_files_were_modified(self):
        """'The following files were modified:' -> END_OF_COMMAND."""
        text = (
            "The following files were modified:\n"
            "- src/app.py\n"
            "- src/config.py\n"
            "- tests/test_app.py"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND


class TestContinuationPatterns:
    """Tests for the continuation guard."""

    def test_next_ill(self):
        """'Next I'll' should trigger continuation guard."""
        text = (
            "Here's a summary of the changes:\n"
            "- Fixed the bug\n"
            "Next I'll add tests."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_now_i_need_to(self):
        """'Now I need to' should trigger continuation guard."""
        text = (
            "Here are the changes I made:\n"
            "- Updated config\n"
            "Now I need to update the tests."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_i_still_need_to(self):
        """'I still need to' should trigger continuation guard."""
        text = (
            "Here's a summary of what I've done so far:\n"
            "- Fixed the login\n"
            "I still need to update the documentation."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_should_i_proceed(self):
        """'Should I proceed' should trigger continuation guard and be QUESTION."""
        text = "I've made the initial changes. Should I proceed with the rest?"
        result = detect_agent_intent(text)
        # This should be QUESTION (from QUESTION_PATTERNS), not END_OF_COMMAND
        assert result.intent == TurnIntent.QUESTION

    def test_moving_on_to(self):
        """'Moving on to' should trigger continuation guard."""
        text = (
            "Here are the changes I implemented:\n"
            "- Updated the API\n"
            "Moving on to the frontend next."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_working_on(self):
        """'Working on' should trigger continuation guard."""
        text = (
            "Here's a summary of the changes:\n"
            "- Fixed the database layer\n"
            "Working on the service layer now."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND


class TestDetectEndOfCommandUnit:
    """Unit tests for _detect_end_of_command function."""

    def test_returns_none_with_continuation(self):
        """Should return None when has_continuation is True."""
        result = _detect_end_of_command(
            "Here's a summary of the changes:\nLet me know if you'd like any adjustments.",
            has_continuation=True,
        )
        assert result is None

    def test_summary_plus_soft_close_high_confidence(self):
        """Summary + soft close -> 0.95 confidence."""
        tail = (
            "Here's a summary of the changes:\n"
            "- Fixed bugs\n"
            "Let me know if you'd like any adjustments."
        )
        result = _detect_end_of_command(tail, has_continuation=False)
        assert result is not None
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.95

    def test_soft_close_alone_lower_confidence(self):
        """Soft close alone -> 0.7 confidence."""
        tail = "Let me know if there's anything else."
        result = _detect_end_of_command(tail, has_continuation=False)
        assert result is not None
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.7

    def test_no_patterns_returns_none(self):
        """Should return None when no patterns match."""
        result = _detect_end_of_command(
            "I'm still working on the implementation.",
            has_continuation=False,
        )
        assert result is None


class TestInferenceClassificationFallback:
    """Tests for _infer_completion_classification."""

    def test_finished_classification(self):
        """LLM returning 'A' should map to END_OF_COMMAND."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "A"
        mock_service.infer.return_value = mock_result

        result = _infer_completion_classification("Some tail text", mock_service)
        assert result is not None
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.85

    def test_continuing_classification(self):
        """LLM returning 'B' should map to PROGRESS."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "B"
        mock_service.infer.return_value = mock_result

        result = _infer_completion_classification("Some tail text", mock_service)
        assert result is not None
        assert result.intent == TurnIntent.PROGRESS

    def test_asking_classification(self):
        """LLM returning 'C' should map to QUESTION."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "C"
        mock_service.infer.return_value = mock_result

        result = _infer_completion_classification("Some tail text", mock_service)
        assert result is not None
        assert result.intent == TurnIntent.QUESTION

    def test_blocked_classification(self):
        """LLM returning 'D' should map to QUESTION."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "D"
        mock_service.infer.return_value = mock_result

        result = _infer_completion_classification("Some tail text", mock_service)
        assert result is not None
        assert result.intent == TurnIntent.QUESTION

    def test_exception_returns_none(self):
        """Exception from inference should return None (graceful degradation)."""
        mock_service = MagicMock()
        mock_service.infer.side_effect = Exception("API error")

        result = _infer_completion_classification("Some tail text", mock_service)
        assert result is None

    def test_invalid_letter_returns_none(self):
        """Invalid letter from LLM should return None."""
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "Z"
        mock_service.infer.return_value = mock_result

        result = _infer_completion_classification("Some tail text", mock_service)
        assert result is None

    def test_inference_fallback_in_detect_agent_intent(self):
        """Inference fallback should be called when no patterns match and service available."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_result = MagicMock()
        mock_result.text = "A"
        mock_service.infer.return_value = mock_result

        # Use text that matches no patterns
        result = detect_agent_intent(
            "The error occurs because the database connection times out after 30 seconds.",
            inference_service=mock_service,
        )
        assert result.intent == TurnIntent.END_OF_COMMAND
        assert result.confidence == 0.85

    def test_inference_not_called_when_pattern_matches(self):
        """Inference should NOT be called when a pattern already matched."""
        mock_service = MagicMock()
        mock_service.is_available = True

        result = detect_agent_intent("Done.", inference_service=mock_service)
        assert result.intent == TurnIntent.COMPLETION
        mock_service.infer.assert_not_called()

    def test_inference_not_called_when_service_unavailable(self):
        """Inference should NOT be called when service is not available."""
        mock_service = MagicMock()
        mock_service.is_available = False

        result = detect_agent_intent(
            "Some ambiguous text that matches nothing.",
            inference_service=mock_service,
        )
        assert result.intent == TurnIntent.PROGRESS
        mock_service.infer.assert_not_called()


class TestCompletionOpenerDetection:
    """Integration tests for completion opener detection via detect_agent_intent."""

    def test_done_with_detail(self):
        """'Done. All files updated...' should detect as COMPLETION."""
        result = detect_agent_intent(
            "Done. All files now consistently use anthropic/claude-3-haiku."
        )
        assert result.intent == TurnIntent.COMPLETION
        assert result.confidence == 0.75

    def test_complete_with_detail(self):
        """'Complete. The feature is ready.' should detect as COMPLETION."""
        result = detect_agent_intent("Complete. The feature is ready for review.")
        assert result.intent == TurnIntent.COMPLETION

    def test_finished_with_detail(self):
        """'Finished. Here's what changed...' should detect as COMPLETION."""
        result = detect_agent_intent("Finished. Here's what changed in the codebase.")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_done_with_detail(self):
        """'All done! The tests pass.' should detect as COMPLETION."""
        result = detect_agent_intent("All done! The tests pass and coverage is at 95%.")
        assert result.intent == TurnIntent.COMPLETION

    def test_done_with_soft_close_boosted(self):
        """'Done. Let me know if you'd like changes.' should get boosted confidence."""
        result = detect_agent_intent(
            "Done. Let me know if you'd like any changes."
        )
        # Soft-close boosts opener to 0.9
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)
        assert result.confidence >= 0.7

    def test_done_standalone_still_works(self):
        """'Done.' alone should still detect as COMPLETION via existing pattern."""
        result = detect_agent_intent("Done.")
        assert result.intent == TurnIntent.COMPLETION
        assert result.confidence == 1.0  # Existing pattern, Phase 1

    def test_done_with_continuation_is_not_completion(self):
        """'Done. ... Now I need to...' should NOT be COMPLETION (continuation guard)."""
        result = detect_agent_intent(
            "Done. Fixed the login bug.\nNow I need to work on the tests."
        )
        assert result.intent != TurnIntent.COMPLETION

    def test_question_takes_priority_over_opener(self):
        """'I'm done. Should I continue?' -> QUESTION (question fires before opener)."""
        result = detect_agent_intent("I'm done. Should I continue?")
        assert result.intent == TurnIntent.QUESTION

    def test_mid_sentence_done_no_match(self):
        """'The task is done already.' should NOT match opener (no punctuation after done)."""
        result = detect_agent_intent("The task is done already.")
        assert result.intent == TurnIntent.PROGRESS

    def test_lowercase_done_at_start(self):
        """'done. everything is updated.' should match (case insensitive)."""
        result = detect_agent_intent("done. everything is updated and tests pass.")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_set_with_detail(self):
        """'All set! The configuration has been updated.' should detect as COMPLETION."""
        result = detect_agent_intent("All set! The configuration has been updated.")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_finished_with_detail(self):
        """'All finished. Three files were modified.' should detect as COMPLETION."""
        result = detect_agent_intent("All finished. Three files were modified.")
        assert result.intent == TurnIntent.COMPLETION

    def test_real_world_done_buried_in_response(self):
        """Real-world case: 'Done.' mid-response after tool output lines."""
        text = (
            "Updated the pluralization logic in the template.\n"
            "Updated the CSS for button alignment.\n"
            "\n"
            "Done. Two changes:\n"
            "\n"
            '  - The text now reads "4 active agents" '
            '(pluralized — shows "1 active agent" for singular)\n'
            "  - Brain Reboot button is aligned on the same row "
            "as the project name heading"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_opener_not_at_start_of_tail(self):
        """Opener on a later line (not first) in tail should still match."""
        lines = ["Processing file..."] * 5
        lines.append("Done. All files now consistently use anthropic/claude-3-haiku.")
        text = "\n".join(lines)
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION


class TestArtifactCreationCompletion:
    """Tests for artifact creation/delivery completion patterns."""

    def test_prd_created_at_path(self):
        """'PRD created at docs/...' should detect as completion."""
        result = detect_agent_intent(
            "PRD created at docs/prds/core/e4-s2-project-controls-prd.md."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_file_created_at_path(self):
        """'File created at src/...' should detect as completion."""
        result = detect_agent_intent("File created at src/services/new_service.py.")
        assert result.intent == TurnIntent.COMPLETION

    def test_ive_created_the_file(self):
        """'I've created the file at ...' should detect as completion."""
        result = detect_agent_intent(
            "I've created the file at src/routes/projects.py."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_migration_written_to_path(self):
        """'Migration written to migrations/...' should detect as completion."""
        result = detect_agent_intent(
            "Migration written to migrations/versions/001_add_fields.py."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_config_saved_to_path(self):
        """'Config saved to config.yaml' should detect as completion."""
        result = detect_agent_intent("Config saved to ./config.yaml.")
        assert result.intent == TurnIntent.COMPLETION

    def test_spec_generated_at_path(self):
        """'Spec generated at ...' should detect as completion."""
        result = detect_agent_intent(
            "Spec generated at openspec/specs/project-controls/spec.md."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_artifact_summary_message(self):
        """Real-world PRD creation summary should detect as END_OF_COMMAND."""
        text = (
            "PRD created at docs/prds/core/e4-s2-project-controls-prd.md. "
            "Here's a summary of what it covers:\n\n"
            "Core deliverables:\n"
            "- Project CRUD API (7 endpoints)\n"
            "- Projects management UI at /projects\n"
            "- Manual-only registration\n\n"
            "Data model changes: 4 new columns on projects table\n\n"
            "Key technical details:\n"
            "- Inference gating at caller level\n"
            "- Priority scoring filters out paused-project agents\n\n"
            "Files: 6 new files, 8 modified files"
        )
        result = detect_agent_intent(text)
        assert result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION)

    def test_artifact_summary_with_intermediate_text(self):
        """Artifact creation with intermediate text blocks should still detect completion.

        This simulates transcript text where the last assistant message contains
        intermediate text blocks from before tool calls, followed by the summary.
        """
        text = (
            "Now I have all the context needed. Let me create the PRD.\n"
            "PRD created at docs/prds/core/e4-s2-prd.md. "
            "Here's a summary of what it covers:\n\n"
            "Core deliverables:\n"
            "- Project CRUD API\n"
            "- Projects management UI\n\n"
            "Files: 6 new files, 8 modified files"
        )
        result = detect_agent_intent(text)
        assert result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION)


class TestNumberedFileSummaryPatterns:
    """Tests for adjective-first numbered file summary patterns."""

    def test_new_files_count(self):
        """'6 new files' should be detected as END_OF_COMMAND summary."""
        result = detect_agent_intent("6 new files created for the feature.")
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_modified_files_count(self):
        """'8 modified files' should be detected as END_OF_COMMAND summary."""
        result = detect_agent_intent("8 modified files across the codebase.")
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_created_tests_count(self):
        """'3 new tests' should be detected as END_OF_COMMAND summary."""
        result = detect_agent_intent("3 new tests added for coverage.")
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_deleted_files_count(self):
        """'2 deleted files' should be detected as END_OF_COMMAND summary."""
        result = detect_agent_intent("2 deleted files that were no longer needed.")
        assert result.intent == TurnIntent.END_OF_COMMAND


class TestContinuationGuardWindow:
    """Tests that continuation guard only checks the last few lines."""

    def test_intermediate_working_on_does_not_block_completion(self):
        """'Working on' in intermediate text should NOT block completion detection.

        When the transcript has intermediate text from before tool calls
        (e.g. 'I'm working on creating the PRD') followed by a completion
        summary, the completion should still be detected.
        """
        text = (
            "I'm working on creating the PRD now.\n"
            "PRD created at docs/prds/core/prd.md. "
            "Here's a summary of what it covers:\n"
            "- Feature A\n"
            "- Feature B\n"
            "- Feature C\n"
            "- Feature D\n"
            "- Feature E\n"
            "- Feature F\n"
            "Let me know if you'd like any adjustments."
        )
        result = detect_agent_intent(text)
        assert result.intent in (TurnIntent.END_OF_COMMAND, TurnIntent.COMPLETION)

    def test_intermediate_let_me_also_does_not_block(self):
        """'Let me also' in intermediate text should NOT block completion."""
        text = (
            "Let me also check the integration points.\n"
            "Here are the changes I made:\n"
            "- Updated config\n"
            "- Fixed tests\n"
            "- Added migration\n"
            "- Updated routes\n"
            "- Added templates\n"
            "- Updated docs\n"
            "Let me know if there's anything else."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_working_on_at_end_still_blocks(self):
        """'Working on' at the END of the message should still block completion."""
        text = (
            "Here's a summary of the changes:\n"
            "- Fixed the database layer\n"
            "Working on the service layer now."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND

    def test_next_ill_at_end_still_blocks(self):
        """'Next I'll' at the end should still trigger continuation guard."""
        text = (
            "Here's a summary of the changes:\n"
            "- Fixed the bug\n"
            "Next I'll add tests."
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.END_OF_COMMAND


class TestCompletionOpenerUnit:
    """Unit tests for _detect_completion_opener function."""

    def test_returns_none_with_continuation(self):
        """Should return None when has_continuation is True."""
        result = _detect_completion_opener(
            "Done. All files updated.", has_continuation=True
        )
        assert result is None

    def test_plain_opener_returns_completion(self):
        """Plain opener should return COMPLETION with 0.75 confidence."""
        result = _detect_completion_opener(
            "Done. All files updated.", has_continuation=False
        )
        assert result is not None
        assert result.intent == TurnIntent.COMPLETION
        assert result.confidence == 0.75

    def test_opener_with_soft_close_boosted(self):
        """Opener + soft-close should return COMPLETION with 0.9 confidence."""
        result = _detect_completion_opener(
            "Done. Let me know if you'd like any adjustments.",
            has_continuation=False,
        )
        assert result is not None
        assert result.intent == TurnIntent.COMPLETION
        assert result.confidence == 0.9

    def test_no_opener_returns_none(self):
        """Should return None when no opener patterns match."""
        result = _detect_completion_opener(
            "I'm still working on the implementation.", has_continuation=False
        )
        assert result is None

    def test_done_without_punctuation_returns_none(self):
        """'done with' (no punctuation after 'done') should return None."""
        result = _detect_completion_opener(
            "done with the first part of the task", has_continuation=False
        )
        assert result is None

    def test_opener_on_later_line_in_multiline_tail(self):
        """Opener on a non-first line should still match (multiline ^)."""
        tail = (
            "Updated the CSS for button alignment.\n"
            "Done. Two changes made to the codebase."
        )
        result = _detect_completion_opener(tail, has_continuation=False)
        assert result is not None
        assert result.intent == TurnIntent.COMPLETION
        assert result.confidence == 0.75


class TestStatusReportCompletion:
    """Tests for status-report style completion patterns (e.g. 'Everything looks healthy')."""

    def test_everything_looks_healthy(self):
        """'Everything looks healthy after the server restart.' should detect completion."""
        result = detect_agent_intent("Everything looks healthy after the server restart.")
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_everything_looks_good(self):
        """'Everything looks good.' should detect completion."""
        result = detect_agent_intent("Everything looks good.")
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_everything_appears_correct(self):
        """'Everything appears correct.' should detect completion."""
        result = detect_agent_intent("Everything appears correct.")
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_everything_seems_fine(self):
        """'Everything seems fine.' should detect completion."""
        result = detect_agent_intent("Everything seems fine.")
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_status_report_with_bullet_points(self):
        """Full multi-line status report ending with 'everything looks healthy' -> completion."""
        text = (
            "The dashboard is running and showing this session. It shows:\n"
            "- 1 active agent (#28919c2a) on claude_headspace project\n"
            "- Status: WORKING [1], with \"Processing...\" state\n"
            "Everything looks healthy after the server restart."
        )
        result = detect_agent_intent(text)
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_everything_looks_healthy_as_handoff(self):
        """'Everything looks healthy' should match the handoff pattern for END_OF_COMMAND."""
        text = (
            "I've restarted the server and checked the dashboard.\n"
            "Everything looks healthy."
        )
        result = detect_agent_intent(text)
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_everything_is_good(self):
        """'Everything is good.' should detect completion (broadened 'is' adjectives)."""
        result = detect_agent_intent("Everything is good.")
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)


class TestCookedCompletionMarker:
    """Tests for Claude Code CLI completion marker (✻ Cooked for Xm Xs)."""

    def test_cooked_marker(self):
        """'✻ Cooked for 1m 33s' should detect as completion."""
        result = detect_agent_intent("✻ Cooked for 1m 33s")
        assert result.intent == TurnIntent.COMPLETION

    def test_baked_marker(self):
        """'✻ Baked for 2m 5s' should detect as completion."""
        result = detect_agent_intent("✻ Baked for 2m 5s")
        assert result.intent == TurnIntent.COMPLETION

    def test_checkmark_variant(self):
        """'✓ Worked for 45s' should detect as completion."""
        result = detect_agent_intent("✓ Worked for 45s")
        assert result.intent == TurnIntent.COMPLETION

    def test_simmered_marker(self):
        """'✻ Simmered for 3m 12s' should detect as completion."""
        result = detect_agent_intent("✻ Simmered for 3m 12s")
        assert result.intent == TurnIntent.COMPLETION

    def test_pondered_marker(self):
        """'✻ Pondered for 10m 2s' should detect as completion."""
        result = detect_agent_intent("✻ Pondered for 10m 2s")
        assert result.intent == TurnIntent.COMPLETION


class TestCommandCompleteMarker:
    """Tests for TASK COMPLETE structured completion marker."""

    def test_command_complete_marker_basic(self):
        """'TASK COMPLETE — <summary>' should detect as completion."""
        result = detect_agent_intent(
            "---\nTASK COMPLETE — Returned current Unix timestamp.\n---"
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_command_complete_marker_with_tests(self):
        """'TASK COMPLETE — <summary>. Tests: N passed.' should detect as completion."""
        result = detect_agent_intent(
            "---\nTASK COMPLETE — Fixed login bug. Tests: 12 passed.\n---"
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_command_complete_marker_inline(self):
        """TASK COMPLETE marker without surrounding --- lines should still detect."""
        result = detect_agent_intent(
            "TASK COMPLETE — Added the new endpoint and updated tests."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_command_complete_marker_at_end_of_long_response(self):
        """TASK COMPLETE marker at end of a long agent response should detect as completion."""
        lines = ["Working on the implementation..."] * 20
        lines.append("---")
        lines.append("TASK COMPLETE — Implemented feature and ran all tests.")
        lines.append("---")
        text = "\n".join(lines)
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_command_complete_marker_with_regular_dash(self):
        """TASK COMPLETE with regular dash should also detect."""
        result = detect_agent_intent(
            "TASK COMPLETE - Updated the configuration."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_command_complete_case_insensitive(self):
        """TASK COMPLETE should match case-insensitively."""
        result = detect_agent_intent(
            "Task Complete — Refactored the service layer."
        )
        assert result.intent == TurnIntent.COMPLETION


class TestGitSuccessPatterns:
    """Tests for git commit/push completion patterns."""

    def test_committed_and_pushed(self):
        """'Committed and pushed: <hash>' should detect as completion."""
        result = detect_agent_intent(
            "Committed and pushed: `755ed18` on `development`. Working tree clean. All 165 tests pass."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_committed_hash_and_pushed(self):
        """'Committed <hash> and pushed to <branch>' should detect as completion."""
        result = detect_agent_intent(
            "Committed 8b58cab and pushed to development."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_working_tree_clean(self):
        """'Working tree clean' should detect as completion."""
        result = detect_agent_intent("Working tree clean.")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_passing(self):
        """'all passing' should detect as completion."""
        result = detect_agent_intent(
            "Ran all 26 objective route tests — all passing."
        )
        assert result.intent == TurnIntent.COMPLETION


class TestBlockedPatternFalsePositives:
    """Tests that 'Failed to' inside descriptions doesn't trigger false positives."""

    def test_failed_to_in_quoted_text_not_blocked(self):
        """'Failed to' inside a description of a fix should NOT be QUESTION."""
        text = (
            'The endpoint works. Here\'s what I found and fixed:\n\n'
            '**Root cause:** The except blocks returned a generic '
            '"Failed to save objective" message.\n\n'
            '**Fix applied:** Added logger.exception calls.\n\n'
            'Ran all 26 objective route tests — all passing. '
            'Server restarted with the fix live.'
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.QUESTION

    def test_failed_to_in_logger_example_not_blocked(self):
        """'Failed to' inside logger.exception example should NOT be QUESTION."""
        text = (
            'Added `logger.exception("Failed to save objective")` '
            'to both exception handlers. All tests passing.'
        )
        result = detect_agent_intent(text)
        assert result.intent != TurnIntent.QUESTION

    def test_real_failed_to_at_line_start_still_blocked(self):
        """'Failed to' at start of line should still be detected as blocked."""
        result = detect_agent_intent("Failed to install the dependency.")
        assert result.intent == TurnIntent.QUESTION

    def test_error_at_line_start_still_blocked(self):
        """'Error:' at start of line should still be detected as blocked."""
        result = detect_agent_intent("Error: Unable to connect to the database.")
        assert result.intent == TurnIntent.QUESTION

    def test_permission_denied_still_blocked(self):
        """'Permission denied' anywhere should still be detected as blocked."""
        result = detect_agent_intent("The operation failed: Permission denied.")
        assert result.intent == TurnIntent.QUESTION

    def test_real_world_objective_fix_transcript(self):
        """Exact transcript text from the objective endpoint fix should be COMPLETION."""
        text = (
            'The endpoint works. Here\'s what I found and fixed:\n\n'
            '**What happened:** Your `POST /api/objective` request at 14:18:22 '
            'returned a 500 error. The server was restarted at 14:19:31 '
            '(which is why subsequent requests would have worked).\n\n'
            '**Root cause:** Unknown \u2014 the exception handlers in `objective.py` '
            'were silently swallowing all exceptions. The `except` blocks caught '
            'the error, rolled back the DB transaction, and returned a generic '
            '"Failed to save objective" message, but **never logged the actual '
            'exception**. There\'s no traceback in the logs, just the werkzeug '
            'access log showing the 500 status code.\n\n'
            '**Fix applied:** Added `logger.exception(...)` calls to both exception '
            'handlers in `src/claude_headspace/routes/objective.py`:\n'
            '- Line 162: `logger.exception("Failed to save objective")` in the POST endpoint\n'
            '- Line 233: `logger.exception("Failed to fetch objective history")` in the history endpoint\n\n'
            'This ensures the full traceback will be logged if this happens again, '
            'making it diagnosable. Ran all 26 objective route tests \u2014 all passing. '
            'Server restarted with the fix live.'
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION


class TestConfirmationDetection:
    """Tests for _is_confirmation helper and confirmation detection in detect_user_intent."""

    # _is_confirmation unit tests

    def test_bare_affirmative_yes(self):
        """'yes' should be detected as confirmation."""
        assert _is_confirmation("yes") is True

    def test_bare_affirmative_y(self):
        """'y' should be detected as confirmation."""
        assert _is_confirmation("y") is True

    def test_bare_affirmative_ok(self):
        """'ok' should be detected as confirmation."""
        assert _is_confirmation("ok") is True

    def test_bare_affirmative_sure(self):
        """'sure' should be detected as confirmation."""
        assert _is_confirmation("sure") is True

    def test_bare_affirmative_go_ahead(self):
        """'go ahead' should be detected as confirmation."""
        assert _is_confirmation("go ahead") is True

    def test_bare_affirmative_lgtm(self):
        """'LGTM' should be detected as confirmation (case insensitive)."""
        assert _is_confirmation("LGTM") is True

    def test_bare_affirmative_with_period(self):
        """'Yes.' should be detected as confirmation (trailing punctuation stripped)."""
        assert _is_confirmation("Yes.") is True

    def test_bare_affirmative_with_exclamation(self):
        """'OK!' should be detected as confirmation."""
        assert _is_confirmation("OK!") is True

    def test_plan_approval_clear_context(self):
        """Plan approval 'Yes, clear context and auto-accept edits' should be confirmation."""
        assert _is_confirmation("Yes, clear context and auto-accept edits") is True

    def test_plan_approval_manually_approve(self):
        """Plan approval 'Yes, manually approve each edit' should be confirmation."""
        assert _is_confirmation("Yes, manually approve each edit") is True

    def test_substantive_command_not_confirmation(self):
        """'Fix the bug' should NOT be confirmation."""
        assert _is_confirmation("Fix the bug") is False

    def test_stop_command_not_confirmation(self):
        """'Stop that, do this instead' should NOT be confirmation."""
        assert _is_confirmation("Stop that, do this instead") is False

    def test_empty_text_not_confirmation(self):
        """Empty string should NOT be confirmation."""
        assert _is_confirmation("") is False

    # detect_user_intent integration tests

    def test_yes_during_processing_is_answer(self):
        """'yes' during PROCESSING should be ANSWER."""
        result = detect_user_intent("yes", CommandState.PROCESSING)
        assert result.intent == TurnIntent.ANSWER
        assert result.confidence == 0.9
        assert result.matched_pattern == "confirmation"

    def test_plan_approval_during_processing_is_answer(self):
        """Plan approval text during PROCESSING should be ANSWER."""
        result = detect_user_intent(
            "Yes, clear context and auto-accept edits", CommandState.PROCESSING
        )
        assert result.intent == TurnIntent.ANSWER

    def test_substantive_command_during_processing_is_command(self):
        """'Fix the bug' during PROCESSING should still be COMMAND."""
        result = detect_user_intent("Fix the bug in login", CommandState.PROCESSING)
        assert result.intent == TurnIntent.COMMAND

    def test_confirmation_during_idle_is_command(self):
        """'yes' during IDLE should be COMMAND (confirmation only applies during PROCESSING)."""
        result = detect_user_intent("yes", CommandState.IDLE)
        assert result.intent == TurnIntent.COMMAND

    def test_confirmation_during_complete_is_command(self):
        """'yes' during COMPLETE should be COMMAND."""
        result = detect_user_intent("yes", CommandState.COMPLETE)
        assert result.intent == TurnIntent.COMMAND

    def test_none_text_during_processing_is_command(self):
        """None text during PROCESSING should be COMMAND (not matched as confirmation)."""
        result = detect_user_intent(None, CommandState.PROCESSING)
        assert result.intent == TurnIntent.COMMAND

    def test_empty_text_during_processing_is_command(self):
        """Empty text during PROCESSING should be COMMAND."""
        result = detect_user_intent("", CommandState.PROCESSING)
        assert result.intent == TurnIntent.COMMAND


class TestCompletionOverridesFollowUpQuestion:
    """Tests that completed commands with follow-up questions are COMPLETION, not QUESTION.

    When an agent finishes its work and asks a follow-up question about
    optional additional work, the command IS complete. The follow-up question
    is about starting a NEW potential command, not continuing the current one.
    """

    def test_completion_with_followup_question(self):
        """Completed command + follow-up question → COMPLETION, not QUESTION."""
        text = (
            "All tests passed. Would you like me to also update the docs?"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_committed_and_pushed_with_followup(self):
        """Git commit + follow-up → COMPLETION."""
        text = (
            "Committed 8b58cab and pushed to development. "
            "The remaining unstaged changes are from prior work. "
            "Would you like me to clean those up too?"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_test_results_with_followup(self):
        """Test results + follow-up → COMPLETION."""
        text = (
            "Ran 12 card_state tests (all passed) and 50 dashboard "
            "route tests (49 passed, 1 pre-existing failure).\n"
            "Would you like me to investigate the failing test?"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_done_with_offer_for_more(self):
        """'Done' + offer for additional work → COMPLETION."""
        text = (
            "I've finished implementing the feature. "
            "Do you want me to add more test coverage?"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_continuation_question_still_wins(self):
        """'Should I proceed/continue' still wins over completion (continuation guard)."""
        result = detect_agent_intent("I'm done. Should I continue?")
        assert result.intent == TurnIntent.QUESTION

    def test_genuine_question_no_completion(self):
        """Pure question with no completion evidence → QUESTION."""
        result = detect_agent_intent(
            "I have some concerns about the approach. "
            "Would you like me to explain the trade-offs?"
        )
        assert result.intent == TurnIntent.QUESTION

    def test_intermediate_question_then_completion(self):
        """Intermediate question followed by completion in multi-message transcript."""
        text = (
            "I need to check something first. Should I use approach A?\n\n"
            "OK, I used approach A. Here's what I changed:\n"
            "- Updated config.py\n"
            "- Fixed the login flow\n"
            "- Added tests\n\n"
            "All 12 tests passed. Committed and pushed to development."
        )
        result = detect_agent_intent(text)
        # END_OF_COMMAND or COMPLETION both indicate task is done
        assert result.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND)

    def test_real_world_commit_push_completion(self):
        """Real-world commit+push output should be COMPLETION."""
        text = (
            "Committed 8b58cab and pushed to development. "
            "The remaining unstaged changes are from prior work, "
            "unrelated to this task."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION


class TestNewCompletionPatterns:
    """Tests for newly added completion patterns."""

    def test_ran_tests_report(self):
        """'Ran 12 tests' should detect as COMPLETION."""
        result = detect_agent_intent("Ran 12 tests successfully.")
        assert result.intent == TurnIntent.COMPLETION

    def test_ran_tests_with_name(self):
        """'Ran 12 card_state tests' should detect as COMPLETION."""
        result = detect_agent_intent(
            "Ran 12 card_state tests (all passed)."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_parenthetical_all_passed(self):
        """'(all passed)' should detect as COMPLETION."""
        result = detect_agent_intent(
            "Ran 50 dashboard route tests (all passed)."
        )
        assert result.intent == TurnIntent.COMPLETION

    def test_all_tests_passed_no_count(self):
        """'all tests passed' without count should detect as COMPLETION."""
        result = detect_agent_intent("All tests passed.")
        assert result.intent == TurnIntent.COMPLETION

    def test_all_tests_pass_no_count(self):
        """'all tests pass' without count should detect as COMPLETION."""
        result = detect_agent_intent("All tests pass.")
        assert result.intent == TurnIntent.COMPLETION

    def test_ive_made_following_changes_is_eot(self):
        """'I've made the following changes:' should be END_OF_COMMAND."""
        result = detect_agent_intent(
            "I've made the following changes:\n- Fixed bug\n- Updated tests"
        )
        assert result.intent == TurnIntent.END_OF_COMMAND


class TestTrailingQuestionGuard:
    """Tests for Phase 0.5 trailing question guard.

    The guard detects conversational questions at the end of agent output
    that would otherwise be misclassified as COMPLETION because completion
    patterns match earlier in the message body.
    """

    def test_pure_conversational_question(self):
        """Pure conversational question → QUESTION."""
        result = detect_agent_intent("Want me to check if the server is up?")
        assert result.intent == TurnIntent.QUESTION

    def test_multi_line_response_ending_with_question(self):
        """Multi-line response ending with question → QUESTION."""
        text = (
            "I've looked at the configuration and the settings seem correct.\n"
            "The database is configured properly.\n"
            "Want me to check if the server is up?"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.QUESTION

    def test_completion_deep_in_body_question_at_end(self):
        """Completion evidence deep in body, question at tail → QUESTION.

        This is the core scenario: the agent's output contains completion-like
        text (e.g. test results) earlier in a long message, but the final
        lines are a question. The completion evidence must be pushed outside
        the 15-line tail window so Phase 0 (END_OF_COMMAND) doesn't fire first.
        """
        # Build enough lines to push "All 12 tests passed" out of the tail
        lines = [
            "I've updated the configuration files.",
            "All 12 tests passed.",
            "The migration ran successfully.",
        ]
        # Add filler lines to push completion evidence out of 15-line tail
        lines.extend([f"Updated file_{i}.py with new config." for i in range(15)])
        lines.extend([
            "",
            "I noticed the deployment config is outdated.",
            "Should I update it as well?",
        ])
        text = "\n".join(lines)
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.QUESTION

    def test_completion_plus_question_in_same_trailing_window(self):
        """Completion + question in same 3-line window → still COMPLETION.

        When both completion evidence AND a question are in the trailing
        window, the guard skips and lets Phase 1 handle it (preserving
        existing 'completion overrides follow-up question' behavior).
        """
        text = "All tests passed. Would you like me to also update the docs?"
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

    def test_soft_close_still_end_of_command(self):
        """Soft-close offers → still END_OF_COMMAND (guard skips)."""
        text = (
            "I've applied all the changes.\n"
            "Let me know if you'd like any adjustments."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.END_OF_COMMAND

    def test_trailing_blocked_pattern(self):
        """Blocked/error pattern at tail → QUESTION."""
        text = (
            "I tried to access the deployment server.\n"
            "The connection was established.\n"
            "I couldn't locate the configuration file."
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.QUESTION

    def test_unit_returns_none_with_continuation(self):
        """Unit: _detect_trailing_question returns None when has_continuation=True."""
        result = _detect_trailing_question(
            "Want me to check the server?", has_continuation=True
        )
        assert result is None

    def test_unit_returns_none_for_empty_tail(self):
        """Unit: _detect_trailing_question returns None for empty tail."""
        result = _detect_trailing_question("", has_continuation=False)
        assert result is None

    def test_unit_returns_question_for_trailing_question(self):
        """Unit: _detect_trailing_question returns QUESTION for trailing question."""
        tail = (
            "Some progress text.\n"
            "More details here.\n"
            "Want me to check the server?"
        )
        result = _detect_trailing_question(tail, has_continuation=False)
        assert result is not None
        assert result.intent == TurnIntent.QUESTION
        assert result.confidence == 0.95

    def test_unit_skips_when_completion_in_trailing_window(self):
        """Unit: guard skips when COMPLETION pattern is in trailing window."""
        tail = "All tests passed. Want me to continue?"
        result = _detect_trailing_question(tail, has_continuation=False)
        assert result is None

    def test_unit_skips_when_soft_close_in_trailing_window(self):
        """Unit: guard skips when soft-close pattern is in trailing window."""
        tail = "Let me know if you'd like any adjustments."
        result = _detect_trailing_question(tail, has_continuation=False)
        assert result is None

    def test_existing_completion_override_still_works(self):
        """Existing TestCompletionOverridesFollowUpQuestion cases still pass.

        The trailing question guard must NOT break the existing behavior where
        completion + follow-up question → COMPLETION.
        """
        # Committed and pushed with follow-up
        text = (
            "Committed 8b58cab and pushed to development. "
            "The remaining unstaged changes are from prior work. "
            "Would you like me to clean those up too?"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION

        # Test results with follow-up
        text2 = (
            "Ran 12 card_state tests (all passed) and 50 dashboard "
            "route tests (49 passed, 1 pre-existing failure).\n"
            "Would you like me to investigate the failing test?"
        )
        result2 = detect_agent_intent(text2)
        assert result2.intent == TurnIntent.COMPLETION

    def test_question_mark_multiline_flag(self):
        """(?m) flag on QUESTION_PATTERNS[0] matches ? at end-of-line, not just end-of-string."""
        text = (
            "Should I update the deployment config?\n"
            "Here are the details of what changed."
        )
        # The question mark is at end of line 1 (not end of string)
        # With (?m), $ matches end-of-line so this should still detect
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.QUESTION


class TestCommandCompleteMarkerInFullResponse:
    """Tests that TASK COMPLETE marker is detected as COMPLETION in realistic full responses.

    Regression tests for task 1057: a joke response with embedded question marks
    (inside the joke text) was not being detected as COMPLETION despite ending
    with the TASK COMPLETE marker. The command stayed in AWAITING_INPUT instead of
    transitioning to COMPLETE.
    """

    def test_joke_response_with_command_complete_marker(self):
        """Full joke response ending with TASK COMPLETE marker should be COMPLETION.

        This is the exact scenario that caused task 1057 to stay in AWAITING_INPUT:
        a joke containing embedded question marks followed by the TASK COMPLETE marker.
        """
        text = (
            "Here's an absurdist one:\n"
            "\n"
            "A horse walks into a bar. The bartender asks, \"Why the long face?\" "
            "The horse says, \"I just realized I'm a metaphor for existential dread.\" "
            "The bartender nods, turns into a lamp, and nobody is surprised because "
            "the bar was actually a dream being had by a potato.\n"
            "\n"
            "---\n"
            "TASK COMPLETE \u2014 Delivered an absurdist joke after asking the user's preference.\n"
            "---"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION, (
            f"Expected COMPLETION but got {result.intent.value} "
            f"(pattern={result.matched_pattern})"
        )

    def test_one_liner_joke_with_command_complete_marker(self):
        """One-liner joke with TASK COMPLETE marker should be COMPLETION."""
        text = (
            "Here's a one-liner for you:\n"
            "\n"
            "I told my suitcase there would be no vacation this year "
            "\u2014 now I'm dealing with emotional baggage.\n"
            "\n"
            "---\n"
            "TASK COMPLETE \u2014 Delivered a one-liner joke after asking the user's preference.\n"
            "---"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION, (
            f"Expected COMPLETION but got {result.intent.value} "
            f"(pattern={result.matched_pattern})"
        )

    def test_response_with_embedded_questions_and_command_complete(self):
        """Response containing question marks in quoted text + TASK COMPLETE should be COMPLETION.

        The embedded question marks (inside quotes) must not override the TASK COMPLETE
        marker at the end via the trailing question guard or question patterns.
        """
        text = (
            "The function checks if the user asked \"are you sure?\" before proceeding.\n"
            "I've updated the validation logic to handle this edge case.\n"
            "\n"
            "---\n"
            "TASK COMPLETE \u2014 Updated validation logic for quoted question handling.\n"
            "---"
        )
        result = detect_agent_intent(text)
        assert result.intent == TurnIntent.COMPLETION, (
            f"Expected COMPLETION but got {result.intent.value} "
            f"(pattern={result.matched_pattern})"
        )


class TestHandoffPatterns:
    """Tests for HANDOFF_PATTERNS regex matching."""

    # ── Positive matches ──────────────────────────────────────────────

    def test_bare_handoff(self):
        assert _match_patterns("handoff", HANDOFF_PATTERNS)

    def test_bare_hand_off_space(self):
        assert _match_patterns("hand off", HANDOFF_PATTERNS)

    def test_prepare_handoff(self):
        """The exact phrase from the bug report."""
        assert _match_patterns("Prepare handoff for the next Section in a new agent.", HANDOFF_PATTERNS)

    def test_do_a_handoff(self):
        assert _match_patterns("do a handoff", HANDOFF_PATTERNS)

    def test_please_handoff(self):
        assert _match_patterns("please handoff", HANDOFF_PATTERNS)

    def test_start_handoff(self):
        assert _match_patterns("start handoff", HANDOFF_PATTERNS)

    def test_initiate_handoff(self):
        assert _match_patterns("initiate handoff", HANDOFF_PATTERNS)

    def test_begin_a_handoff(self):
        assert _match_patterns("begin a handoff", HANDOFF_PATTERNS)

    def test_trigger_handoff(self):
        assert _match_patterns("trigger handoff", HANDOFF_PATTERNS)

    def test_run_handoff(self):
        assert _match_patterns("run handoff", HANDOFF_PATTERNS)

    def test_kick_off_handoff(self):
        assert _match_patterns("kick off handoff", HANDOFF_PATTERNS)

    def test_please_start_a_handoff(self):
        assert _match_patterns("please start a handoff", HANDOFF_PATTERNS)

    def test_hand_off_to_successor(self):
        assert _match_patterns("hand off to the next agent", HANDOFF_PATTERNS)

    def test_handoff_for_next_section(self):
        assert _match_patterns("handoff for the next section", HANDOFF_PATTERNS)

    def test_case_insensitive(self):
        assert _match_patterns("HANDOFF", HANDOFF_PATTERNS)
        assert _match_patterns("Handoff", HANDOFF_PATTERNS)
        assert _match_patterns("PREPARE HANDOFF", HANDOFF_PATTERNS)

    # ── Negative: should NOT match ────────────────────────────────────

    def test_no_match_normal_command(self):
        assert not _match_patterns("fix the login bug", HANDOFF_PATTERNS)

    def test_no_match_question_about_code(self):
        assert not _match_patterns("what does this function do?", HANDOFF_PATTERNS)


class TestHandoffNegativePatterns:
    """Tests for HANDOFF_NEGATIVE_PATTERNS — vetoes false positives."""

    def test_check_handoff_code(self):
        assert _match_patterns("check the handoff executor code", HANDOFF_NEGATIVE_PATTERNS)

    def test_review_handoff_service(self):
        assert _match_patterns("review the handoff service", HANDOFF_NEGATIVE_PATTERNS)

    def test_fix_handoff_bug(self):
        assert _match_patterns("fix handoff bug", HANDOFF_NEGATIVE_PATTERNS)

    def test_debug_handoff_executor(self):
        assert _match_patterns("debug the handoff executor", HANDOFF_NEGATIVE_PATTERNS)

    def test_handoff_test(self):
        assert _match_patterns("run the handoff test", HANDOFF_NEGATIVE_PATTERNS)

    def test_look_at_handoff_log(self):
        assert _match_patterns("look at the handoff log", HANDOFF_NEGATIVE_PATTERNS)

    def test_does_not_veto_real_handoff(self):
        """A real handoff request should NOT match negative patterns."""
        assert not _match_patterns("prepare handoff for the next section", HANDOFF_NEGATIVE_PATTERNS)

    def test_does_not_veto_bare_handoff(self):
        assert not _match_patterns("handoff", HANDOFF_NEGATIVE_PATTERNS)


class TestDetectHandoffIntent:
    """Tests for the detect_handoff_intent function."""

    # ── Bug report reproduction ───────────────────────────────────────

    def test_exact_bug_report_message(self):
        """The exact message from the bug report that was missed."""
        is_handoff, context = detect_handoff_intent(
            "Prepare handoff for the next Section in a new agent."
        )
        assert is_handoff is True
        assert context == "for the next Section in a new agent"

    # ── Positive detections ───────────────────────────────────────────

    def test_bare_handoff(self):
        is_handoff, context = detect_handoff_intent("handoff")
        assert is_handoff is True
        assert context is None

    def test_do_a_handoff(self):
        is_handoff, context = detect_handoff_intent("do a handoff")
        assert is_handoff is True

    def test_please_handoff(self):
        is_handoff, context = detect_handoff_intent("please handoff")
        assert is_handoff is True

    def test_handoff_with_context(self):
        is_handoff, context = detect_handoff_intent("handoff to continue the workshop")
        assert is_handoff is True
        assert context == "to continue the workshop"

    def test_start_handoff_with_context(self):
        is_handoff, context = detect_handoff_intent("start handoff for the next epic")
        assert is_handoff is True
        assert context == "for the next epic"

    def test_prepare_a_handoff(self):
        is_handoff, context = detect_handoff_intent("prepare a handoff")
        assert is_handoff is True

    # ── Negative detections (not handoff) ─────────────────────────────

    def test_normal_command(self):
        is_handoff, context = detect_handoff_intent("fix the login bug")
        assert is_handoff is False
        assert context is None

    def test_empty_text(self):
        is_handoff, context = detect_handoff_intent("")
        assert is_handoff is False

    def test_none_text(self):
        is_handoff, context = detect_handoff_intent(None)
        assert is_handoff is False

    def test_short_text(self):
        is_handoff, context = detect_handoff_intent("hi")
        assert is_handoff is False

    def test_check_handoff_code_vetoed(self):
        """Negative guard should veto: user is discussing handoff, not requesting."""
        is_handoff, context = detect_handoff_intent("check the handoff executor code")
        assert is_handoff is False

    def test_fix_handoff_bug_vetoed(self):
        is_handoff, context = detect_handoff_intent("fix the handoff bug in hook_receiver.py")
        assert is_handoff is False

    def test_review_handoff_service_vetoed(self):
        is_handoff, context = detect_handoff_intent("review the handoff service")
        assert is_handoff is False

    def test_investigate_handoff_error_vetoed(self):
        is_handoff, context = detect_handoff_intent("investigate the handoff error")
        assert is_handoff is False

    # ── LLM fallback ─────────────────────────────────────────────────

    def test_llm_fallback_when_regex_misses(self):
        """When regex doesn't match but message contains 'handoff' and
        LLM classifies as handoff, should return True."""
        mock_inference = MagicMock()
        mock_inference.is_available = True
        mock_inference.infer.return_value = MagicMock(text="A")

        is_handoff, context = detect_handoff_intent(
            "I think we should handoff this work now",
            inference_service=mock_inference,
        )
        assert is_handoff is True

    def test_llm_fallback_rejects_non_handoff(self):
        """LLM classifies as COMMAND (B) — not a handoff."""
        mock_inference = MagicMock()
        mock_inference.is_available = True
        mock_inference.infer.return_value = MagicMock(text="B")

        is_handoff, context = detect_handoff_intent(
            "the handoff process worked well last time",
            inference_service=mock_inference,
        )
        assert is_handoff is False

    def test_no_llm_without_handoff_keyword(self):
        """LLM should not be called if message doesn't contain 'handoff'."""
        mock_inference = MagicMock()
        mock_inference.is_available = True

        is_handoff, context = detect_handoff_intent(
            "fix the login bug",
            inference_service=mock_inference,
        )
        assert is_handoff is False
        mock_inference.infer.assert_not_called()
