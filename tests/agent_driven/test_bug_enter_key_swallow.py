"""Agent-driven integration test: Enter-key swallowing regression (FR17).

Bug reference: commit e48f1ef ("fix: prevent Enter-key swallowing and skill
expansion backflush in voice chat")

The bug: When sending commands via the voice chat tmux bridge, terminal
autocomplete could swallow the Enter keystroke on slash commands or long
text, leaving commands sitting in the tmux input box without being submitted
to Claude Code. The fix was to always use verify_enter=True in the tmux
bridge so that after typing text, the bridge confirms the Enter key was
actually received by checking that the pane content changed.

This bug was caught by manual testing but passed all existing mock-based
unit tests because the mocks did not exercise the actual tmux pane
interaction where autocomplete swallows Enter.

This test exercises the specific code path by sending a long command via
the voice chat UI and verifying that it actually gets submitted and
produces a response, rather than silently sitting in the input box.

Every layer is real. Nothing is mocked.
"""

import time
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from tests.agent_driven.helpers.output import scenario_header, scenario_footer, step
from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms -- generous timeout for real LLM processing


# ---------------------------------------------------------------------------
# Test: Enter-Key Swallowing Regression (FR17 / bug e48f1ef)
# ---------------------------------------------------------------------------

@pytest.mark.agent_driven
def test_long_command_not_swallowed(claude_session, page, e2e_server, e2e_app):
    """Long command submission does not get swallowed by terminal autocomplete.

    Bug: e48f1ef -- Enter-key swallowing in voice chat tmux bridge.

    The original bug caused long text or slash commands sent via the voice
    chat to sit in the tmux input line without being submitted, because
    terminal autocomplete consumed the Enter keystroke.

    This test would have caught the bug by:
    1. Sending a deliberately long command through the voice chat UI.
    2. Waiting for the agent to actually respond (response proves the
       command was submitted, not swallowed).
    3. Verifying the command reaches COMPLETE state in the database
       (proves the full round-trip through tmux worked).
    4. Checking that exactly 1 user bubble exists (no backflush).

    If Enter were swallowed, the test would timeout waiting for a response
    bubble, exactly as the bug manifested in manual testing.
    """
    start = scenario_header("Bug Regression: Enter-Key Swallow (e48f1ef)")
    agent_id = claude_session["agent_id"]

    va = VoiceAssertions(page, SCREENSHOT_DIR)

    # --- 1. Navigate to voice chat ---
    with step("Navigate to voice chat", num=1, total=6):
        va.navigate_to_voice(e2e_server)
        va.capture("enterkey_01_voice_loaded")

    # --- 2. Select agent ---
    with step("Select agent card", num=2, total=6):
        va.assert_agent_card_visible(agent_id, timeout=15_000)
        va.select_agent(agent_id)
        va.assert_chat_screen_active()
        va.capture("enterkey_02_chat_ready")

    # --- 3. Send a deliberately long command ---
    # Long text triggers the autocomplete behavior in the terminal that
    # originally caused Enter to be swallowed. The marker ensures we can
    # identify this specific command's response.
    with step("Send long command (triggers autocomplete path)", num=3, total=6):
        marker = f"ENTER_{uuid4().hex[:8]}"
        # A sufficiently long command that exercises the text entry path
        # where autocomplete could interfere with Enter delivery.
        prompt = (
            f"Please calculate the following and include the marker '{marker}' "
            f"in your response: What is the sum of 123 plus 456 plus 789? "
            f"Give me just the number and the marker, nothing else."
        )
        va.send_chat_message(prompt)
        va.capture("enterkey_03_command_sent")

    # --- 4. Wait for agent response (proves Enter was delivered) ---
    # This is the critical assertion: if Enter were swallowed, this would
    # timeout because the command never reaches Claude Code.
    with step("Wait for response (proves Enter delivered)", num=4, total=6):
        agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
        expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
        va.capture("enterkey_04_response_visible")

    # --- 5. Verify command reaches COMPLETE state in DB ---
    with step("Verify COMPLETE state in database", num=5, total=6):
        from claude_headspace.database import db
        from claude_headspace.models.command import Command, CommandState

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
                if command and command.state == CommandState.COMPLETE:
                    break
                time.sleep(1)

            db.session.expire_all()
            command = (
                db.session.query(Command)
                .filter_by(agent_id=agent_id)
                .order_by(Command.id.desc())
                .first()
            )
            assert command is not None, "No Command record found"
            assert command.state == CommandState.COMPLETE, (
                f"Expected COMPLETE state, got {command.state.value}"
            )
        va.capture("enterkey_05_complete_verified")

    # --- 6. Verify no command backflush (exactly 1 user bubble) ---
    with step("Verify no command backflush (1 user bubble)", num=6, total=6):
        # Wait for any delayed SSE events to settle
        time.sleep(3)
        user_bubbles = page.locator(".chat-bubble.user")
        user_count = user_bubbles.count()
        assert user_count == 1, (
            f"Expected exactly 1 user bubble, got {user_count}. "
            f"Command text may have been backflushed. "
            f"Texts: {[user_bubbles.nth(i).inner_text()[:80] for i in range(user_count)]}"
        )
        va.capture("enterkey_06_no_backflush")

    va.capture("enterkey_07_test_complete")
    scenario_footer("Bug Regression: Enter-Key Swallow (e48f1ef)", start)
