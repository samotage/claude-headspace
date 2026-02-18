---
title: 'Turn Capture Reliability'
slug: 'turn-capture-reliability'
created: '2026-02-18'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4]
tech_stack:
  - Python 3.10+
  - Flask 3.0+ (app factory, blueprints)
  - PostgreSQL / SQLAlchemy (session-per-request, caller-owned commits)
  - tmux (capture-pane subprocess, 5s default timeout)
  - Watchdog (filesystem observer for JSONL)
files_to_modify:
  - src/claude_headspace/services/hook_receiver.py (Task 1 — decouple turn persistence)
  - src/claude_headspace/services/hook_deferred_stop.py (Task 1 — same broken pattern)
  - src/claude_headspace/services/transcript_reconciler.py (Tasks 2, 3, 8)
  - src/claude_headspace/services/state_machine.py (Task 4 — audit transitions)
  - src/claude_headspace/services/tmux_watchdog.py (Task 7 — NEW service)
  - src/claude_headspace/routes/agents.py (Task 6 — reconcile endpoint)
  - templates/partials/_agent_card.html (Task 6 — reconcile kebab button)
  - static/js/agent-lifecycle.js (Task 6 — reconcile click handler)
code_patterns:
  - Services accessed via app.extensions["service_name"]
  - State transitions via TaskLifecycleManager -> StateMachine (raises InvalidTransitionError)
  - TaskLifecycleManager flushes but NEVER commits — caller (hook_receiver) owns commits
  - SSE broadcasts via broadcaster.broadcast(event_type, data)
  - tmux subprocess calls via tmux_bridge.capture_pane(pane_id, lines=N, timeout=5)
  - Background daemon threads with stop_event for periodic services (CommanderAvailability pattern)
  - Kebab menu items: .card-kebab-item + .card-{name}-action class + data-agent-id attr
  - Route endpoints in blueprints: @agents_bp.route("/api/agents/<int:agent_id>/...")
test_patterns:
  - Unit tests in tests/services/, route tests in tests/routes/
  - _force_test_database fixture enforces claude_headspace_test DB
  - app_ctx fixture creates/drops all tables per test class
  - MagicMock for agents, tasks; patch() for service dependencies
  - factory-boy for integration tests (tests/integration/)
---

# Tech-Spec: Turn Capture Reliability

**Created:** 2026-02-18

## Overview

### Problem Statement

Agent turns are silently destroyed when hook processing fails. The `process_stop` method in `hook_receiver.py` creates a Turn and attempts a state transition in a single transaction. If the state machine raises `InvalidTransitionError`, the `except` block calls `db.session.rollback()`, destroying the Turn along with the failed state change. The transcript reconciler (safety net) only runs at session_end via `reconcile_agent_session()` — it is never called during active sessions, so mid-session recovery never happens. No independent real-time verification exists to catch these gaps.

**Root cause sequence (observed 2026-02-18, agent 583):**
1. Agent outputs response -> `stop` hook fires -> Turn created in session
2. `lifecycle.update_task_state()` called -> state machine has no entry for `(AWAITING_INPUT, AGENT, QUESTION)`
3. `InvalidTransitionError` raised -> `except` block at line 1092 -> `db.session.rollback()` -> Turn destroyed
4. JSONL transcript has the entry -> reconciler only runs at session_end -> turn lost until session ends

**Broken pattern prevalence (from deep investigation):**

| Method | Location | Turn Type | Risk |
|--------|----------|-----------|------|
| `process_stop()` | hook_receiver.py:1006-1013 | QUESTION | CRITICAL |
| `process_stop()` | hook_receiver.py (via complete_task) | COMPLETION | CRITICAL |
| `process_user_prompt_submit()` | hook_receiver.py (via process_turn) | USER COMMAND | CRITICAL |
| `_handle_awaiting_input()` | hook_receiver.py:1209-1218 | QUESTION | CRITICAL |
| deferred stop handler | hook_deferred_stop.py:291-297 | QUESTION | CRITICAL |
| `_capture_progress_text_impl()` | hook_receiver.py:261-271 | PROGRESS | MEDIUM |

All share the same root cause: Turn creation and state transition in a single transaction, with `db.session.rollback()` in the except block destroying both.

### Solution

Three-tier reliability model where each tier independently guarantees turn capture:

| Tier | Source | Latency | Reliability | Role |
|------|--------|---------|-------------|------|
| 1 | Hooks | <100ms | Unreliable | Fast path — optimistic UI updates |
| 2 | JSONL Transcripts | 2-10s | Authoritative | Gold standard — guarantees completeness |
| 3 | Tmux Pane | ~1s | Visual ground truth | Near-real-time watchdog — bridges "hook didn't fire" to "transcript hasn't arrived" |

**The inversion:** Hooks are the preview. JSONL is the authority. Tmux is the near-real-time early warning. If a hook fails, the tmux watchdog detects the gap within seconds and triggers reconciliation before the JSONL even arrives. The reconciler MUST create the missing turn from the JSONL entry. Additionally, the content hash used for dedup matching is improved from 200-char truncation to full content to eliminate false positive matches.

### Scope

**In Scope:**
- Task 1: Decouple turn persistence from state transitions (all 5 critical locations + 1 medium)
- Task 2: Fix transcript reconciler — ensure missing turns are always created from JSONL
- Task 3: Recovered turns feed into task lifecycle (IntentDetector + state transitions)
- Task 4: State machine audit for missing transitions
- Task 5: Recovery logging (WARNING/INFO/DEBUG levels)
- Task 6: Force reconciliation endpoint + kebab menu button
- Task 7: New Tmux Watchdog service — near-real-time gap detection and early reconciliation trigger
- Task 8: Improve `_content_hash` to use full content instead of first 200 chars

**Out of Scope:**
- Client-side voice chat rendering changes
- Database schema changes (new tables)
- File watcher polling interval changes
- SSE event type definition changes
- Recovery health metrics/dashboard

## Context for Development

### Codebase Patterns

- **Service injection:** Services registered in `app.extensions` and accessed via `app.extensions["service_name"]`
- **Transaction ownership:** TaskLifecycleManager flushes (to get IDs) but NEVER commits. The caller (hook_receiver) owns the final `db.session.commit()`. This is why rollback in hook_receiver destroys everything — it's the transaction owner.
- **InvalidTransitionError propagation:** `update_task_state()` raises `InvalidTransitionError` which propagates to the caller uncaught. `complete_task()` is different — it validates transitions advisorily (log-only), allowing forced completions.
- **SSE broadcasting:** `broadcaster.broadcast(event_type, data)` — turn events use `turn_created` and `turn_updated`
- **Tmux infrastructure:** `tmux_bridge.capture_pane(pane_id, lines=50, timeout=5)` returns string content via subprocess. No caching. Each call spawns a new tmux subprocess. Thread-safe (no shared state).
- **IntentDetector:** Fully standalone — no Flask context, no DB access, thread-safe. `detect_agent_intent(text, inference_service=None)` works from any thread. Regex pipeline handles 95%+ of cases; LLM fallback is optional.
- **Reconciler invocation:** `reconcile_agent_session()` only called at session_end. `reconcile_transcript_entries()` exists for incremental use but nothing calls it mid-session. The file watcher's content pipeline detects questions but does NOT feed the reconciler.
- **Kebab menu:** 5 existing items (Chat, Attach, Fetch context, Agent info, Dismiss). Each uses `.card-kebab-item .card-{name}-action` class + `data-agent-id` attribute. JS handlers use `e.target.closest()` + `closeCardKebabs()` + API call pattern.
- **Route pattern:** Agent endpoints in `routes/agents.py` blueprint. 4 existing endpoints. New reconcile endpoint fits naturally here.

### Files to Reference

| File | Purpose | Key Findings |
| ---- | ------- | ------------ |
| `src/claude_headspace/services/hook_receiver.py` | Hook processing, turn creation | 4 CRITICAL broken pattern locations; single commit at end of each handler |
| `src/claude_headspace/services/hook_deferred_stop.py` | Deferred stop processing | 1 CRITICAL broken pattern (lines 291-326) |
| `src/claude_headspace/services/transcript_reconciler.py` | JSONL -> DB reconciliation | `_infer_intent()` is too naive (user=COMMAND, agent=PROGRESS); `_content_hash` uses only 200 chars |
| `src/claude_headspace/services/task_lifecycle.py` | State transitions, turn records | Flushes but never commits; InvalidTransitionError propagates; complete_task creates Turn internally |
| `src/claude_headspace/services/state_machine.py` | Valid transition definitions | 20 transitions defined; AWAITING_INPUT agent transitions already fixed in 179f87c |
| `src/claude_headspace/services/file_watcher.py` | Watches JSONL, content pipeline | Does NOT call reconciler; content pipeline detects questions only |
| `src/claude_headspace/services/intent_detector.py` | Classifies agent intent | Thread-safe, no Flask context, 10-phase regex pipeline, optional LLM fallback |
| `src/claude_headspace/services/tmux_bridge.py` | `capture_pane()`, `check_health()` | DEFAULT_SUBPROCESS_TIMEOUT=5s; capture_pane(lines=50) default; no caching |
| `src/claude_headspace/services/commander_availability.py` | Tmux health check service | 30s interval, ThreadPoolExecutor, register/unregister pattern — reference for watchdog |
| `src/claude_headspace/routes/agents.py` | Agent API endpoints | 4 endpoints; reconcile endpoint fits after `/context` |
| `templates/partials/_agent_card.html` | Agent card template | Kebab menu lines 134-161; reconcile goes after "Agent info" before divider |
| `static/js/agent-lifecycle.js` | Kebab menu JS handlers | Handler pattern: closest() + getAttribute + closeCardKebabs() + fetch() |

### Technical Decisions

- **Separate commits for turn vs state:** Turn is committed to DB BEFORE state transition is attempted. If state fails, turn survives. This applies to all 5 critical locations, not just process_stop.
- **Reconciler uses IntentDetector:** Recovered turns use `detect_agent_intent()` (thread-safe, no Flask context needed) instead of the naive `_infer_intent()`. Pass `inference_service=None` to skip LLM — regex handles 95%+ of cases.
- **Tmux Watchdog is a new service:** Dedicated `tmux_watchdog.py` with its own daemon thread. Near-real-time cadence (2-5 seconds configurable). Uses `capture_pane(lines=20)` with hash-based change detection for performance. Does not interfere with CommanderAvailability's 30-second health checks.
- **Content hash uses full content:** `_content_hash()` changed from `text[:200]` to full `text` to eliminate false positives on similar-looking turns.
- **No new database tables:** All changes use existing models (Turn, Task, Agent).
- **Deferred stop also fixed:** `hook_deferred_stop.py` has the same broken pattern and must be fixed alongside hook_receiver.

## Implementation Plan

### Tasks

Tasks are ordered by dependency — lowest-level changes first, then consumers of those changes.

- [x] **Task 1: Improve `_content_hash` to use full content**
  - File: `src/claude_headspace/services/transcript_reconciler.py`
  - Action: In `_content_hash()` (line 155), change `text[:200]` to `text` so the hash covers full content instead of first 200 chars. This eliminates false positive matches on turns with similar openings but different bodies.
  - Current: `normalized = f"{actor}:{text[:200].strip().lower()}"`
  - Target: `normalized = f"{actor}:{text.strip().lower()}"`
  - **Hash migration strategy:** Existing `jsonl_entry_hash` values in the DB were computed with the old 200-char hash. New entries will use full-content hashes. To prevent duplicates on first reconciliation after deployment, the reconciler must check BOTH hash formats during matching:
    1. Compute full-content hash (new format) for the JSONL entry
    2. Also compute 200-char hash (old format) for the same entry
    3. Match against DB turns using EITHER hash
    4. Only create a new Turn if NEITHER hash matches any existing Turn
  - Implementation: Add a `_legacy_content_hash()` function that preserves the old `text[:200]` behavior. In `reconcile_transcript_entries()` and `reconcile_agent_session()`, build the `turn_index` / `existing_hashes` set using both old and new hashes for each existing Turn. Match incoming entries against both.
  - After a transition period (e.g., 7 days of running), the legacy hash path can be removed — all new Turns will have full-content hashes.
  - **NULL hash handling:** Some existing Turns may have `jsonl_entry_hash = NULL` (Turns created by hooks before reconciliation ever ran, or Turns from older code paths). The dual-hash lookup builds its match set from `turn.jsonl_entry_hash` values in the DB. NULL values are naturally excluded from the hash set. To prevent the reconciler from creating a duplicate of a NULL-hash Turn, the existing time-window + content matching in `reconcile_transcript_entries()` (which matches by timestamp proximity, not just hash) serves as the fallback dedup mechanism. The hash is the primary dedup; time-window matching is the secondary safety net. This means: a JSONL entry that already has a corresponding Turn (with NULL hash) will still be matched by the time-window logic and won't create a duplicate.
  - Notes: No database migration needed. The dual-hash check is a runtime-only change. Old Turns are matched by their old hashes; new Turns are matched by full-content hashes; NULL-hash Turns are matched by time-window proximity. No duplicates.

- [x] **Task 2: State machine audit for missing transitions**
  - File: `src/claude_headspace/services/state_machine.py`
  - Action: Audit `VALID_TRANSITIONS` dict for missing entries that could cause `InvalidTransitionError` and data loss. Add defensive transitions where the state machine should absorb the turn rather than reject it.
  - Transitions to add:
    - `(TaskState.IDLE, TurnActor.AGENT, TurnIntent.PROGRESS): TaskState.PROCESSING` — agent produces output before user command is processed (race condition)
    - `(TaskState.IDLE, TurnActor.AGENT, TurnIntent.QUESTION): TaskState.AWAITING_INPUT` — agent asks question from idle (session resumption edge case)
    - `(TaskState.IDLE, TurnActor.AGENT, TurnIntent.COMPLETION): TaskState.COMPLETE` — agent completes from idle (deferred completion)
    - `(TaskState.IDLE, TurnActor.AGENT, TurnIntent.END_OF_TASK): TaskState.COMPLETE` — agent ends task from idle
    - `(TaskState.COMMANDED, TurnActor.USER, TurnIntent.COMMAND): TaskState.COMMANDED` — user sends follow-up command before agent responds (already handled in process_turn but not in state machine)
    - `(TaskState.PROCESSING, TurnActor.USER, TurnIntent.COMMAND): TaskState.PROCESSING` — user sends new command while processing (the lifecycle manager handles this as a new task, but the state machine should not reject it if called directly)
  - **Systematic audit methodology:** Enumerate all 60 possible `(state, actor, intent)` combinations (5 states x 2 actors x 6 intents). For each, classify as: (a) already defined — no change, (b) can reasonably occur in production — add transition, (c) nonsensical — keep as invalid. Document the full matrix in a code comment above `VALID_TRANSITIONS`. The 6 transitions listed above are the result of this analysis; verify no others are needed by checking each of the 60 combinations.
  - Notes: The principle is "the state machine should never be the reason a turn is lost." Invalid transitions should log a warning but not raise exceptions that cascade to data loss. However, we keep `InvalidTransitionError` for truly nonsensical transitions — the fix is in the CALLER (Task 3) catching the error gracefully, not in making all transitions valid.

- [x] **Task 3: Decouple turn persistence from state transitions**
  - File: `src/claude_headspace/services/hook_receiver.py`
  - File: `src/claude_headspace/services/hook_deferred_stop.py`
  - Action: Refactor all 5 critical locations so the Turn is committed to the database BEFORE the state transition is attempted. If the state transition fails, the turn survives.
  - **Pattern to apply at each location:**
    ```python
    # 1. Create and persist the turn FIRST
    turn = Turn(task_id=current_task.id, actor=..., intent=..., text=...)
    db.session.add(turn)
    db.session.commit()  # Turn is now safe in DB

    # 2. Broadcast the turn immediately (it exists regardless of state outcome)
    _broadcast_turn_created(agent, turn.text, current_task, turn_id=turn.id, ...)

    # 3. THEN attempt state transition (can fail without data loss)
    try:
        lifecycle.update_task_state(task=current_task, ...)
        db.session.commit()  # State change committed separately
    except InvalidTransitionError as e:
        db.session.rollback()  # Only rolls back the state change, NOT the turn
        logger.warning(
            f"[HOOK_RECEIVER] State transition failed: "
            f"from={current_task.state.value} actor=... intent=... "
            f"error={e} — turn {turn.id} preserved"
        )
    ```
  - **Location 1 — `process_stop()` QUESTION path (hook_receiver.py:1006-1017):**
    - Currently: Turn created at 1006-1013, `update_task_state()` at 1014, single commit at 1043
    - Change: Commit turn immediately after `db.session.add(turn)`, then wrap `update_task_state()` in try/except
  - **Location 2 — `process_stop()` COMPLETION path (hook_receiver.py:1024-1037):**
    - Currently: `lifecycle.complete_task()` creates Turn internally and flushes it, single commit at 1043
    - Change: `complete_task()` already validates transitions advisorily (doesn't raise), so the risk is from OTHER exceptions in the same transaction. Wrap the `complete_task()` + downstream code in a try/except that commits the turn portion first. Since `complete_task()` creates the Turn internally, refactor to: (a) call `complete_task()`, (b) immediately commit to persist the Turn it created, (c) then proceed with summarisation/broadcasting in a separate try/except.
  - **Location 3 — `process_user_prompt_submit()` (hook_receiver.py:798-817):**
    - Currently: `lifecycle.process_turn()` creates Turn(s) internally via `db.session.add()` + `db.session.flush()` (getting IDs), but the actual DB persist happens at the handler's `db.session.commit()` on line 817
    - Change: After `process_turn()` returns, immediately call `db.session.commit()` to persist the Turn(s) that `process_turn()` flushed. This makes them survive any subsequent exception. Then wrap the remaining operations (summarisation queueing, state update to PROCESSING at 808-811, broadcasting) in a separate try/except. Note: `process_turn()` internally calls `flush()` which puts Turns in the session but does NOT commit — the explicit `commit()` after it returns is what persists them to disk.
  - **Location 4 — `_handle_awaiting_input()` (hook_receiver.py:1209-1259):**
    - Currently: Question Turn created at 1209-1218 or 1238-1245, `update_task_state()` at 1249, commit at 1259
    - Change: Commit Turn immediately after creation, then wrap `update_task_state()` in try/except.
  - **Location 5 — deferred stop handler (hook_deferred_stop.py:291-326):**
    - Currently: Turn created at 291-297, `update_task_state()` at 298, commit at 326
    - Change: Same pattern — commit Turn first, wrap state transition in try/except.
  - **Location 6 (MEDIUM) — `_capture_progress_text_impl()` (hook_receiver.py:261-271):**
    - Currently: Turn created and flushed at 270-271, but no explicit commit — caller commits later
    - Change: Add `db.session.commit()` immediately after the flush at line 271 to persist the PROGRESS turn before any downstream processing.
  - **Intentional inconsistency window:** The double-commit pattern creates a brief window where a Turn exists in the DB but the corresponding state transition hasn't happened yet. This is the INTENDED design — a Turn without a state change is recoverable (the reconciler can trigger the state transition later), but a destroyed Turn is permanent data loss. The window is ~1ms (between turn commit and state commit). If a crash occurs in this window, the reconciler will detect the orphaned Turn on next run and apply the state transition.
  - Notes: The key insight is that `db.session.commit()` is called TWICE per handler: once for the turn, once for the state change. The second commit's rollback cannot touch the first commit's data. This adds ~1ms overhead per handler (one extra DB round-trip) — negligible. Existing tests that expect a single transaction should be updated to accommodate the two-commit pattern.

- [x] **Task 4: Recovery logging**
  - Files: All files modified in Tasks 1-3
  - Action: Add structured logging at appropriate levels throughout the modified code.
  - **WARNING level** (every hook processing failure):
    - `[HOOK_RECEIVER] process_stop state transition failed: from={state} actor={actor} intent={intent} error={exception} — turn {turn_id} preserved`
    - `[HOOK_RECEIVER] process_user_prompt_submit state transition failed: error={exception} — turn(s) preserved`
    - `[HOOK_RECEIVER] _handle_awaiting_input state transition failed: error={exception} — turn {turn_id} preserved`
    - `[DEFERRED_STOP] state transition failed: error={exception} — turn {turn_id} preserved`
  - **INFO level** (every recovery action):
    - `[RECONCILER] Created turn {turn_id} from JSONL entry (agent={agent_id}, intent={intent}, hash={hash}) — no matching hook-created turn found`
    - `[RECONCILER] Recovered turn {turn_id} triggered state transition: {from_state} -> {to_state}`
    - `[TMUX_WATCHDOG] Gap detected for agent {agent_id} — new output in pane {pane_id} with no matching turn after {threshold}s, triggering reconciliation`
  - **DEBUG level** (diagnostics):
    - Content hash computation details, match attempts, time windows
    - `[TMUX_WATCHDOG] Agent {agent_id} pane content unchanged`
    - `[TMUX_WATCHDOG] Agent {agent_id} no tmux pane — skipping`
  - Notes: Logging is woven into each task's implementation. This task is listed separately to ensure the log format and levels are consistent across all changes.

- [x] **Task 5: Fix transcript reconciler — create missing turns**
  - File: `src/claude_headspace/services/transcript_reconciler.py`
  - Action: Ensure `reconcile_transcript_entries()` and `reconcile_agent_session()` always create a Turn for JSONL entries with no matching DB record. Fix conditions that could silently skip creation.
  - Changes:
    1. **Widen the match window:** Change `MATCH_WINDOW_SECONDS = 30` to `MATCH_WINDOW_SECONDS = 120` in `reconcile_transcript_entries()`. JSONL writes can be delayed by several seconds, and the 30-second window is too narrow for entries that arrive after a processing delay. 120 seconds is generous enough to catch delayed writes without matching stale turns.
    2. **Add INFO logging for every created turn:** After `db.session.flush()` at line 91, log: `logger.info(f"[RECONCILER] Created turn {turn.id} from JSONL entry (agent={agent.id}, intent={turn.intent.value}, hash={content_key}) — no matching hook-created turn found")`
    3. **Add INFO logging for matched turns:** After timestamp correction at line 73, log: `logger.info(f"[RECONCILER] Updated turn {matched_turn.id} timestamp: {old_ts} -> {entry.timestamp}")`
    4. **Ensure `reconcile_agent_session()` also logs:** Add same INFO log after creating turns at line 228.
  - Notes: The reconciler's core creation logic (lines 78-92) is structurally correct — it creates turns for unmatched entries. The bugs are: (a) the time window is too narrow, (b) nothing calls it mid-session (addressed in Task 7), (c) intent detection is too naive (addressed in Task 6).

- [x] **Task 6: Recovered turns feed into task lifecycle**
  - File: `src/claude_headspace/services/transcript_reconciler.py`
  - Action: Replace the naive `_infer_intent()` with proper `IntentDetector` calls, and feed recovered turns into `TaskLifecycleManager` for state transitions.
  - Changes:
    1. **Replace `_infer_intent()` in `reconcile_transcript_entries()`:** At line 83, replace `intent=_infer_intent(actor, entry)` with:
       ```python
       from .intent_detector import detect_agent_intent, detect_user_intent
       if actor == "user":
           intent_result = detect_user_intent(entry.content.strip(), task.state)
       else:
           intent_result = detect_agent_intent(entry.content.strip(), inference_service=None)
       # Then use intent_result.intent instead of _infer_intent()
       ```
    2. **Replace `_infer_intent()` in `reconcile_agent_session()`:** At line 220, same replacement. For user intent, pass `latest_task.state`. **Caveat:** If `latest_task.state` is COMPLETE (common for historical entries), `detect_user_intent()` will classify as COMMAND (correct — user commands restart task flow). For agent intent, `detect_agent_intent()` is stateless and works regardless of task state.
    3. **Feed recovered turns into TaskLifecycleManager:** After creating a recovered Turn and committing it, call into the lifecycle:
       ```python
       try:
           from flask import current_app
           lifecycle = current_app.extensions.get("task_lifecycle")
           if lifecycle and turn.intent in (TurnIntent.QUESTION, TurnIntent.COMPLETION, TurnIntent.END_OF_TASK):
               if turn.intent == TurnIntent.QUESTION:
                   lifecycle.update_task_state(
                       task=task, to_state=TaskState.AWAITING_INPUT,
                       trigger="reconciler:recovered_turn",
                       confidence=intent_result.confidence,
                   )
               elif turn.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_TASK):
                   lifecycle.complete_task(
                       task=task, trigger="reconciler:recovered_turn",
                       agent_text=turn.text, intent=turn.intent,
                   )
               db.session.commit()
       except InvalidTransitionError as e:
           db.session.rollback()
           logger.warning(f"[RECONCILER] Recovered turn {turn.id} state transition failed: {e} — turn preserved")
       except Exception as e:
           db.session.rollback()
           logger.warning(f"[RECONCILER] Recovered turn {turn.id} lifecycle integration failed: {e}")
       ```
    4. **Broadcast SSE events for recovered turns' state transitions:** After a successful state transition from a recovered turn, broadcast `state_change` event:
       ```python
       from .card_state import broadcast_card_refresh
       from .broadcaster import get_broadcaster
       broadcast_card_refresh(agent, "reconciler")
       ```
    5. **Keep `_infer_intent()` as dead code removal:** Delete the `_infer_intent()` function since it's no longer called.
  - **App context requirement:** The lifecycle integration code uses `current_app.extensions.get("task_lifecycle")`. This requires Flask app context. When called from:
    - **Request context** (force reconcile endpoint): app context is automatic.
    - **Background threads** (file watcher, tmux watchdog): caller MUST wrap in `with self._app.app_context():` before calling reconciliation functions. See Task 8's `_watchdog_loop` for the pattern.
  - Notes: `detect_agent_intent()` is thread-safe and needs no app context. The lifecycle integration is the part that needs context. State transitions from recovered turns use the same try/except pattern from Task 3 — the turn is already committed, so a failed transition doesn't destroy it.

- [x] **Task 7: Force reconciliation endpoint + kebab menu button**
  - File: `src/claude_headspace/routes/agents.py`
  - File: `templates/partials/_agent_card.html`
  - File: `static/js/agent-lifecycle.js`
  - Action: Add a POST endpoint to trigger on-demand reconciliation for a specific agent, and add a "Reconcile" button to the agent card kebab menu.
  - **Endpoint — `routes/agents.py`:**
    ```python
    @agents_bp.route("/api/agents/<int:agent_id>/reconcile", methods=["POST"])
    def reconcile_agent_endpoint(agent_id: int):
        """Manually trigger transcript reconciliation for an agent."""
        from ..models.agent import Agent
        from ..services.transcript_reconciler import reconcile_agent_session, broadcast_reconciliation

        agent = db.session.get(Agent, agent_id)
        if not agent:
            return jsonify({"error": "Agent not found"}), 404

        result = reconcile_agent_session(agent)
        broadcast_reconciliation(agent, result)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "created": len(result["created"]),
        })
    ```
  - **Kebab button — `_agent_card.html`:**
    - Insert after the "Agent info" button (line 154), before `<div class="kebab-divider">`:
    ```html
    <button class="card-kebab-item card-reconcile-action" data-agent-id="{{ agent.id }}">
      <svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 8a7 7 0 0 1 13.4-2.8M15 8a7 7 0 0 1-13.4 2.8"/><path d="M14.4 1v4.2h-4.2M1.6 15v-4.2h4.2"/></svg>
      <span>Reconcile</span>
    </button>
    ```
  - **JS handler — `agent-lifecycle.js`:**
    - Add after the Agent info handler block:
    ```javascript
    var reconcileAction = e.target.closest('.card-reconcile-action');
    if (reconcileAction) {
        e.preventDefault();
        e.stopPropagation();
        var agentId = parseInt(reconcileAction.getAttribute('data-agent-id'), 10);
        closeCardKebabs();
        if (agentId) {
            fetch('/api/agents/' + agentId + '/reconcile', { method: 'POST' })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (global.Toast) {
                        if (data.created > 0) {
                            global.Toast.success('Reconciled', data.created + ' turn(s) recovered');
                        } else {
                            global.Toast.info('Reconcile', 'No missing turns found');
                        }
                    }
                })
                .catch(function() {
                    if (global.Toast) global.Toast.error('Reconcile failed', 'Could not reach server');
                });
        }
        return;
    }
    ```
  - **Concurrency guard:** Use a per-agent lock to prevent concurrent reconciliation (manual endpoint + watchdog racing). Add an in-memory dict `_reconcile_locks: dict[int, threading.Lock]` in the reconciler module. The endpoint and watchdog both acquire the lock before calling `reconcile_agent_session()`. If the lock is already held, the endpoint returns `{"status": "ok", "created": 0, "message": "Reconciliation already in progress"}` immediately (non-blocking trylock). **Critical: Always use try/finally** to ensure lock release even if reconciliation raises an exception:
    ```python
    lock = get_reconcile_lock(agent_id)
    if not lock.acquire(blocking=False):
        return jsonify({"status": "ok", "created": 0, "message": "Reconciliation already in progress"})
    try:
        result = reconcile_agent_session(agent)
        broadcast_reconciliation(agent, result)
        db.session.commit()
    finally:
        lock.release()
    ```
    The same try/finally pattern applies in the Tmux Watchdog (Task 8) when acquiring the lock.
  - **Timeout:** The endpoint must complete within 5 seconds (NFR4 from PRD). For large JSONL files, `reconcile_agent_session()` reads from position 0 which could be slow. Add a safety limit: process at most 500 JSONL entries per call. If more exist, return `{"status": "partial", "created": N, "remaining": M}` and let subsequent calls process the rest.
  - **Error handling:** Wrap `broadcast_reconciliation()` in try/except so broadcast failures don't affect the response. The Turns are already committed regardless.
  - Notes: The `broadcast_reconciliation()` call sends SSE events for created/updated turns so the dashboard updates live. Broadcast failures are logged but don't affect data integrity.

- [x] **Task 8: New Tmux Watchdog service**
  - File: `src/claude_headspace/services/tmux_watchdog.py` (NEW)
  - File: `src/claude_headspace/app.py` (register service)
  - Action: Create a new near-real-time monitoring service that captures tmux pane content, detects new agent output, checks for corresponding DB turns, and triggers early reconciliation when gaps are found.
  - **Service design:**
    ```python
    class TmuxWatchdog:
        def __init__(self, app=None, config=None):
            self._app = app
            self._config = config or {}
            self._stop_event = threading.Event()
            self._thread = None
            self._last_content_hash = {}  # agent_id -> sha256 hash
            self._gap_detected_at = {}    # agent_id -> timestamp of first gap detection
            # Config
            watchdog_config = self._config.get("headspace", {}).get("tmux_watchdog", {})
            self._poll_interval = watchdog_config.get("poll_interval_seconds", 3)
            self._gap_threshold = watchdog_config.get("gap_threshold_seconds", 5)
            self._capture_lines = watchdog_config.get("capture_lines", 20)

        def start(self): ...   # Start daemon thread
        def stop(self): ...    # Stop daemon thread
        def register_agent(self, agent_id, tmux_pane_id): ...
        def unregister_agent(self, agent_id): ...
    ```
  - **Core loop (`_watchdog_loop`):**
    1. Every `poll_interval` seconds (default 3), iterate registered agents
    2. **All DB operations MUST be wrapped in `with self._app.app_context():`** — the watchdog runs in a daemon thread without automatic Flask context. Follow the same pattern as `CommanderAvailability._attempt_reconnection()` (line 169 of commander_availability.py).
    3. For each agent with a `tmux_pane_id`:
       a. Call `tmux_bridge.capture_pane(pane_id, lines=self._capture_lines, timeout=3)`
       b. Compute SHA-256 hash of captured content
       c. Compare against `_last_content_hash[agent_id]`
       d. If hash changed (new output detected):
          - **Within `with self._app.app_context():`:**
          - Query DB for recent agent Turns (last 30 seconds) for this agent
          - Extract a representative snippet from the new pane content (last few non-empty lines)
          - Check if any recent Turn's text contains a significant overlap with the new content
          - If no match found: record gap in `_gap_detected_at[agent_id]`
          - If gap has persisted for `gap_threshold` seconds:
            - Log at INFO: `[TMUX_WATCHDOG] Gap detected for agent {agent_id}...`
            - Acquire per-agent reconcile lock (from Task 7 concurrency guard). If locked, skip (reconciliation already in progress).
            - Trigger reconciliation: call `reconcile_agent_session(agent)` + `broadcast_reconciliation(agent, result)`
            - Clear gap tracker
       e. Update `_last_content_hash[agent_id]`
    4. Agents without `tmux_pane_id`: skip silently (DEBUG log)
  - **Registration & Unregistration:** The watchdog registers/unregisters agents via the same hooks as CommanderAvailability:
    - **Register:** In `hook_receiver.py`'s session_start handler, after `commander_availability.register_agent()`, also call `tmux_watchdog.register_agent(agent_id, tmux_pane_id)`.
    - **Unregister:** In `hook_receiver.py`'s session_end handler, after `commander_availability.unregister_agent()`, also call `tmux_watchdog.unregister_agent(agent_id)`. This clears `_last_content_hash[agent_id]`, `_gap_detected_at[agent_id]`, and `_pane_ids[agent_id]` to prevent memory leaks and stale pane polling.
    - **Also unregister** in the agent reaper (`agent_reaper.py`) when cleaning up inactive agents — same pattern as commander_availability.
  - **App registration** (`app.py`):
    ```python
    from .services.tmux_watchdog import TmuxWatchdog
    watchdog = TmuxWatchdog(app=app, config=config)
    app.extensions["tmux_watchdog"] = watchdog
    watchdog.start()
    ```
  - **Config** (`config.yaml`):
    ```yaml
    headspace:
      tmux_watchdog:
        poll_interval_seconds: 3
        gap_threshold_seconds: 5
        capture_lines: 20
    ```
  - **Graceful degradation:** When tmux is unavailable (agent not in tmux session, or tmux command fails), the watchdog skips that agent silently. The system falls back to JSONL-only reconciliation (Tier 2). Log at DEBUG level.
  - Notes: The watchdog uses `capture_pane(lines=20)` instead of the default 50 for performance. At 3-second intervals across 5-10 agents, that's ~2-3 tmux subprocesses/second — acceptable overhead. Hash-based change detection avoids full string comparison. The gap threshold (5s) ensures we don't trigger reconciliation for content that's in the process of being committed by a hook handler.

### Acceptance Criteria

**Task 1: Content hash improvement**
- [ ] AC 1.1: Given a reconciler processing two JSONL entries with identical first 200 chars but different content after char 200, when matching against DB turns, then each entry gets a unique hash and is treated as a separate turn (no false positive match).
- [ ] AC 1.2: Given an existing Turn in the DB with a 200-char hash (old format), when the reconciler processes the same JSONL entry using the new full-content hash, then the entry is matched via dual-hash lookup (no duplicate created).
- [ ] AC 1.3: Given an existing Turn in the DB with a 200-char hash, when the reconciler processes a genuinely different JSONL entry that happens to share the same first 200 chars, then a new Turn is created (correct behavior with full-content hash).

**Task 2: State machine audit**
- [ ] AC 2.1: Given a task in IDLE state, when an agent produces a PROGRESS turn, then the state machine returns a valid transition to PROCESSING (not InvalidTransitionError).
- [ ] AC 2.2: Given a task in IDLE state, when an agent produces a QUESTION turn, then the state machine returns a valid transition to AWAITING_INPUT.
- [ ] AC 2.3: Given the full set of `(state, actor, intent)` combinations, when validated against the transition table, then no combination that could reasonably occur in production raises InvalidTransitionError.

**Task 3: Decouple turn persistence**
- [ ] AC 3.1: Given `process_stop()` creating a QUESTION Turn, when `update_task_state()` raises `InvalidTransitionError`, then the Turn is still present in the database after the handler completes.
- [ ] AC 3.2: Given `process_stop()` creating a COMPLETION Turn via `complete_task()`, when an exception occurs after Turn creation but before the handler's final commit, then the Turn is still present in the database.
- [ ] AC 3.3: Given `process_user_prompt_submit()` creating a USER COMMAND Turn via `process_turn()`, when an exception occurs during state update or broadcasting, then the Turn is still present in the database.
- [ ] AC 3.4: Given `_handle_awaiting_input()` creating a QUESTION Turn, when `update_task_state()` raises `InvalidTransitionError`, then the Turn is still present in the database.
- [ ] AC 3.5: Given the deferred stop handler creating a Turn, when the state transition fails, then the Turn is still present in the database.
- [ ] AC 3.6: Given any of the above scenarios, when the Turn is preserved but the state transition failed, then a WARNING log entry is emitted with the turn ID, error details, and "turn preserved" message.

**Task 4: Recovery logging**
- [ ] AC 4.1: Given a hook processing failure that preserves a turn, when checking application logs, then a WARNING entry exists with format `[HOOK_RECEIVER] ... — turn {id} preserved`.
- [ ] AC 4.2: Given the reconciler creating a turn from a JSONL entry, when checking application logs, then an INFO entry exists with format `[RECONCILER] Created turn {id} from JSONL entry ...`.
- [ ] AC 4.3: Given the tmux watchdog detecting a gap, when checking application logs, then an INFO entry exists with format `[TMUX_WATCHDOG] Gap detected ...`.

**Task 5: Fix transcript reconciler**
- [ ] AC 5.1: Given a JSONL entry with non-empty content that has no matching Turn in the database, when the reconciler processes it, then a new Turn is created with the correct actor, text, timestamp, and `jsonl_entry_hash`.
- [ ] AC 5.2: Given the reconciler running twice on the same JSONL data, when checking the database, then no duplicate Turns exist (idempotency via `jsonl_entry_hash` dedup).
- [ ] AC 5.3: Given a JSONL entry arriving 45 seconds after the hook-created Turn was rolled back, when the reconciler runs with `MATCH_WINDOW_SECONDS=120`, then the entry is correctly identified as unmatched and a new Turn is created.

**Task 6: Recovered turns feed into lifecycle**
- [ ] AC 6.1: Given the reconciler creating a Turn with intent=QUESTION, when the task lifecycle is invoked, then the agent's task transitions to AWAITING_INPUT.
- [ ] AC 6.2: Given the reconciler creating a Turn with intent=COMPLETION, when the task lifecycle is invoked, then the agent's task transitions to COMPLETE.
- [ ] AC 6.3: Given the reconciler creating a Turn with intent=PROGRESS, when the task lifecycle is invoked, then the agent's task state remains unchanged (PROGRESS is informational, not a state trigger from reconciliation).
- [ ] AC 6.4: Given a recovered turn triggering a state transition, when the transition succeeds, then an SSE `card_refresh` event is broadcast for the agent.
- [ ] AC 6.5: Given a recovered turn triggering a state transition that fails (InvalidTransitionError), when the exception is caught, then the Turn is preserved and a WARNING log is emitted.

**Task 7: Force reconciliation endpoint + UI**
- [ ] AC 7.1: Given a POST to `/api/agents/{id}/reconcile` for a valid agent, when the endpoint completes, then the response contains `{"status": "ok", "created": N}` with the correct count of newly created turns. Note: `reconcile_agent_session()` does not track "updated" turns — it only creates missing ones.
- [ ] AC 7.2: Given a POST to `/api/agents/{id}/reconcile` for a non-existent agent, when the endpoint processes the request, then a 404 response is returned.
- [ ] AC 7.3: Given the reconcile endpoint creating new turns, when SSE clients are connected, then `turn_created` events are broadcast for each new turn.
- [ ] AC 7.4: Given the agent card kebab menu in the dashboard, when the user clicks "Reconcile", then the endpoint is called and a toast notification shows the result.
- [ ] AC 7.5: Given a concurrent reconciliation already in progress for an agent (watchdog or another manual call), when a second POST to `/api/agents/{id}/reconcile` arrives, then the endpoint returns immediately with `{"status": "ok", "created": 0, "message": "Reconciliation already in progress"}` (non-blocking).
- [ ] AC 7.6: Given the reconcile endpoint encountering a broadcast failure after committing turns, when the error is caught, then the response still includes correct `created`/`updated` counts and the turns are preserved.

**Task 8: Tmux Watchdog service**
- [ ] AC 8.1: Given an agent with a `tmux_pane_id` producing new output visible in the pane, when no matching Turn exists in the database after 5 seconds, then the watchdog triggers reconciliation for that agent.
- [ ] AC 8.2: Given an agent without a `tmux_pane_id`, when the watchdog runs its check cycle, then the agent is skipped silently (DEBUG log only).
- [ ] AC 8.3: Given the watchdog triggering reconciliation, when the reconciler creates a new Turn, then the Turn appears in the dashboard via SSE (turn_created event).
- [ ] AC 8.4: Given tmux subprocess calls failing (timeout, tmux not available), when the watchdog encounters the error, then it logs at DEBUG and continues to the next agent (no crash, no data corruption).
- [ ] AC 8.5: Given the watchdog running concurrently with CommanderAvailability, when both access tmux, then neither interferes with the other (no shared state, no lock contention).
- [ ] AC 8.6: Given an agent session ending, when `unregister_agent()` is called on the watchdog, then the agent's pane ID, content hash, and gap tracker are all cleaned up (no memory leak).
- [ ] AC 8.7: Given the watchdog detecting a gap while reconciliation is already in progress for the same agent, when the per-agent lock is held, then the watchdog skips reconciliation for that agent and retries on the next cycle.

## Additional Context

### Dependencies

- PRD: `_bmad-output/planning-artifacts/prd.md`
- Band-aid commit: `179f87c` (added missing AWAITING_INPUT transitions)
- Implementation prompt: `docs/reviews_remediation/turn-capture-reliability-implementation-prompt.md`
- No new external libraries required — all changes use existing dependencies

### Testing Strategy

**Existing tests to run after changes (targeted — do NOT run full suite):**
- `pytest tests/services/test_hook_receiver.py` — Verify happy path not broken by Task 3 refactor
- `pytest tests/services/test_transcript_reconciler.py` — Verify reconciler still matches/creates correctly after Tasks 1, 5, 6
- `pytest tests/services/test_task_lifecycle.py` — Verify lifecycle integration
- `pytest tests/services/test_state_machine.py` — Verify new transitions from Task 2
- `pytest tests/routes/test_hooks.py` — Verify hook endpoint behavior unchanged

**New tests to write:**

| Test | File | What it Verifies |
|------|------|-----------------|
| Turn survives InvalidTransitionError in process_stop | `tests/services/test_hook_receiver.py` | AC 3.1 |
| Turn survives exception after complete_task | `tests/services/test_hook_receiver.py` | AC 3.2 |
| USER Turn survives exception in process_user_prompt_submit | `tests/services/test_hook_receiver.py` | AC 3.3 |
| Turn survives InvalidTransitionError in _handle_awaiting_input | `tests/services/test_hook_receiver.py` | AC 3.4 |
| Reconciler creates Turn for unmatched JSONL entry | `tests/services/test_transcript_reconciler.py` | AC 5.1 |
| Reconciler idempotent — no duplicates on re-run | `tests/services/test_transcript_reconciler.py` | AC 5.2 |
| Recovered QUESTION turn triggers AWAITING_INPUT transition | `tests/services/test_transcript_reconciler.py` | AC 6.1 |
| Recovered COMPLETION turn triggers COMPLETE transition | `tests/services/test_transcript_reconciler.py` | AC 6.2 |
| Failed transition from recovered turn preserves turn | `tests/services/test_transcript_reconciler.py` | AC 6.5 |
| Content hash uses full content (no 200-char false positives) | `tests/services/test_transcript_reconciler.py` | AC 1.1 |
| State machine accepts IDLE + AGENT:PROGRESS | `tests/services/test_state_machine.py` | AC 2.1 |
| State machine accepts IDLE + AGENT:QUESTION | `tests/services/test_state_machine.py` | AC 2.2 |
| Force reconcile endpoint returns correct counts | `tests/routes/test_agents.py` | AC 7.1 |
| Force reconcile endpoint 404 for missing agent | `tests/routes/test_agents.py` | AC 7.2 |
| Tmux watchdog detects gap and triggers reconciliation | `tests/services/test_tmux_watchdog.py` (NEW) | AC 8.1 |
| Tmux watchdog skips agents without tmux pane | `tests/services/test_tmux_watchdog.py` (NEW) | AC 8.2 |
| Tmux watchdog handles tmux failure gracefully | `tests/services/test_tmux_watchdog.py` (NEW) | AC 8.4 |

**Test database:** Tests use `claude_headspace_test` (enforced by `_force_test_database` fixture). Before running: `createdb claude_headspace_test` if it doesn't exist.

### Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Refactoring turn persistence in hook_receiver breaks happy path | High | Run all existing hook_receiver + hook route tests before and after. The refactor adds a commit, it doesn't change turn creation logic. |
| Double-commit overhead (turn commit + state commit) | Low | ~1ms extra per hook handler. Negligible compared to hook processing time (~50-200ms). |
| Reconciler creates duplicate turns | Medium | `jsonl_entry_hash` column provides dedup. Dual-hash lookup (old 200-char + new full-content) prevents duplicates during migration. Per-agent reconcile lock prevents concurrent reconciliation races. |
| Concurrent reconciliation (endpoint + watchdog) | Medium | Per-agent lock with non-blocking trylock. Endpoint returns "already in progress" immediately. Watchdog skips and retries next cycle. |
| Background thread missing app context | High (mitigated) | Watchdog wraps all DB operations in `with self._app.app_context():`. Pattern copied from CommanderAvailability line 169. |
| Tmux watchdog subprocess overhead | Low | `capture_pane(lines=20)` is fast (~10ms). 3-second interval across 5-10 agents = 2-3 subprocesses/second. |
| Tmux watchdog false gap detection | Medium | 5-second gap threshold filters out turns being processed by hooks. Only triggers reconciliation, which is idempotent. |
| State machine audit adds transitions that mask bugs | Low | Only add transitions for scenarios observed in production. Keep InvalidTransitionError for truly nonsensical combinations. The real fix is in the caller (Task 3) catching errors gracefully. |

### Notes

- **Transaction model insight:** The "two-commit" pattern (commit turn, then commit state) is the minimal change. An alternative is SQLAlchemy savepoints (`db.session.begin_nested()`), but savepoints add complexity and have PostgreSQL-specific behavior. Two commits is simpler and more explicit.
- **File watcher gap:** The file watcher polls JSONL and emits `turn_detected` events, but these go to legacy callbacks — they do NOT feed the transcript reconciler. The content pipeline (`check_transcript_for_questions`) only detects questions. The tmux watchdog (Task 8) bridges this gap by triggering reconciliation when new output is detected.
- **Deferred stop:** `hook_deferred_stop.py` runs in a background thread with its own app context. It has the same broken pattern and must be fixed alongside hook_receiver.
- **complete_task() advisory validation:** Unlike `update_task_state()`, `complete_task()` validates transitions advisorily (log-only, doesn't raise). This means the COMPLETION path in process_stop is less likely to fail from InvalidTransitionError, but it can still fail from other exceptions (broadcasting, summarisation) that trigger the outer rollback.
