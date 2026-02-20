"""Agent-driven integration test: multi-turn conversation with cross-layer verification.

Sends two sequential commands via the voice chat UI, waits for both to complete,
and verifies correct turn counts, bubble ordering, command separators, and
cross-layer consistency (DOM vs API vs DB). Includes timestamp ordering checks.

Every layer is real. Nothing is mocked.
"""

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
# Test: Multi-Turn Conversation (FR10)
# ---------------------------------------------------------------------------

@pytest.mark.agent_driven
def test_multi_turn_with_cross_layer_verification(
    claude_session, page, e2e_server, e2e_app
):
    """Two sequential command/response cycles with cross-layer verification.

    Exercises the full multi-turn flow:
    1. Navigate to voice chat and select the agent.
    2. Send first command ("tell me a short joke"), wait for response.
    3. Send second command ("tell me another joke"), wait for response.
    4. Verify both commands reach COMPLETE state in DB.
    5. Verify correct number of user and agent turns in DB.
    6. Verify all bubbles rendered in correct order in DOM.
    7. Verify command separator visible between command groups.
    8. Run cross-layer verification (DOM vs API vs DB consistency).
    9. Verify timestamp ordering.
    10. Capture screenshots at each stage.
    """
    start = scenario_header("Multi-Turn Conversation")
    agent_id = claude_session["agent_id"]

    va = VoiceAssertions(page, SCREENSHOT_DIR)

    # --- 1. Navigate to voice chat ---
    with step("Navigate to voice chat", num=1, total=10):
        va.navigate_to_voice(e2e_server)
        va.capture("mt_01_voice_loaded")

    # --- 2. Wait for agent card and select it ---
    with step("Select agent card", num=2, total=10):
        va.assert_agent_card_visible(agent_id, timeout=15_000)
        va.capture("mt_02_agent_card_visible")
        va.select_agent(agent_id)
        va.assert_chat_screen_active()
        va.capture("mt_03_chat_ready")

    # --- 3. Send first command ---
    with step("Send first command (joke 1)", num=3, total=10):
        va.send_chat_message(
            "Tell me a short one-liner joke. Keep your response to one sentence."
        )
        va.capture("mt_04_command1_sent")

    # --- 4. Wait for first response ---
    with step("Wait for first response bubble", num=4, total=10):
        agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
        expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
        va.capture("mt_05_command1_response")
        round1_bubble_count = agent_bubbles.count()

    # --- 5. Wait for first command to fully complete ---
    with step("Poll for first command COMPLETE state", num=5, total=10):
        from claude_headspace.database import db
        from claude_headspace.models.command import Command, CommandState

        deadline = time.time() + 30
        with e2e_app.app_context():
            while time.time() < deadline:
                db.session.expire_all()
                cmd = (
                    db.session.query(Command)
                    .filter_by(agent_id=agent_id)
                    .order_by(Command.id.desc())
                    .first()
                )
                if cmd and cmd.state == CommandState.COMPLETE:
                    break
                time.sleep(1)
        time.sleep(2)

    # --- 6. Send second command and wait for response ---
    with step("Send second command (joke 2) and wait", num=6, total=10):
        va.send_chat_message(
            "Now tell me a different short one-liner joke. Keep your response to one sentence."
        )
        va.capture("mt_06_command2_sent")
        expect(agent_bubbles.nth(round1_bubble_count)).to_be_visible(
            timeout=RESPONSE_TIMEOUT
        )
        va.capture("mt_07_command2_response")

    # --- 7. Verify both commands reach COMPLETE in DB ---
    with step("Verify both commands COMPLETE in database", num=7, total=10):
        deadline = time.time() + 30
        with e2e_app.app_context():
            while time.time() < deadline:
                db.session.expire_all()
                commands = (
                    db.session.query(Command)
                    .filter_by(agent_id=agent_id)
                    .order_by(Command.id)
                    .all()
                )
                if len(commands) >= 2 and all(
                    c.state == CommandState.COMPLETE for c in commands
                ):
                    break
                time.sleep(1)

            db.session.expire_all()
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
            for cmd in commands:
                assert cmd.state == CommandState.COMPLETE, (
                    f"Command {cmd.id} not COMPLETE: {cmd.state.value}"
                )
        va.capture("mt_08_both_commands_complete")

    # --- 8. Verify correct number of user and agent turns in DB ---
    with step("Verify turn counts in database", num=8, total=10):
        from claude_headspace.models.turn import Turn, TurnActor

        with e2e_app.app_context():
            db.session.expire_all()
            turns = (
                db.session.query(Turn)
                .join(Command, Turn.command_id == Command.id)
                .filter(Command.agent_id == agent_id)
                .filter(Turn.is_internal == False)  # noqa: E712
                .order_by(Turn.timestamp.asc())
                .all()
            )
            user_turns = [t for t in turns if t.actor == TurnActor.USER]
            agent_turns = [t for t in turns if t.actor == TurnActor.AGENT]

            assert len(user_turns) >= 2, (
                f"Expected at least 2 user turns, got {len(user_turns)}"
            )
            assert len(agent_turns) >= 2, (
                f"Expected at least 2 agent turns, got {len(agent_turns)}"
            )
        va.capture("mt_09_turn_counts_verified")

    # --- 9. Verify bubble order and command separator ---
    with step("Verify bubble order and command separator", num=9, total=10):
        all_bubbles = page.locator(".chat-bubble[data-turn-id]")
        bubble_count = all_bubbles.count()
        turn_ids = []
        for i in range(bubble_count):
            tid = int(all_bubbles.nth(i).get_attribute("data-turn-id"))
            if tid > 0:
                turn_ids.append(tid)

        for i in range(1, len(turn_ids)):
            assert turn_ids[i] > turn_ids[i - 1], (
                f"Bubbles not in order: turn_id {turn_ids[i]} after {turn_ids[i - 1]}\n"
                f"All turn IDs: {turn_ids}"
            )
        va.capture("mt_10_bubble_order_verified")

        separators = page.locator(".chat-command-separator")
        separator_count = separators.count()
        assert separator_count >= 1, (
            f"Expected at least 1 command separator between command groups, "
            f"got {separator_count}"
        )
        va.capture("mt_11_separator_verified")

    # --- 10. Cross-layer verification (FR11, FR12, FR13) ---
    with step("Cross-layer verification (DOM/API/DB)", num=10, total=10):
        time.sleep(2)
        result = verify_cross_layer_consistency(page, agent_id, e2e_server, e2e_app)
        assert result["dom_turn_count"] >= 4, (
            f"Expected at least 4 DOM turns (2 user + 2 agent), "
            f"got {result['dom_turn_count']}"
        )
        assert result["command_count"] >= 2, (
            f"Expected at least 2 commands, got {result['command_count']}"
        )
        va.capture("mt_12_cross_layer_verified")

    va.capture("mt_13_test_complete")
    scenario_footer("Multi-Turn Conversation", start)
