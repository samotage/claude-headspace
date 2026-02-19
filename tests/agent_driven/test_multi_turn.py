"""Agent-driven integration test: multi-turn conversation with cross-layer verification.

Sends two sequential commands via the voice chat UI, waits for both to complete,
and verifies correct turn counts, bubble ordering, command separators, and
cross-layer consistency (DOM vs API vs DB). Includes timestamp ordering checks.

Every layer is real. Nothing is mocked.
"""

import time
from pathlib import Path

import pytest
import requests
from playwright.sync_api import expect

from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 60_000  # ms -- generous timeout for real LLM processing


# ---------------------------------------------------------------------------
# Cross-layer verification (plain function, per constraint C3)
# ---------------------------------------------------------------------------

def verify_cross_layer_consistency(page, agent_id, e2e_server, e2e_app):
    """Verify DOM, API transcript, and DB are consistent.

    Compares:
    - DOM chat bubbles (data-turn-id elements)
    - API transcript (/api/voice/agents/<id>/transcript)
    - Database Turn records (queried directly)

    Also verifies timestamp monotonic ordering in API and DB.
    """
    # --- 1. Collect DOM turn IDs and actor classes ---
    bubbles = page.locator(".chat-bubble[data-turn-id]")
    bubble_count = bubbles.count()
    dom_turns = []
    for i in range(bubble_count):
        bubble = bubbles.nth(i)
        turn_id = int(bubble.get_attribute("data-turn-id"))
        classes = bubble.get_attribute("class") or ""
        if "user" in classes:
            actor = "user"
        elif "agent" in classes:
            actor = "agent"
        else:
            actor = "unknown"
        dom_turns.append({"id": turn_id, "actor": actor})

    # Filter out fake/negative turn IDs (pending sends use negative IDs)
    dom_turns = [t for t in dom_turns if t["id"] > 0]

    # --- 2. Fetch API transcript ---
    resp = requests.get(
        f"{e2e_server}/api/voice/agents/{agent_id}/transcript?limit=200",
        verify=False,
    )
    assert resp.status_code == 200, f"Transcript API returned {resp.status_code}"
    api_data = resp.json()
    api_turns = api_data.get("turns", [])

    # --- 3. Query DB directly ---
    from claude_headspace.database import db
    from claude_headspace.models.command import Command, CommandState
    from claude_headspace.models.turn import Turn, TurnIntent

    with e2e_app.app_context():
        db_turns = (
            db.session.query(Turn)
            .join(Command, Turn.command_id == Command.id)
            .filter(Command.agent_id == agent_id)
            .filter(Turn.is_internal == False)  # noqa: E712
            .order_by(Turn.timestamp.asc(), Turn.id.asc())
            .all()
        )

        # Filter out empty PROGRESS turns (matches API behavior)
        db_turns = [
            t for t in db_turns
            if not (t.intent == TurnIntent.PROGRESS and (not t.text or not t.text.strip()))
        ]

        db_turn_data = [
            {"id": t.id, "actor": t.actor.value, "timestamp": t.timestamp}
            for t in db_turns
        ]

        # --- FR12: Verify command states ---
        commands = (
            db.session.query(Command)
            .filter_by(agent_id=agent_id)
            .order_by(Command.id)
            .all()
        )
        for cmd in commands:
            assert cmd.state in (CommandState.COMPLETE, CommandState.AWAITING_INPUT), (
                f"Command {cmd.id} in unexpected state: {cmd.state.value}"
            )

    # --- FR11: DOM/API consistency ---
    dom_turn_ids = {t["id"] for t in dom_turns}
    api_turn_ids = {t["id"] for t in api_turns}

    # DOM should contain all API turns
    missing_in_dom = api_turn_ids - dom_turn_ids
    assert not missing_in_dom, (
        f"API turns missing from DOM: {missing_in_dom}\n"
        f"DOM turn IDs: {sorted(dom_turn_ids)}\n"
        f"API turn IDs: {sorted(api_turn_ids)}"
    )

    # Compare actor sequences for turns present in both
    common_ids = sorted(dom_turn_ids & api_turn_ids)
    if common_ids:
        dom_actors = {t["id"]: t["actor"] for t in dom_turns}
        api_actors = {t["id"]: t["actor"] for t in api_turns}
        for tid in common_ids:
            assert dom_actors[tid] == api_actors[tid], (
                f"Actor mismatch for turn {tid}: DOM={dom_actors[tid]}, API={api_actors[tid]}"
            )

    # --- FR12: DOM/DB consistency ---
    db_turn_ids = {t["id"] for t in db_turn_data}
    missing_in_dom_from_db = db_turn_ids - dom_turn_ids
    assert not missing_in_dom_from_db, (
        f"DB turns missing from DOM: {missing_in_dom_from_db}\n"
        f"DOM turn IDs: {sorted(dom_turn_ids)}\n"
        f"DB turn IDs: {sorted(db_turn_ids)}"
    )

    # --- FR13: Timestamp ordering (API) ---
    api_timestamps = [t["timestamp"] for t in api_turns if t.get("timestamp")]
    for i in range(1, len(api_timestamps)):
        assert api_timestamps[i] >= api_timestamps[i - 1], (
            f"API timestamps out of order at index {i}: "
            f"{api_timestamps[i - 1]} > {api_timestamps[i]}"
        )

    # --- FR13: Timestamp ordering (DB) ---
    db_timestamps = [t["timestamp"] for t in db_turn_data]
    for i in range(1, len(db_timestamps)):
        assert db_timestamps[i] >= db_timestamps[i - 1], (
            f"DB timestamps out of order at index {i}: "
            f"{db_timestamps[i - 1]} > {db_timestamps[i]}"
        )

    return {
        "dom_turn_count": len(dom_turns),
        "api_turn_count": len(api_turns),
        "db_turn_count": len(db_turn_data),
        "command_count": len(commands),
    }


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
    agent_id = claude_session["agent_id"]

    # --- 1. Navigate to voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.capture("mt_01_voice_loaded")

    # --- 2. Wait for agent card and select it ---
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.capture("mt_02_agent_card_visible")
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("mt_03_chat_ready")

    # --- 3. Send first command ---
    va.send_chat_message(
        "Tell me a short one-liner joke. Keep your response to one sentence."
    )
    va.capture("mt_04_command1_sent")

    # Wait for first agent response bubble
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("mt_05_command1_response")

    # Record bubble count after round 1
    round1_bubble_count = agent_bubbles.count()

    # --- 4. Wait for first command to fully complete ---
    from claude_headspace.database import db
    from claude_headspace.models.command import Command, CommandState

    # Poll for COMPLETE state on the first command
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

    # Let the state fully settle
    time.sleep(2)

    # --- 5. Send second command ---
    va.send_chat_message(
        "Now tell me a different short one-liner joke. Keep your response to one sentence."
    )
    va.capture("mt_06_command2_sent")

    # Wait for a new agent bubble beyond round 1's count
    expect(agent_bubbles.nth(round1_bubble_count)).to_be_visible(
        timeout=RESPONSE_TIMEOUT
    )
    va.capture("mt_07_command2_response")

    # --- 6. Verify both commands reach COMPLETE in DB ---
    # Poll for second command to complete
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

        # Final assertion
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

    # --- 7. Verify correct number of user and agent turns in DB ---
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

    # --- 8. Verify all bubbles in correct order in DOM ---
    all_bubbles = page.locator(".chat-bubble[data-turn-id]")
    bubble_count = all_bubbles.count()
    turn_ids = []
    for i in range(bubble_count):
        tid = int(all_bubbles.nth(i).get_attribute("data-turn-id"))
        if tid > 0:  # Skip negative fake IDs
            turn_ids.append(tid)

    # Turn IDs should be monotonically increasing (rendered in order)
    for i in range(1, len(turn_ids)):
        assert turn_ids[i] > turn_ids[i - 1], (
            f"Bubbles not in order: turn_id {turn_ids[i]} after {turn_ids[i - 1]}\n"
            f"All turn IDs: {turn_ids}"
        )

    va.capture("mt_10_bubble_order_verified")

    # --- 9. Verify command separator between command groups ---
    separators = page.locator(".chat-command-separator")
    separator_count = separators.count()
    assert separator_count >= 1, (
        f"Expected at least 1 command separator between command groups, "
        f"got {separator_count}"
    )

    va.capture("mt_11_separator_verified")

    # --- 10. Cross-layer verification (FR11, FR12, FR13) ---
    time.sleep(2)  # Let async processing settle
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
