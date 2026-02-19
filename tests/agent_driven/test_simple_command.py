"""Agent-driven integration test: simple command round-trip.

Sends a command to a real Claude Code session via the voice chat UI
(Playwright), waits for the agent response bubble to appear in the DOM,
and verifies command state transitions in the database.

Every layer is real. Nothing is mocked.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms — generous timeout for real LLM processing


@pytest.mark.agent_driven
def test_simple_command_roundtrip(claude_session, page, e2e_server, e2e_app):
    """Voice chat → Claude Code → hooks → SSE → browser round-trip.

    1. Navigate Playwright to voice chat on the test server.
    2. Select the agent card for the launched Claude Code session.
    3. Send a deterministic command via the chat input.
    4. Wait for an agent response bubble in the DOM.
    5. Verify command state transitions in the database.
    """
    agent_id = claude_session["agent_id"]

    # --- 1. Navigate to voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.capture("01_voice_loaded")

    # --- 2. Wait for agent card and select it ---
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.capture("02_agent_card_visible")

    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("03_chat_screen_active")

    # --- 3. Send a deterministic command ---
    test_id = uuid4().hex[:8]
    prompt = (
        f"Create a file called /tmp/headspace_test_{test_id}.txt "
        f"with the content 'hello'"
    )
    va.send_chat_message(prompt)
    va.capture("04_command_sent")

    # --- 4. Wait for agent response bubble ---
    # Agent bubbles have class "chat-bubble agent" with data-turn-id attribute.
    agent_bubble = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubble.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("05_agent_response_visible")

    # --- 5. Verify command state transitions in DB ---
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
        assert command.state in (CommandState.COMPLETE, CommandState.AWAITING_INPUT), (
            f"Expected command state COMPLETE or AWAITING_INPUT, "
            f"got {command.state}"
        )

    va.capture("06_test_complete")
