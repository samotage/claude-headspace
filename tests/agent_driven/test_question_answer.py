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

    # DOM should contain all API turns (DOM may have extra pending items)
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
    agent_id = claude_session["agent_id"]
    session_name = claude_session["session_name"]

    # --- 1. Navigate to voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.capture("qa_01_voice_loaded")

    # --- 2. Wait for agent card and select it ---
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.capture("qa_02_agent_card_visible")
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("qa_03_chat_ready")

    # --- 3. Send prompt that triggers AskUserQuestion ---
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
    # When Claude uses AskUserQuestion, the pre_tool_use hook fires,
    # state transitions to AWAITING_INPUT, and a question Turn is created.
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("qa_05_question_visible")

    # --- 5. Verify option text in the question bubble ---
    question_text = agent_bubbles.first.inner_text()
    assert "12-hour" in question_text.lower() or "24-hour" in question_text.lower(), (
        f"Expected AskUserQuestion with time format options: {question_text!r}"
    )

    # --- 6. Verify AWAITING_INPUT state reached in database ---
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
    time.sleep(1)  # Let terminal UI settle
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "Enter"],
        check=True, timeout=5,
    )
    va.capture("qa_07_option_selected")

    # --- 8. Wait for response bubble after option selection ---
    # After selection, Claude processes and responds. Wait for a second
    # agent bubble (the actual response after the question).
    expect(agent_bubbles.nth(1)).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("qa_08_response_visible")

    # --- 9. Verify command reaches COMPLETE state ---
    with e2e_app.app_context():
        db.session.expire_all()
        command = (
            db.session.query(Command)
            .filter_by(agent_id=agent_id)
            .order_by(Command.id.desc())
            .first()
        )
        assert command is not None, "No Command record found after response"
        assert command.state == CommandState.COMPLETE, (
            f"Expected COMPLETE state, got {command.state.value}"
        )

    va.capture("qa_09_complete_verified")

    # --- 10. Cross-layer verification (FR11, FR12, FR13) ---
    # Wait briefly for any async processing to settle
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
