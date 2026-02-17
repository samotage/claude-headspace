# Implementation Prompt: Turn Capture Reliability

**PRD:** `_bmad-output/planning-artifacts/prd.md`
**Branch:** Create `feature/turn-capture-reliability` from `development`

## Problem

Agent turns are silently lost when hook processing fails. The `process_stop` method in `hook_receiver.py` creates a Turn, then attempts a state transition. If the state machine raises `InvalidTransitionError`, the `except` block calls `db.session.rollback()`, destroying the Turn. The transcript reconciler (Phase 2 safety net) should catch this, but doesn't — it only matches against existing turns and fails to create new ones in certain edge cases.

**Root cause sequence (observed 2026-02-18, agent 583):**
1. Agent outputs response → `stop` hook fires → Turn created in session
2. `lifecycle.update_task_state()` called → state machine has no entry for `(AWAITING_INPUT, AGENT, QUESTION)`
3. `InvalidTransitionError` raised → `except` block at line 1092 → `db.session.rollback()` → Turn destroyed
4. JSONL transcript has the entry → reconciler runs → but recovery path doesn't trigger

**Band-aid applied:** Commit `179f87c` added missing transitions. This PRD fixes the systemic issue.

## Architecture: Three-Tier Reliability Model

| Tier | Source | Latency | Reliability | Role |
|------|--------|---------|-------------|------|
| 1 | Hooks | <100ms | Unreliable | Fast path — optimistic UI updates |
| 2 | JSONL Transcripts | 2-10s | Authoritative | Gold standard — guarantees completeness |
| 3 | Tmux Pane | ~1s | Visual ground truth | Real-time watchdog — bridges "hook didn't fire" to "transcript hasn't arrived" |

**The inversion:** Hooks are the preview. JSONL is the authority. Tmux is the early warning. If a hook fails, the tmux watchdog detects the gap within seconds and triggers reconciliation. The reconciler MUST create the missing turn from the JSONL entry.

## Implementation Tasks (in dependency order)

### Task 1: Decouple Turn Persistence from State Transitions

**File:** `src/claude_headspace/services/hook_receiver.py`
**Method:** `process_stop()` (lines 870–1096)

**Current pattern (broken):**
```
try:
    turn = Turn(...)          # Create turn
    db.session.add(turn)
    lifecycle.update_task_state(...)  # May raise InvalidTransitionError
    db.session.commit()       # Line 1043 — single commit for everything
except Exception:
    db.session.rollback()     # Lines 1092-1095 — destroys the turn
```

**Required pattern:**
```
# 1. Persist the turn FIRST (separate commit or savepoint)
turn = Turn(...)
db.session.add(turn)
db.session.flush()  # Get the turn ID
db.session.commit()  # Turn is now safe in DB

# 2. Broadcast the turn (it exists regardless of state outcome)
broadcast_turn_created(turn)

# 3. THEN attempt state transition (can fail without data loss)
try:
    lifecycle.update_task_state(...)
    db.session.commit()
except InvalidTransitionError as e:
    db.session.rollback()  # Only rolls back the state change, not the turn
    logger.warning(f"State transition failed for turn {turn.id}: {e}")
```

**Key constraint:** The turn must be committed to the database BEFORE `update_task_state()` is called. If the state transition fails, the turn survives. The SSE broadcast should also happen after the turn commit, not after the state commit.

**Affected code paths in `process_stop`:**
- QUESTION intent turn creation (lines 1006–1017)
- COMPLETION via `complete_task()` (line 1037)
- END_OF_TASK via `complete_task()` (lines 1024–1027)

**Also check:** `_handle_awaiting_input()` and `process_user_prompt_submit()` for the same pattern — any place a Turn is created and a state transition follows in the same transaction scope.

### Task 2: Fix Transcript Reconciler — Create Missing Turns

**File:** `src/claude_headspace/services/transcript_reconciler.py`
**Method:** `reconcile_transcript_entries()` (lines 23–97)

**Current behavior:** The reconciler builds a `turn_index` from recent turns (within a time window), then for each JSONL entry:
- If content hash matches → update timestamp (working)
- If no match → create new Turn (lines 78–92)

**The bug:** The reconciler IS creating turns for unmatched entries in its code path, but there are conditions where it doesn't trigger:
1. The time window for matching (`MATCH_WINDOW_SECONDS`) may be too narrow
2. The file watcher's byte position tracking may skip entries
3. The `_content_hash` dedup may produce false positives

**Investigation needed:** Read the reconciler flow end-to-end and trace exactly why a rolled-back turn's JSONL entry doesn't result in a new turn being created. The code at lines 78-92 looks like it should work. The gap is likely in:
- How entries are fed from `file_watcher.py` to the reconciler
- The time window filtering when building the `turn_index`
- Whether the reconciler is even called for the relevant JSONL entries

**Required outcome:** Every JSONL entry with non-empty content that has no matching Turn in the database MUST result in a new Turn being created. No silent skipping. Add logging at INFO level when a new turn is created via reconciliation.

### Task 3: Recovered Turns Feed Into Task Lifecycle

**File:** `src/claude_headspace/services/transcript_reconciler.py`

**Current behavior:** When the reconciler creates a new Turn (lines 78-92), it sets `intent=_infer_intent(actor, entry)` which maps User→COMMAND, Agent→PROGRESS. It does NOT call into the TaskLifecycleManager.

**Required change:** After creating a recovered Turn, the reconciler must:
1. Detect the turn's intent using `IntentDetector` (not just the simple `_infer_intent`)
2. Call `TaskLifecycleManager.update_task_state()` with the appropriate transition
3. Handle `InvalidTransitionError` gracefully (log warning, don't destroy the turn)
4. Broadcast SSE events for both the turn and any state transition

**Key consideration:** The reconciler runs in the file watcher's thread context. It needs access to `app.extensions["intent_detector"]` and `app.extensions["task_lifecycle"]`. Ensure the Flask app context is available.

### Task 4: State Machine Audit

**File:** `src/claude_headspace/services/state_machine.py`
**Dict:** `VALID_TRANSITIONS` (lines 34–60)

**Current AWAITING_INPUT transitions (already includes fix from 179f87c):**
- `(AWAITING_INPUT, USER, ANSWER) → PROCESSING`
- `(AWAITING_INPUT, AGENT, QUESTION) → AWAITING_INPUT`
- `(AWAITING_INPUT, AGENT, PROGRESS) → AWAITING_INPUT`
- `(AWAITING_INPUT, AGENT, COMPLETION) → COMPLETE`
- `(AWAITING_INPUT, AGENT, END_OF_TASK) → COMPLETE`

**Audit required:** Check ALL state combinations for missing transitions that could cause data loss. Specifically:
- Can an agent produce a COMMAND intent? (Shouldn't happen, but defensive)
- What about PROCESSING → PROCESSING with USER:COMMAND? (User sends new command while agent is working)
- Any IDLE state transitions that could fail unexpectedly?

**Principle:** The state machine should never be the reason a turn is lost. If a transition is invalid, log it — don't destroy the turn.

### Task 5: Recovery Logging

**All modified files from Tasks 1-4.**

**Required log levels:**
- **WARNING:** Every hook processing failure with context: `[HOOK_RECEIVER] process_stop state transition failed: from={state} actor={actor} intent={intent} error={exception} — turn {turn_id} preserved`
- **INFO:** Every recovery action: `[RECONCILER] Created turn {turn_id} from JSONL entry (agent={agent_id}, intent={intent}, hash={hash}) — no matching hook-created turn found`
- **INFO:** State transitions from recovered turns: `[RECONCILER] Recovered turn {turn_id} triggered state transition: {from_state} → {to_state}`
- **DEBUG:** Full diagnostic chain details (content hash, match attempts, time windows)

### Task 6: Force Reconciliation Endpoint + Kebab Menu

**New route:** Add to an appropriate existing blueprint (likely `routes/sessions.py` or create in the agents routes).

**Endpoint:** `POST /api/agents/<agent_id>/reconcile`
- Triggers `reconcile_agent_session()` for the specified agent
- Returns `{"status": "ok", "created": N, "updated": N}`
- Must complete within 5 seconds

**Dashboard kebab menu:** Add a "Reconcile" button to the agent card kebab menu.

**Template:** `templates/partials/_agent_card.html` — Add after the "Fetch context" button (line 150):
```html
<button class="card-kebab-item card-reconcile-action" data-agent-id="{{ agent.id }}">
  <svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 8a7 7 0 0 1 13.4-2.8M15 8a7 7 0 0 1-13.4 2.8"/><path d="M14.4 1v4.2h-4.2M1.6 15v-4.2h4.2"/></svg>
  <span>Reconcile</span>
</button>
```

**JS handler:** Add to `static/js/agent-lifecycle.js` alongside the existing kebab item handlers (after line 248):
```javascript
var reconcileAction = e.target.closest('.card-reconcile-action');
if (reconcileAction) {
    e.preventDefault();
    e.stopPropagation();
    var agentId = reconcileAction.getAttribute('data-agent-id');
    closeCardKebabs();
    fetch('/api/agents/' + agentId + '/reconcile', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            // Brief notification of result
        });
    return;
}
```

### Task 7: Tmux Pane Watchdog

**File:** `src/claude_headspace/services/commander_availability.py` (extend or extract new service)
**Related:** `src/claude_headspace/services/tmux_bridge.py`

**Current behavior:** `CommanderAvailability` already monitors tmux panes on a background thread to track whether agents are available for commander input. It reads pane content but only checks for availability indicators — it does NOT compare pane output against database turns.

**Required behavior:** Add a turn gap detection layer that:

1. **Captures tmux pane content** on each monitoring cycle (already happening)
2. **Detects new agent output** — compare current pane content against last-seen content to identify new output since last check
3. **Checks for unrepresented turns** — when new agent output is detected, query the database for a matching Turn within the last N seconds. If no match exists after 5 seconds, flag a gap.
4. **Triggers early reconciliation** — when a gap is detected, trigger the reconciler for that agent immediately rather than waiting for the file watcher's next JSONL poll cycle
5. **Graceful degradation** — when tmux is unavailable (agent not in tmux session), skip watchdog silently. The system falls back to JSONL-only reconciliation (Tier 2). Log at DEBUG level.

**Key considerations:**
- The watchdog runs on the existing `CommanderAvailability` background thread (or a new lightweight thread if separation is cleaner)
- Pane content comparison should be lightweight — hash-based, not full diff
- The 5-second threshold is configurable via `config.yaml` (suggest `headspace.tmux_watchdog.gap_threshold_seconds`)
- Must not interfere with the existing commander availability checks
- Agent must have a `tmux_pane_id` set — skip agents without one

**Logging:**
- **INFO:** `[TMUX_WATCHDOG] Gap detected for agent {agent_id} — new output in pane {pane_id} with no matching turn after {threshold}s, triggering reconciliation`
- **DEBUG:** `[TMUX_WATCHDOG] Agent {agent_id} pane content unchanged` / `[TMUX_WATCHDOG] Agent {agent_id} no tmux pane — skipping`

## Key Files Reference

| File | Role | What Changes |
|------|------|-------------|
| `src/claude_headspace/services/hook_receiver.py` | Hook processing, turn creation | Decouple turn commit from state transition (Task 1) |
| `src/claude_headspace/services/transcript_reconciler.py` | JSONL → DB reconciliation | Fix missing turn creation, add lifecycle integration (Tasks 2, 3) |
| `src/claude_headspace/services/task_lifecycle.py` | State transitions, turn records | No changes expected — but verify transaction scope |
| `src/claude_headspace/services/state_machine.py` | Valid transition definitions | Audit for gaps (Task 4) |
| `src/claude_headspace/services/file_watcher.py` | Watches JSONL, feeds reconciler | Investigate if entries are being dropped (Task 2) |
| `src/claude_headspace/services/intent_detector.py` | Classifies agent intent | Used by Task 3 for recovered turn intent detection |
| `src/claude_headspace/services/commander_availability.py` | Tmux pane monitoring | Add turn gap detection watchdog (Task 7) |
| `templates/partials/_agent_card.html` | Agent card template | Add reconcile kebab item (Task 6) |
| `static/js/agent-lifecycle.js` | Kebab menu JS handlers | Add reconcile click handler (Task 6) |

## Testing Strategy

**Run targeted tests only.** Do NOT run the full suite unless explicitly asked.

**Existing test files to run after changes:**
- `pytest tests/services/test_hook_receiver.py` — Verify happy path not broken
- `pytest tests/services/test_transcript_reconciler.py` — Verify reconciler creates missing turns
- `pytest tests/services/test_task_lifecycle.py` — Verify state transitions
- `pytest tests/services/test_state_machine.py` — Verify transition table
- `pytest tests/routes/test_hooks.py` — Verify hook endpoint behavior

**New tests needed:**
- Test that a Turn survives when `update_task_state()` raises `InvalidTransitionError`
- Test that the reconciler creates a Turn when no matching hash exists
- Test that a reconciler-created Turn triggers a state transition
- Test that force reconciliation endpoint works
- Test idempotency: reconciler run twice on same data produces no duplicates
- Test that tmux watchdog detects new pane output with no matching turn and triggers reconciliation
- Test that tmux watchdog skips agents without a tmux pane (graceful degradation)
- Test that tmux watchdog does not interfere with commander availability checks

**Test database:** Tests use `claude_headspace_test` (enforced by `_force_test_database` fixture). Before running tests: `createdb claude_headspace_test` if it doesn't exist.

## Critical Rules

- **NEVER restart the server** unless absolutely necessary. Flask auto-reloads Python changes. If restart needed: `./restart_server.sh` ONLY.
- **NEVER switch git branches.** Work on the feature branch.
- **NEVER use `localhost`** — the application URL is `https://smac.griffin-blenny.ts.net:5055`
- **NEVER run `python run.py` directly** or kill processes manually.
- **NEVER modify `.gitignore`** — symlinked directories have specific ignore patterns.
- **Run targeted tests**, not the full suite.
- **After implementation, verify against the running app** — unit tests passing does not mean the app works. Take screenshots with Playwright CLI to verify UI changes.

## What NOT to Change

- Client-side voice chat rendering (SSE handling, gap recovery, bubble rendering)
- File watcher polling interval
- SSE event type definitions (`turn_created`, `turn_updated`)
- Database schema (no new tables; possible new columns on Turn if needed)
- Service registration patterns (`app.extensions`)
- Any file outside the scope of Tasks 1-7
