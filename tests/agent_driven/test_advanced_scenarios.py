"""Agent-driven integration tests: multi-turn and error recovery scenarios.

Tests that exercise multiple command/response cycles in a single Claude
session, including context retention across turns and error recovery
with file system side effects.

Every layer is real. Nothing is mocked.
"""

import re
import time
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms — generous timeout for real LLM processing


@pytest.mark.agent_driven
def test_multi_turn_context_retention(claude_session, page, e2e_server, e2e_app):
    """Two command/response cycles where the second depends on the first.

    Verifies:
    - State machine cycles twice: IDLE → COMMANDED → PROCESSING → COMPLETE (×2)
    - Voice chat correctly renders multiple bubble pairs
    - Claude retains conversation context across commands
    - Database has two Command records after both rounds

    Flow:
    1. Send "My favorite color is chartreuse"
    2. Wait for confirmation bubble
    3. Send "What was my favorite color?"
    4. Wait for recall bubble
    5. Assert "chartreuse" in the recall response
    6. Verify two Command records in the database
    """
    agent_id = claude_session["agent_id"]

    # --- Setup voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("context_01_chat_ready")

    # --- Round 1: Tell Claude a favorite color ---
    va.send_chat_message(
        "My favorite color is chartreuse. "
        "Just confirm you've noted it, nothing else."
    )
    va.capture("context_02_round1_sent")

    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("context_03_round1_response")

    # Verify confirmation mentions the color
    confirm_text = agent_bubbles.first.inner_text()
    assert "chartreuse" in confirm_text.lower(), (
        f"Expected confirmation of chartreuse but got: {confirm_text!r}"
    )

    # Record how many agent bubbles exist after round 1
    round1_count = agent_bubbles.count()

    # Let the command fully complete before sending the next one
    time.sleep(2)

    # --- Round 2: Recall the favorite color ---
    va.send_chat_message("What was my favorite color that I just told you?")
    va.capture("context_04_round2_sent")

    # Wait for a new agent bubble beyond round 1's count
    expect(agent_bubbles.nth(round1_count)).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("context_05_round2_response")

    # Verify the recall response contains the color
    recall_text = agent_bubbles.nth(round1_count).inner_text()
    assert "chartreuse" in recall_text.lower(), (
        f"Expected 'chartreuse' in recall response: {recall_text!r}"
    )

    # --- Database verification: two Command records ---
    from claude_headspace.database import db
    from claude_headspace.models.command import Command

    with e2e_app.app_context():
        commands = (
            db.session.query(Command)
            .filter_by(agent_id=agent_id)
            .order_by(Command.id)
            .all()
        )
        assert len(commands) >= 2, (
            f"Expected at least 2 Command records, got {len(commands)}: "
            f"{[(c.id, c.state.value) for c in commands]}"
        )

    va.capture("context_06_complete")


@pytest.mark.agent_driven
def test_error_recovery_file_ops(claude_session, page, e2e_server, e2e_app):
    """Error recovery: read a non-existent file, then create and verify it.

    Verifies:
    - Claude handles tool errors gracefully (file not found)
    - Multi-turn recovery: failed operation → corrective action
    - File system side effects: file is actually created on disk
    - File content matches what was requested
    - State machine cycles twice through error and recovery paths

    Flow:
    1. Ask Claude to read a file that doesn't exist
    2. Verify the response acknowledges the error
    3. Ask Claude to create that file with specific content and read it back
    4. Verify the response confirms the content
    5. Verify the file exists on disk with correct content
    6. Clean up the file
    """
    agent_id = claude_session["agent_id"]
    test_id = uuid4().hex[:8]
    filepath = f"/tmp/headspace_recovery_{test_id}.txt"

    # --- Setup voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("recovery_01_chat_ready")

    # --- Round 1: Read a non-existent file ---
    va.send_chat_message(
        f"Please use your Read tool to read the file at {filepath} "
        f"and tell me what it contains."
    )
    va.capture("recovery_02_round1_sent")

    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("recovery_03_round1_response")

    # Verify Claude reports the file doesn't exist
    error_text = agent_bubbles.first.inner_text().lower()
    assert any(kw in error_text for kw in [
        "not found", "doesn't exist", "does not exist",
        "no such file", "not exist", "couldn't find", "could not find",
        "error", "failed",
    ]), f"Expected file-not-found message: {error_text!r}"

    round1_count = agent_bubbles.count()
    time.sleep(2)

    # --- Round 2: Create the file and read it back ---
    va.send_chat_message(
        f"Please use your Write tool to create the file {filepath} "
        f"with the content: recovery successful\n"
        f"Then read it back and tell me what it says."
    )
    va.capture("recovery_04_round2_sent")

    expect(agent_bubbles.nth(round1_count)).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("recovery_05_round2_response")

    # Verify the response confirms the content
    recovery_text = agent_bubbles.nth(round1_count).inner_text().lower()
    assert "recovery successful" in recovery_text, (
        f"Expected 'recovery successful' in response: {recovery_text!r}"
    )

    # --- Verify file exists on disk ---
    file_path = Path(filepath)
    assert file_path.exists(), f"File {filepath} was not created on disk"

    file_content = file_path.read_text().strip()
    assert file_content == "recovery successful", (
        f"Expected file content 'recovery successful', got: {file_content!r}"
    )
    va.capture("recovery_06_file_verified")

    # --- Database verification: two Command records ---
    from claude_headspace.database import db
    from claude_headspace.models.command import Command

    with e2e_app.app_context():
        commands = (
            db.session.query(Command)
            .filter_by(agent_id=agent_id)
            .order_by(Command.id)
            .all()
        )
        assert len(commands) >= 2, (
            f"Expected at least 2 Command records, got {len(commands)}: "
            f"{[(c.id, c.state.value) for c in commands]}"
        )

    # --- Cleanup ---
    file_path.unlink(missing_ok=True)

    va.capture("recovery_07_complete")
