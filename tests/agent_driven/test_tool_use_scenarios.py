"""Agent-driven integration tests: tool use and command backflush detection.

Tests that verify Claude Code tool usage flows through the full production
loop correctly, and that the original command text does not "backflush"
into the voice chat as a duplicate user bubble.

Every layer is real. Nothing is mocked.
"""

import time
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms — generous timeout for real LLM processing


@pytest.mark.agent_driven
def test_tool_use_bash_echo(claude_session, page, e2e_server, e2e_app):
    """Verify Claude uses the Bash tool and the output flows through correctly.

    Exercises the full tool-use hook chain:
    - pre_tool_use hook fires (Bash tool detected)
    - post_tool_use hook fires (tool result captured)
    - Agent response contains the tool output

    Flow:
    1. Send a command asking Claude to run `echo <unique_marker>`
    2. Wait for agent response bubble
    3. Assert the unique marker appears in the response
    4. Verify no command backflush (exactly 1 user bubble)
    """
    agent_id = claude_session["agent_id"]
    marker = f"HSVFY_{uuid4().hex[:8]}"

    # --- Setup voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("tool_01_chat_ready")

    # --- Send command that requires Bash tool use ---
    va.send_chat_message(
        f"Please run this exact bash command and tell me what it outputs: "
        f"echo {marker}"
    )
    va.capture("tool_02_command_sent")

    # --- Wait for agent response ---
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("tool_03_response_visible")

    # --- Verify the response contains the tool output ---
    response_text = agent_bubbles.first.inner_text()
    assert marker in response_text, (
        f"Expected Bash tool output '{marker}' in response: {response_text!r}"
    )

    # --- Backflush check: wait for any delayed SSE events ---
    time.sleep(3)
    va.capture("tool_04_after_settle")

    # Count user bubbles — should be exactly 1 (the command we sent)
    user_bubbles = page.locator(".chat-bubble.user")
    user_count = user_bubbles.count()
    assert user_count == 1, (
        f"Expected exactly 1 user bubble, got {user_count} "
        f"(command text may have been backflushed). "
        f"Texts: {[user_bubbles.nth(i).inner_text() for i in range(user_count)]}"
    )

    va.capture("tool_05_complete")


@pytest.mark.agent_driven
def test_no_command_backflush(claude_session, page, e2e_server, e2e_app):
    """Verify the original command text doesn't appear as a duplicate user bubble.

    After sending a command and receiving a response, the voice chat should
    show exactly 1 user bubble (the optimistic render). The system must NOT
    "backflush" the raw command text from the tmux session back into the
    chat as an additional user bubble.

    This tests the SSE turn_created promotion logic: when the server
    broadcasts a USER turn via SSE, the frontend should promote the
    existing optimistic bubble rather than rendering a duplicate.

    Flow:
    1. Send a simple command with a unique marker
    2. Wait for agent response
    3. Wait extra time for any delayed SSE events (transcript reconciler, etc.)
    4. Assert exactly 1 user bubble exists
    5. Assert the user bubble text matches what was sent
    6. Assert no duplicate user bubbles with the same content
    """
    agent_id = claude_session["agent_id"]
    marker = f"BF_{uuid4().hex[:8]}"
    command_text = f"What is the square root of 144? Include '{marker}' in your answer."

    # --- Setup voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("backflush_01_chat_ready")

    # --- Send the command ---
    va.send_chat_message(command_text)
    va.capture("backflush_02_command_sent")

    # --- Verify optimistic user bubble rendered immediately ---
    user_bubbles = page.locator(".chat-bubble.user")
    expect(user_bubbles.first).to_be_visible(timeout=5_000)

    # --- Wait for agent response ---
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("backflush_03_response_visible")

    # Verify the agent actually answered
    response_text = agent_bubbles.first.inner_text()
    assert "12" in response_text, (
        f"Expected '12' (sqrt of 144) in response: {response_text!r}"
    )

    # --- Wait for any delayed SSE events to settle ---
    # The transcript reconciler, deferred stop, and other async processes
    # may broadcast additional turn_created events after the response.
    time.sleep(5)
    va.capture("backflush_04_after_settle")

    # --- BACKFLUSH ASSERTIONS ---

    # 1. Exactly 1 user bubble should exist
    user_count = user_bubbles.count()
    assert user_count == 1, (
        f"BACKFLUSH DETECTED: Expected exactly 1 user bubble, got {user_count}. "
        f"The command text may have been duplicated by SSE turn_created events. "
        f"User bubble texts: {[user_bubbles.nth(i).inner_text() for i in range(user_count)]}"
    )

    # 2. The single user bubble should contain the original command text
    user_text = user_bubbles.first.inner_text()
    assert marker in user_text, (
        f"User bubble text doesn't match sent command. "
        f"Expected marker '{marker}' in: {user_text!r}"
    )

    # 3. Exactly 1 agent bubble should exist (no duplicate responses)
    agent_count = agent_bubbles.count()
    assert agent_count == 1, (
        f"Expected exactly 1 agent bubble, got {agent_count}. "
        f"Agent bubble texts: {[agent_bubbles.nth(i).inner_text()[:80] for i in range(agent_count)]}"
    )

    va.capture("backflush_05_complete")
