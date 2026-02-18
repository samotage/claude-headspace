---
title: 'Turn Capture Reliability'
slug: 'turn-capture-reliability'
created: '2026-02-18'
status: 'in-progress'
stepsCompleted: [1]
tech_stack:
  - Python 3.10+
  - Flask 3.0+
  - PostgreSQL / SQLAlchemy
  - tmux (capture-pane, subprocess)
files_to_modify:
  - src/claude_headspace/services/hook_receiver.py
  - src/claude_headspace/services/transcript_reconciler.py
  - src/claude_headspace/services/state_machine.py
  - src/claude_headspace/services/commander_availability.py
  - src/claude_headspace/routes/ (new or existing blueprint for reconcile endpoint)
  - templates/partials/_agent_card.html
  - static/js/agent-lifecycle.js
code_patterns:
  - Services accessed via app.extensions["service_name"]
  - State transitions via TaskLifecycleManager -> StateMachine
  - SSE broadcasts via broadcaster.broadcast()
  - tmux integration via tmux_bridge.capture_pane()
  - Background threads for periodic checks (CommanderAvailability pattern)
test_patterns:
  - Unit tests in tests/services/, route tests in tests/routes/
  - _force_test_database fixture enforces claude_headspace_test DB
  - factory-boy for integration tests
---

# Tech-Spec: Turn Capture Reliability

**Created:** 2026-02-18

## Overview

### Problem Statement

Agent turns are silently destroyed when hook processing fails. The `process_stop` method in `hook_receiver.py` creates a Turn and attempts a state transition in a single transaction. If the state machine raises `InvalidTransitionError`, the `except` block calls `db.session.rollback()`, destroying the Turn along with the failed state change. The transcript reconciler (safety net) only runs at session_end, not during the session, so mid-session recovery never happens. No independent verification exists to catch these gaps.

**Root cause sequence (observed 2026-02-18, agent 583):**
1. Agent outputs response -> `stop` hook fires -> Turn created in session
2. `lifecycle.update_task_state()` called -> state machine has no entry for `(AWAITING_INPUT, AGENT, QUESTION)`
3. `InvalidTransitionError` raised -> `except` block at line 1092 -> `db.session.rollback()` -> Turn destroyed
4. JSONL transcript has the entry -> reconciler only runs at session_end -> turn lost until session ends

### Solution

Three-tier reliability model where each tier independently guarantees turn capture:

| Tier | Source | Latency | Reliability | Role |
|------|--------|---------|-------------|------|
| 1 | Hooks | <100ms | Unreliable | Fast path — optimistic UI updates |
| 2 | JSONL Transcripts | 2-10s | Authoritative | Gold standard — guarantees completeness |
| 3 | Tmux Pane | ~1s | Visual ground truth | Independent verification via pane capture |

**The inversion:** Hooks are the preview. JSONL is the authority. Tmux is the ground truth. If a hook fails, the reconciler MUST create the missing turn. If the reconciler misses it, the tmux pane verifier catches it.

### Scope

**In Scope:**
- Task 1: Decouple turn persistence from state transitions in `process_stop`
- Task 2: Fix transcript reconciler — ensure missing turns are always created from JSONL
- Task 3: Recovered turns feed into task lifecycle (IntentDetector + state transitions)
- Task 4: State machine audit for missing transitions
- Task 5: Recovery logging (WARNING/INFO/DEBUG levels)
- Task 6: Force reconciliation endpoint + kebab menu button
- Task 7: Tier 3 — Tmux pane content verification (periodic capture_pane checks cross-referenced against DB turns)

**Out of Scope:**
- Client-side voice chat rendering changes
- Database schema changes (new tables)
- File watcher polling interval changes
- SSE event type definition changes

## Context for Development

### Codebase Patterns

- **Service injection:** Services registered in `app.extensions` and accessed via `app.extensions["service_name"]`
- **State transitions:** `TaskLifecycleManager.update_task_state()` calls `StateMachine.validate_transition()` — raises `InvalidTransitionError` on invalid combos
- **Transaction scope:** Most hook handlers use a single try/except with `db.session.rollback()` in the except — this is the root cause of turn loss
- **SSE broadcasting:** `broadcaster.broadcast(event_type, data)` — turn events use `turn_created` and `turn_updated`
- **Tmux infrastructure:** `tmux_bridge.capture_pane(pane_id, lines=N)` already captures pane content; `CommanderAvailability` runs a 30-second health check loop that can be extended
- **Reconciler invocation:** Currently only called at session_end in `process_session_end` (line 645 of hook_receiver.py) — NOT called during active sessions

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `src/claude_headspace/services/hook_receiver.py` | Hook processing, turn creation — primary fix target (Task 1) |
| `src/claude_headspace/services/transcript_reconciler.py` | JSONL -> DB reconciliation — fix + lifecycle integration (Tasks 2, 3) |
| `src/claude_headspace/services/state_machine.py` | Valid transition definitions — audit (Task 4) |
| `src/claude_headspace/services/task_lifecycle.py` | State transitions, turn records — verify transaction scope |
| `src/claude_headspace/services/file_watcher.py` | Watches JSONL, feeds reconciler — investigate entry delivery |
| `src/claude_headspace/services/intent_detector.py` | Classifies agent intent — used by Task 3 |
| `src/claude_headspace/services/tmux_bridge.py` | `capture_pane()`, `wait_for_pattern()` — foundation for Tier 3 |
| `src/claude_headspace/services/commander_availability.py` | Periodic health check loop — extend for Tier 3 pane verification |
| `templates/partials/_agent_card.html` | Agent card template — add reconcile kebab item (Task 6) |
| `static/js/agent-lifecycle.js` | Kebab menu JS handlers — add reconcile click handler (Task 6) |

### Technical Decisions

- **Separate commits for turn vs state:** Turn is committed to DB BEFORE state transition is attempted. If state fails, turn survives.
- **Reconciler uses IntentDetector:** Recovered turns get proper intent classification, not just the simple user=COMMAND/agent=PROGRESS heuristic.
- **Tmux Tier 3 piggybacks on CommanderAvailability:** No new background thread — extend the existing 30-second health check loop.
- **No new database tables:** All changes use existing models (Turn, Task, Agent).

## Implementation Plan

### Tasks

(To be populated in Step 3)

### Acceptance Criteria

(To be populated in Step 3)

## Additional Context

### Dependencies

- PRD: `_bmad-output/planning-artifacts/prd.md`
- Band-aid commit: `179f87c` (added missing AWAITING_INPUT transitions)
- Implementation prompt: `docs/reviews_remediation/turn-capture-reliability-implementation-prompt.md`

### Testing Strategy

Run targeted tests only:
- `pytest tests/services/test_hook_receiver.py`
- `pytest tests/services/test_transcript_reconciler.py`
- `pytest tests/services/test_task_lifecycle.py`
- `pytest tests/services/test_state_machine.py`
- `pytest tests/routes/test_hooks.py`

New tests needed for:
- Turn survives when `update_task_state()` raises `InvalidTransitionError`
- Reconciler creates Turn when no matching hash exists
- Reconciler-created Turn triggers state transition
- Force reconciliation endpoint
- Idempotency: reconciler run twice produces no duplicates
- Tmux pane verification detects missing turn and triggers recovery

### Notes

- The file watcher does NOT call the reconciler — reconciliation only happens at session_end
- The `_content_hash` uses first 200 chars + actor, which could produce false positives on similar content
- `MATCH_WINDOW_SECONDS = 30` in the reconciler may be too narrow for delayed JSONL writes
