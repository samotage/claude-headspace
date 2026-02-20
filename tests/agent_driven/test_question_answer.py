"""Agent-driven integration test: question/answer flow with AskUserQuestion.

Sends a command that triggers Claude Code to use AskUserQuestion (structured
question with options), verifies the AWAITING_INPUT state, option rendering,
user selection via tmux, and completion. Includes cross-layer verification
(DOM vs API vs DB consistency) and timestamp ordering checks.

Every layer is real. Nothing is mocked.
"""

import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.agent_driven.helpers.cross_layer import verify_cross_layer_consistency
from tests.agent_driven.helpers.output import scenario_header, scenario_footer, step
from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms -- generous timeout for real LLM processing


# ---------------------------------------------------------------------------
# Test: Question/Answer Flow (FR9)
# ---------------------------------------------------------------------------

@pytest.mark.agent_driven
def test_question_answer_flow(claude_session, page, e2e_server, e2e_app):
    """AskUserQuestion flow with cross-layer verification.

    Exercises the AWAITING_INPUT state path through the full stack:
    1. Navigate to voice chat and select the agent.
    2. Send a prompt that instructs Claude to use AskUserQuestion.
    3. Wait for the question bubble to appear (proves AWAITING_INPUT state).
    4. Verify option text is visible in the question bubble.
    5. Select an option via tmux send-keys (Enter).
    6. Wait for the response bubble (proves COMPLETE state).
    7. Verify AWAITING_INPUT was reached in the database.
    8. Verify command reaches COMPLETE state.
    9. Run cross-layer verification (DOM vs API vs DB consistency).
    10. Verify timestamp ordering.
    11. Capture screenshots at each stage.
    """
    start = scenario_header("Question/Answer Flow (AskUserQuestion)")
    agent_id = claude_session["agent_id"]
    session_name = claude_session["session_name"]

    va = VoiceAssertions(page, SCREENSHOT_DIR)

    # --- 1. Navigate to voice chat ---
    with step("Navigate to voice chat", num=1, total=10):
        va.navigate_to_voice(e2e_server)
        va.capture("qa_01_voice_loaded")

    # --- 2. Wait for agent card and select it ---
    with step("Select agent card", num=2, total=10):
        va.assert_agent_card_visible(agent_id, timeout=15_000)
        va.capture("qa_02_agent_card_visible")
        va.select_agent(agent_id)
        va.assert_chat_screen_active()
        va.capture("qa_03_chat_ready")

    # --- 3. Send prompt that triggers AskUserQuestion ---
    with step("Send AskUserQuestion prompt", num=3, total=10):
        prompt = (
            "I would like you to tell me the current time. "
            "But before you tell me, you MUST use the AskUserQuestion tool to ask me "
            "what format I would like the time in. Offer exactly two options: "
            '"12-hour" (description: "e.g. 3:45 PM") and '
            '"24-hour" (description: "e.g. 15:45"). '
            "Wait for my selection, then tell me the time in that format."
        )
        va.send_chat_message(prompt)
        va.capture("qa_04_command_sent")

    # --- 4. Wait for question bubble (first agent turn) ---
    with step("Wait for question bubble", num=4, total=10):
        agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
        expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
        va.capture("qa_05_question_visible")

    # --- 5. Verify option text in the question bubble ---
    with step("Verify option text in question bubble", num=5, total=10):
        question_text = agent_bubbles.first.inner_text()
        assert "12-hour" in question_text.lower() or "24-hour" in question_text.lower(), (
            f"Expected AskUserQuestion with time format options: {question_text!r}"
        )

    # --- 6. Verify AWAITING_INPUT state reached in database ---
    with step("Verify AWAITING_INPUT state in database", num=6, total=10):
        from claude_headspace.database import db
        from claude_headspace.models.command import Command, CommandState

        with e2e_app.app_context():
            command = (
                db.session.query(Command)
                .filter_by(agent_id=agent_id)
                .order_by(Command.id.desc())
                .first()
            )
            assert command is not None, "No Command record found in database"
            assert command.state == CommandState.AWAITING_INPUT, (
                f"Expected AWAITING_INPUT state, got {command.state.value}"
            )
        va.capture("qa_06_awaiting_input_verified")

    # --- 7. Select the first option via tmux Enter ---
    with step("Select option via tmux Enter", num=7, total=10):
        time.sleep(1)  # Let terminal UI settle
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            check=True, timeout=5,
        )
        va.capture("qa_07_option_selected")

    # --- 8. Wait for response bubble after option selection ---
    with step("Wait for response bubble after selection", num=8, total=10):
        expect(agent_bubbles.nth(1)).to_be_visible(timeout=RESPONSE_TIMEOUT)
        va.capture("qa_08_response_visible")

    # --- 9. Verify command reaches COMPLETE state ---
    with step("Verify COMPLETE state in database", num=9, total=10):
        deadline = time.time() + 30
        with e2e_app.app_context():
            while time.time() < deadline:
                db.session.expire_all()
                command = (
                    db.session.query(Command)
                    .filter_by(agent_id=agent_id)
                    .order_by(Command.id.desc())
                    .first()
                )
                assert command is not None, "No Command record found after response"
                if command.state == CommandState.COMPLETE:
                    break
                time.sleep(1)
            else:
                assert command.state == CommandState.COMPLETE, (
                    f"Expected COMPLETE state, got {command.state.value}"
                )
        va.capture("qa_09_complete_verified")

    # --- 10. Cross-layer verification (FR11, FR12, FR13) ---
    with step("Cross-layer verification (DOM/API/DB)", num=10, total=10):
        time.sleep(2)
        result = verify_cross_layer_consistency(page, agent_id, e2e_server, e2e_app)
        assert result["dom_turn_count"] >= 2, (
            f"Expected at least 2 DOM turns, got {result['dom_turn_count']}"
        )
        assert result["api_turn_count"] >= 2, (
            f"Expected at least 2 API turns, got {result['api_turn_count']}"
        )
        va.capture("qa_10_cross_layer_verified")

    va.capture("qa_11_test_complete")
    scenario_footer("Question/Answer Flow (AskUserQuestion)", start)
