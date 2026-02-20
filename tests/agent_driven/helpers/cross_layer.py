"""Cross-layer verification helper for agent-driven integration tests.

Compares DOM chat bubbles, API transcript, and database Turn records
for consistency. Also verifies timestamp monotonic ordering and
command state validity.

Extracted from Sprint 2 tests (test_question_answer.py, test_multi_turn.py)
where this function was duplicated. Now shared across 3+ test files per FR15.

Plain function only -- no classes, decorators, or metaclasses (constraint C6).
"""

import time

import requests


def _collect_dom_turns(page):
    """Collect turn IDs and actors from DOM chat bubbles."""
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
    return [t for t in dom_turns if t["id"] > 0]



def verify_cross_layer_consistency(page, agent_id, e2e_server, e2e_app):
    """Verify DOM, API transcript, and DB are consistent.

    Compares:
    - DOM chat bubbles (data-turn-id elements)
    - API transcript (/api/voice/agents/<id>/transcript)
    - Database Turn records (queried directly)

    Also verifies timestamp monotonic ordering in API and DB.

    Accounts for the voice chat renderer's turn grouping: consecutive
    agent turns with the same intent within 2 seconds are merged into
    a single DOM bubble, so grouped turn IDs won't appear individually.

    Args:
        page: Playwright page object with voice chat loaded.
        agent_id: The Agent.id to verify.
        e2e_server: The test server base URL (e.g. "https://...").
        e2e_app: The Flask app instance for DB access.

    Returns:
        dict with keys: dom_turn_count, api_turn_count, db_turn_count,
        command_count.

    Raises:
        AssertionError if any consistency check fails.
    """
    # --- 1. Collect DOM turn IDs and actor classes ---
    dom_turns = _collect_dom_turns(page)

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
            {"id": t.id, "actor": t.actor.value, "intent": t.intent.value, "timestamp": t.timestamp}
            for t in db_turns
        ]

        # --- Verify command states ---
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

    # --- DOM/API consistency ---
    # The DOM is a faithful subset of the API. Not every API turn gets a DOM
    # bubble because:
    #   1. Turn grouping: consecutive same-intent agent turns within 2s share
    #      a single bubble (only the first turn's ID becomes data-turn-id).
    #   2. Empty-text filtering: voice-sse-handler.js skips turns with no text
    #      at SSE delivery time, but reconciliation may populate text later.
    #   3. Terminal-originated answers: user ANSWER turns submitted via tmux
    #      Enter may not render as voice chat bubbles.
    #
    # Therefore we verify:
    #   a) Every DOM turn exists in the API (DOM ⊆ API) — no phantom bubbles
    #   b) Actor types match for turns present in both layers
    #   c) API/DB turn counts are consistent with each other (full data)
    dom_turn_ids = {t["id"] for t in dom_turns}
    api_turn_ids = {t["id"] for t in api_turns}

    # (a) Every DOM bubble must have a corresponding API turn
    phantom_dom = dom_turn_ids - api_turn_ids
    if phantom_dom:
        for _attempt in range(3):
            time.sleep(2)
            # Re-fetch API in case turns were still being written
            resp2 = requests.get(
                f"{e2e_server}/api/voice/agents/{agent_id}/transcript?limit=200",
                verify=False,
            )
            if resp2.status_code == 200:
                api_turns = resp2.json().get("turns", [])
                api_turn_ids = {t["id"] for t in api_turns}
                phantom_dom = dom_turn_ids - api_turn_ids
                if not phantom_dom:
                    break

    assert not phantom_dom, (
        f"DOM has turns not found in API: {phantom_dom}\n"
        f"DOM turn IDs: {sorted(dom_turn_ids)}\n"
        f"API turn IDs: {sorted(api_turn_ids)}"
    )

    # (b) Actor types match for turns in both layers
    common_ids = sorted(dom_turn_ids & api_turn_ids)
    if common_ids:
        dom_actors = {t["id"]: t["actor"] for t in dom_turns}
        api_actors = {t["id"]: t["actor"] for t in api_turns}
        for tid in common_ids:
            assert dom_actors[tid] == api_actors[tid], (
                f"Actor mismatch for turn {tid}: DOM={dom_actors[tid]}, API={api_actors[tid]}"
            )

    # (c) API and DB turn counts should match (both represent full data)
    db_turn_ids = {t["id"] for t in db_turn_data}
    assert api_turn_ids == db_turn_ids, (
        f"API/DB turn ID mismatch\n"
        f"In API only: {sorted(api_turn_ids - db_turn_ids)}\n"
        f"In DB only: {sorted(db_turn_ids - api_turn_ids)}"
    )

    # --- Timestamp ordering (API) ---
    api_timestamps = [t["timestamp"] for t in api_turns if t.get("timestamp")]
    for i in range(1, len(api_timestamps)):
        assert api_timestamps[i] >= api_timestamps[i - 1], (
            f"API timestamps out of order at index {i}: "
            f"{api_timestamps[i - 1]} > {api_timestamps[i]}"
        )

    # --- Timestamp ordering (DB) ---
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
