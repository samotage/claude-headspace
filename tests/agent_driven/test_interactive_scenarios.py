"""Agent-driven integration tests: dad joke and time format scenarios.

Tests multi-step interactions including AskUserQuestion tool usage.
Every layer is real. Nothing is mocked.
"""

import re
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms — generous timeout for real LLM processing


@pytest.mark.agent_driven
def test_dad_joke(claude_session, page, e2e_server, e2e_app):
    """Send 'tell me a Dad Joke' and verify a joke is returned.

    1. Navigate Playwright to voice chat.
    2. Select the agent card for the launched Claude Code session.
    3. Send the dad joke request via chat input.
    4. Wait for an agent response bubble.
    5. Verify the response contains joke-length text.
    """
    agent_id = claude_session["agent_id"]

    # --- 1. Navigate to voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)

    # --- 2. Wait for agent card and select it ---
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("dad_joke_01_chat_ready")

    # --- 3. Send the dad joke request ---
    va.send_chat_message("I would like you to tell me a Dad Joke")
    va.capture("dad_joke_02_command_sent")

    # --- 4. Wait for agent response bubble ---
    agent_bubble = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubble.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("dad_joke_03_response_visible")

    # --- 5. Verify the response contains a joke ---
    response_text = agent_bubble.first.inner_text()
    assert len(response_text) > 20, (
        f"Expected a dad joke but got a short response: {response_text!r}"
    )

    va.capture("dad_joke_04_complete")


@pytest.mark.agent_driven
def test_time_with_format_selection(claude_session, page, e2e_server, e2e_app):
    """Ask for the time via AskUserQuestion format selection.

    Multi-step interaction:
    1. Navigate Playwright to voice chat and select the agent.
    2. Send a command that instructs Claude to use AskUserQuestion.
    3. Wait for the AskUserQuestion bubble to appear in the DOM
       (proves Claude used the tool — the pre_tool_use hook creates
       an AGENT turn with the question content).
    4. Send Enter via tmux to select the first option (12-hour).
    5. Wait for a SECOND agent bubble (the actual time response).
    6. Verify the second bubble contains a 12-hour formatted time.
    """
    agent_id = claude_session["agent_id"]
    session_name = claude_session["session_name"]

    # --- 1. Navigate to voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("time_01_chat_ready")

    # --- 2. Send the time request with AskUserQuestion instruction ---
    prompt = (
        "I would like you to tell me the current time. "
        "But before you tell me, you MUST use the AskUserQuestion tool to ask me "
        "what format I would like the time in. Offer exactly two options: "
        '"12-hour" (description: "e.g. 3:45 PM") and '
        '"24-hour" (description: "e.g. 15:45"). '
        "Wait for my selection, then tell me the time in that format."
    )
    va.send_chat_message(prompt)
    va.capture("time_02_command_sent")

    # --- 3. Wait for AskUserQuestion bubble (first agent turn) ---
    # When Claude uses AskUserQuestion, the pre_tool_use hook fires,
    # state transitions to AWAITING_INPUT, and a question Turn is
    # created. This appears as an agent bubble in the voice chat.
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)

    # Verify the bubble contains format options (proves AskUserQuestion was used)
    question_text = agent_bubbles.first.inner_text()
    assert "12-hour" in question_text.lower() or "24-hour" in question_text.lower(), (
        f"Expected AskUserQuestion with time format options: {question_text!r}"
    )
    va.capture("time_03_question_visible")

    # --- 4. Select the first option (12-hour) via tmux ---
    # The AskUserQuestion UI is already rendered in the terminal
    # by the time the bubble appears. Small delay to let it settle.
    time.sleep(1)
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "Enter"],
        check=True, timeout=5,
    )
    va.capture("time_04_selection_made")

    # --- 5. Wait for an agent bubble containing a 12-hour time ---
    # After the selection, Claude processes and responds with the time.
    # PROGRESS turns may insert intermediate bubbles (e.g. "WORKING..."),
    # so we wait for ANY agent bubble matching the time pattern rather
    # than assuming a fixed bubble index.
    time_pattern = re.compile(r'\d{1,2}:\d{2}\s*[AaPp]\.?[Mm]\.?')
    time_bubble = agent_bubbles.filter(has_text=time_pattern)
    expect(time_bubble.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("time_05_response_visible")

    # --- 6. Verify 12-hour time format ---
    response_text = time_bubble.first.inner_text()
    has_12hr = bool(time_pattern.search(response_text))
    assert has_12hr, (
        f"Expected 12-hour time format (e.g. 3:45 PM) in response: {response_text!r}"
    )

    va.capture("time_06_complete")
