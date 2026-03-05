# Channel Relay Pipeline Remediation Plan

**Date:** 5 March 2026
**Lead:** Mark (Full-Stack Flow Tracer)
**Source:** Channels Functional Review — Findings F8, F9, F10
**Branch:** `development`

---

## Problem Statement

Agent completion responses don't appear in channel chat UI. Three structural gaps:

1. **Stale `ChannelMembership.agent_id`** — Neither `HandoffExecutor` nor `SessionCorrelator` updates membership when a new agent registers for an existing persona. Membership lookup in `relay_agent_response()` returns `None`.

2. **Reconciler is channel-blind** — The transcript reconciler creates COMPLETION/END_OF_COMMAND turns but never calls `relay_agent_response()`. This is the primary path exercised in practice (stop hooks are unreliable).

3. **Single integration point** — `relay_agent_response()` is only called from `hook_receiver.process_stop()`. If that path doesn't execute, messages never reach channels.

---

## Fixes

### Fix 1: Update ChannelMembership.agent_id on persona assignment

**Files:** `session_correlator.py`, `handoff_executor.py`

**session_correlator.py:**
- After assigning `agent.persona_id` in `correlate_session()`, query `ChannelMembership` rows with matching `persona_id` and `status='active'`
- Update `agent_id` to the new agent's ID
- Log the update

**handoff_executor.py:**
- After creating the successor agent and assigning persona, update `ChannelMembership` rows for that `persona_id` with the successor's `agent_id`

### Fix 2: Persona-based fallback in relay_agent_response()

**File:** `channel_delivery.py`

- Current: `ChannelMembership.query.filter_by(agent_id=agent.id, status="active").first()`
- Add fallback: if no match by `agent_id` AND agent has `persona_id`, try `filter_by(persona_id=agent.persona_id, status="active").first()`
- If fallback finds a match, update `agent_id` in-place (self-healing)
- This catches race conditions or missed update paths

### Fix 3: Wire channel relay into transcript reconciler

**File:** `transcript_reconciler.py`

- After creating/updating a Turn with COMPLETION or END_OF_COMMAND intent for an AGENT actor:
  - Get `channel_delivery_service` from `app.extensions`
  - If service exists, call `relay_agent_response(agent, turn_text, turn_intent, turn_id, command_id)`
- This makes the reconciler the reliable backbone for channel relay
- The hook path remains as best-effort bonus (no changes needed)

### Fix 4: Verify IntentDetector handles responses without COMMAND COMPLETE footer

**File:** `intent_detector.py`

- Review current COMPLETION and END_OF_COMMAND patterns
- Verify that substantive agent responses (summaries, explanations, code output) without explicit COMMAND COMPLETE footer are detected
- Add patterns if gaps found — e.g., "Here's what I found", "I've completed", structured response with results
- This is investigation + targeted addition, not a rewrite

---

## Implementation Order

1. Fix 1 (membership update) — prerequisite for relay to work
2. Fix 2 (persona fallback) — defense in depth
3. Fix 3 (reconciler relay) — the primary fix
4. Fix 4 (intent detection) — refinement

## Testing

- Targeted unit tests for each fix
- Run existing channel tests to verify no regressions
- Tests must use `claude_headspace_test` database (enforced by `_force_test_database` fixture)

## Verification

After all fixes: agent completes turn → reconciler creates Turn → relay finds membership (by agent_id or persona fallback) → `send_message()` persists Message → SSE `channel_message` broadcasts → UI can render.
