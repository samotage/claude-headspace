# Project Review Report

**Project:** Claude Headspace v3.1.0
**Date:** 2026-02-07
**Stack:** Python 3.10+ / Flask 3.0+ / PostgreSQL (SQLAlchemy + Alembic) / Vanilla JS + Tailwind CSS 3.x / SSE / OpenRouter LLM / macOS (iTerm2, tmux, terminal-notifier)
**Reviewers:** Database, Frontend, Application Server, External Integration, Test, Technical Writer

## Executive Summary

Claude Headspace is a well-engineered single-developer project with strong architectural fundamentals: clean app factory pattern, well-separated service layer, robust SSE broadcasting, excellent database safety in tests, and graceful degradation throughout. The codebase has grown to 42 services, 22 blueprints, and 10 models serving a sophisticated real-time monitoring dashboard — and for this scale, it holds together remarkably well.

**The most critical cross-cutting concern is state management reliability.** State transitions can bypass the state machine validation, lack database-level locking, and rely on process-local mutable globals that would break under multi-worker deployment. This is the single highest-impact area for hardening. The second major theme is **documentation drift** — the hooks architecture doc is severely stale (wrong port, missing 3 of 8 hooks, wrong state diagram), CLAUDE.md undercounts services and omits key ones, and config defaults are out of sync. The third theme is **frontend code duplication** — three separate markdown renderers with divergent XSS handling, and significant utility function duplication across JS files.

What's working well: database layer design (dual-engine isolation, good indexes, proper cascades), test infrastructure (exemplary DB safety, strong E2E with real browser+SSE), error handling and graceful degradation across all services, and the overall event-driven architecture connecting hooks → state machine → summarisation → SSE → dashboard.

## Cross-Cutting Concerns

### 1. State Machine Integrity Gap
The state machine (`state_machine.py`) is well-designed as a pure validation function, but it's routinely bypassed. The hook receiver and task lifecycle manager set states directly in several code paths (AWAITING_INPUT transitions, stop hook processing) without calling `validate_transition()`. Combined with the absence of database-level pessimistic locking on state transitions, this creates a window for race conditions where concurrent requests (e.g., browser "Respond" click + CLI stop hook) can corrupt task state. This was flagged independently by both the server reviewer (C1, C2) and database reviewer (M3).

### 2. Process-Local Mutable State
Multiple services store critical state in module-level Python dicts: `_awaiting_tool_for_agent` in hook_receiver.py, `_session_cache` in session_correlator.py, `_receiver_state` in hook_receiver.py. While this works for the current single-worker Flask dev server, it creates invisible coupling to that deployment model. Flagged by server reviewer (C3), database reviewer (M2), and integration reviewer (finding 3).

### 3. Documentation-Code Drift
The hooks architecture doc references the wrong port (5050 vs 5055), documents only 5 of 8 hooks, and shows an incorrect 4-state diagram instead of the actual 5-state machine. CLAUDE.md undercounts services (says 37, actual 40) and omits critical ones like HookLifecycleBridge. Config defaults in config.py don't match config.yaml values. The sequence diagram and conceptual overview both omit AWAITING_INPUT. This drift means anyone onboarding from docs will have a materially incorrect mental model. Flagged by tech-writer (C1, C3, H2-H5).

### 4. Frontend Code Duplication and XSS Surface
Three independent markdown-to-HTML renderers exist in project_show.js, help.js, and brain-reboot.js — each with different feature support and different sanitisation approaches. The help.js renderer has a potential XSS vector where URLs pass unsanitised into onclick handlers. Additionally, three separate HTML escape implementations exist (CHUtils.escapeHtml, escapeHtmlBR, config-help's escapeHtml). Chart/metric utility functions are copy-pasted across 3 files. Flagged by frontend reviewer (findings 1, 2, 7, 9, 10).

### 5. Unbounded Growth / Memory Leaks
Several in-memory structures grow without bounds: InferenceCache has no max size or periodic eviction (integration reviewer, finding 2), SSE client queues have no maxsize (integration reviewer, finding 4), file watcher watchdog handlers accumulate without unschedule (integration reviewer, finding 5), and HeadspaceSnapshot has a 3000-day default retention that effectively means no pruning (db reviewer, M5).

## Findings by Severity

### Critical

- **[SRV-C1] Race Condition in State Transitions — No Database Locking** (Reviewer: Server)
  - **Files:** `routes/hooks.py:115-151`, `routes/respond.py:216-234`, `services/hook_receiver.py:586-589,713-716`
  - **Issue:** State transitions occur without pessimistic DB locks. Between lookup and modification, another request can modify the same agent/task. Browser "Respond" + CLI stop hook simultaneously can corrupt state.
  - **Remediation:** Use `db.session.get(Agent, id, with_for_update=True)` for pessimistic locking, or add optimistic locking via version columns.

- **[SRV-C2] State Machine Bypass — Direct State Mutations Skip Validation** (Reviewer: Server)
  - **Files:** `services/hook_receiver.py:586-589,713-716`, `services/task_lifecycle.py:390-395`
  - **Issue:** AWAITING_INPUT transitions and stop hook processing directly set task state without calling `validate_transition()`, allowing invalid state sequences.
  - **Remediation:** Route ALL state transitions through `validate_transition()`. Encode awaiting_input rules into VALID_TRANSITIONS.

- **[FE-C1] XSS via innerHTML in Markdown Renderers** (Reviewer: Frontend)
  - **Files:** `project_show.js:1637-1672`, `help.js:253-339`, `brain-reboot.js:206-256`
  - **Issue:** Three separate ad-hoc markdown renderers convert content to HTML. help.js passes raw URLs into onclick handlers without sanitisation. Subsequent regex replacements re-introduce HTML after initial escaping.
  - **Remediation:** Consolidate into a single shared renderer with a sanitiser (e.g., DOMPurify). Validate all user-supplied values injected into href/onclick.

- **[DB-C1] Duplicate Column in Migration Chain Breaks Fresh Install** (Reviewer: Database)
  - **Files:** `migrations/versions/a1b2c3d4e5f6_make_all_datetime_columns_timezone_aware.py:36`, `migrations/versions/a3c924522879_add_ended_at_column_to_agents.py:22`
  - **Issue:** Migration 2 adds `agents.ended_at` as a side-fix; Migration 3 tries to add it again. Running `flask db upgrade` from scratch will fail with DuplicateColumn.
  - **Remediation:** Remove the `ended_at` column addition from migration 2.

- **[SRV-C7] Unauthenticated Hook API Accepts External Input** (Reviewer: Server)
  - **Files:** `routes/hooks.py:80-159`
  - **Issue:** Hook endpoints validate only JSON format. No rate limiting, no signature verification. Attacker can create fake agents via `/hook/session-start`.
  - **Remediation:** Add rate limiting per source IP; implement HMAC signature verification; validate paths against known project directories.

- **[DOC-C1] Hooks Architecture Doc Severely Stale** (Reviewer: Tech Writer)
  - **Files:** `docs/architecture/claude-code-hooks.md`
  - **Issue:** Wrong port (5050 vs 5055), missing 3 of 8 hooks, wrong 4-state diagram (should be 5-state), missing AWAITING_INPUT transitions.
  - **Remediation:** Rewrite the hooks architecture doc to cover all 8 hooks, correct port, update state machine diagram.

- **[DOC-C2] Default `dashboard_url` Uses Wrong Port** (Reviewer: Tech Writer)
  - **Files:** `src/claude_headspace/config.py`
  - **Issue:** Default `dashboard_url` for notifications is `http://localhost:5050` but server runs on `5055`. Missing config section causes wrong notification URLs.
  - **Remediation:** Update config.py default to `5055`.

- **[SRV-C4] Session Correlator Race — Duplicate Agent Creation** (Reviewer: Server)
  - **Files:** `services/session_correlator.py:256-367`
  - **Issue:** DB lookup + cache set is not atomic. Two hook requests from the same session arriving simultaneously can each create duplicate Agent records.
  - **Remediation:** Add UNIQUE constraint on `claude_session_id` + use `INSERT ... ON CONFLICT ... DO UPDATE`.

### High

- **[INT-H1] Blocking `time.sleep()` in Hook Receiver Stop Processing** (Reviewer: Integration)
  - **Files:** `services/hook_receiver.py:546-553`
  - **Issue:** `process_stop()` calls `time.sleep(0.75)` + `time.sleep(1.0)` inside a Flask request handler, blocking the worker thread and directly delaying Claude Code execution.
  - **Remediation:** Move retry logic to background thread or use non-blocking deferred check.

- **[INT-H2] InferenceCache Grows Unbounded** (Reviewer: Integration)
  - **Files:** `services/inference_cache.py`
  - **Issue:** No maximum size limit, no periodic eviction. Entries only evicted on cache miss. Slow memory leak in long-running server.
  - **Remediation:** Add `max_size` parameter with LRU eviction, or schedule periodic `evict_expired()` calls.

- **[INT-H4] SSE Client Queue Unbounded Memory** (Reviewer: Integration)
  - **Files:** `services/broadcaster.py:23`
  - **Issue:** Each `SSEClient.event_queue` has no maxsize. Stalled clients accumulate events indefinitely.
  - **Remediation:** Initialize `Queue(maxsize=1000)` and use `put_nowait()` with try/except, dropping events for full queues.

- **[DB-H1] N+1 Query in `list_projects()`** (Reviewer: Database)
  - **Files:** `src/claude_headspace/routes/projects.py:77`
  - **Issue:** Queries all projects, then lazy-loads `p.agents` for each. Scales linearly with project count.
  - **Remediation:** Add `selectinload(Project.agents)` or use GROUP BY with LEFT JOIN.

- **[DB-H2] N+1 Query in `get_agent_tasks()`** (Reviewer: Database)
  - **Files:** `src/claude_headspace/routes/projects.py:603`
  - **Issue:** Per-task separate `SELECT COUNT(*)` for turn counts.
  - **Remediation:** Replace with single GROUP BY query.

- **[DB-H3] Pending Summarisation Queue Not Persisted** (Reviewer: Database)
  - **Files:** `services/task_lifecycle.py`, `services/summarisation_service.py`
  - **Issue:** Summarisation requests queued in-memory are lost on server crash/restart.
  - **Remediation:** Persist pending requests to DB table or document as known limitation.

- **[DB-H5] Missing Error Handling in `dismiss_agent()`** (Reviewer: Database)
  - **Files:** `src/claude_headspace/routes/focus.py:172-175`
  - **Issue:** Sets `agent.ended_at` and commits without try-except. Failed commit leaves session dirty with no rollback. Every other DB-writing route properly handles this.
  - **Remediation:** Wrap in try-except with `db.session.rollback()`.

- **[FE-H3] SSE Reconnection Triggers Full Page Reload** (Reviewer: Frontend)
  - **Files:** `dashboard-sse.js:216-225`
  - **Issue:** SSE reconnect calls `window.location.reload()`, causing data loss if user is mid-typing in a respond widget.
  - **Remediation:** Fetch current state via API and apply differential updates, or check for active inputs before reloading.

- **[FE-H4] Race Condition in Respond Widget Initialization** (Reviewer: Frontend)
  - **Files:** `respond-init.js:214-218`
  - **Issue:** Uses hardcoded `setTimeout(initRespondWidgets, 100)` after card_refresh. DOM manipulation may not be complete in 100ms.
  - **Remediation:** Use `requestAnimationFrame` or `MutationObserver`.

- **[FE-H5] No CSRF Protection on Destructive Operations** (Reviewer: Frontend)
  - **Files:** `logging.js:285-301`, `logging-inference.js:322-338`, `projects.js:286-304`, `objective.js:199-258`
  - **Issue:** All DELETE endpoints called via fetch() without CSRF tokens.
  - **Remediation:** Implement CSRF tokens via Flask-WTF or custom header check.

- **[SRV-H1] Broadcaster Thread Safety Violation** (Reviewer: Server)
  - **Files:** `services/broadcaster.py:250-287`
  - **Issue:** `get_broadcaster()` checks `_broadcaster is None` without holding lock. `_running` flag checked without lock in `broadcast()`.
  - **Remediation:** Acquire lock before checking in both functions.

- **[SRV-H5] Dashboard Project Model Lookup Bug** (Reviewer: Server)
  - **Files:** `routes/dashboard.py:258-263`
  - **Issue:** Linear search for project_model doesn't reset to None between iterations. If project ID not found, previous iteration's value is reused, rendering agents under wrong project.
  - **Remediation:** Use dict lookup: `projects_by_id = {p.id: p for p in projects}`.

- **[SRV-H7] Summarisation Error Handling Loses Partial Results** (Reviewer: Server)
  - **Files:** `services/summarisation_service.py:168-210`
  - **Issue:** Single try/except covers inference + parsing + DB commit. If only parsing fails, both summary and frustration_score are lost.
  - **Remediation:** Separate try/except for each step; persist partial results.

- **[TST-H1] NotificationService Has ZERO Test Coverage** (Reviewer: Test)
  - **Files:** `src/claude_headspace/services/notification_service.py` (~160 lines)
  - **Issue:** No test file exists. Thread-safe rate limiting, subprocess execution, message templating are completely untested.
  - **Remediation:** Create `tests/services/test_notification_service.py`.

- **[TST-H3] Route Tests for Inference Are Critically Thin** (Reviewer: Test)
  - **Files:** `tests/routes/test_inference.py` — only 4 tests
  - **Issue:** Inference is a core feature. Only tests 2 GET endpoints with success/503 cases.
  - **Remediation:** Expand to ~20+ tests covering all inference endpoints.

- **[DOC-H5] config.py Defaults Outdated and Missing** (Reviewer: Tech Writer)
  - **Files:** `src/claude_headspace/config.py`
  - **Issue:** `server.port` defaults to 5050 (should be 5055), `server.host` defaults to 127.0.0.1 (yaml uses 0.0.0.0), OpenRouter model defaults reference stale model names, several config sections have no fallback defaults.
  - **Remediation:** Sync config.py defaults with config.yaml values.

- **[DOC-H7] database.user Hardcoded in config.yaml** (Reviewer: Tech Writer)
  - **Files:** `config.yaml`
  - **Issue:** `user: samotage` is non-portable. New developers cloning the repo get connection errors. Setup docs don't mention this.
  - **Remediation:** Change to `postgres` or add setup instructions.

### Medium

- **[INT-M5] File Watcher Watchdog Handlers Accumulate** (Reviewer: Integration)
  - **Files:** `services/file_watcher.py:247`
  - **Issue:** `observer.schedule()` called for new sessions but no `unschedule()` on `unregister_session()`. Stale handlers accumulate.
  - **Remediation:** Store watch objects and call `observer.unschedule(watch)` in cleanup.

- **[INT-M6] Inference Timer Flask App Context Race** (Reviewer: Integration)
  - **Files:** `services/file_watcher.py:461-478`
  - **Issue:** Timer threads don't inherit Flask contexts. Inference classification silently fails when timer fires.
  - **Remediation:** Pass Flask app reference and use `app.app_context()` in callback.

- **[INT-M7] Transcript Reader Reads Entire File Into Memory** (Reviewer: Integration)
  - **Files:** `services/transcript_reader.py:78`
  - **Issue:** `f.readlines()` loads entire transcript. Claude Code transcripts can grow very large.
  - **Remediation:** Read in reverse chunks from EOF.

- **[INT-M10] Commander Availability Sequential Health Checks** (Reviewer: Integration)
  - **Files:** `services/commander_availability.py:186-199`
  - **Issue:** Serial tmux subprocess calls. With N agents and slow tmux, blocks for N x timeout seconds.
  - **Remediation:** Use ThreadPoolExecutor for parallel checks.

- **[DB-M1] No DB Constraint on ActivityMetric Scope** (Reviewer: Database)
  - **Files:** `src/claude_headspace/models/activity_metric.py`
  - **Issue:** No CHECK constraint ensuring exactly one of (agent_id, project_id, is_overall) is set.
  - **Remediation:** Add CHECK constraint in migration.

- **[DB-M5] HeadspaceSnapshot Unbounded Growth** (Reviewer: Database)
  - **Files:** `services/headspace_monitor.py`
  - **Issue:** Default 3000-day retention means effectively no pruning. 556 snapshots already.
  - **Remediation:** Set more aggressive retention (30-90 days) or downsample old snapshots.

- **[FE-M7] Excessive Code Duplication Across JS Modules** (Reviewer: Frontend)
  - **Files:** `activity.js`, `project_show.js`, `dashboard-sse.js`
  - **Issue:** `_fillHourlyGaps()`, `_aggregateByDay()`, `_weightedAvgTime()`, `_sumTurns()` copy-pasted across 2-3 files each.
  - **Remediation:** Extract shared utilities into `utils.js`.

- **[FE-M8] Inconsistent JS Module Patterns** (Reviewer: Frontend)
  - **Files:** All JS files
  - **Issue:** Mixes IIFE with global parameter, IIFE with no parameter, revealing module pattern, and bare global functions. Mixed var/let/const.
  - **Remediation:** Standardize on one pattern. Namespace brain-reboot.js globals.

- **[SRV-M2] N+1 Queries in Card State** (Reviewer: Server)
  - **Files:** `services/card_state.py:561-622`
  - **Issue:** `build_card_state()` calls `agent.get_current_task()` 5+ times per agent, each executing a fresh SQL query. 50 agents = 250+ queries.
  - **Remediation:** Cache task lookup per card build, or eager-load tasks.

- **[SRV-M5] Pagination Bounds Missing** (Reviewer: Server)
  - **Files:** `routes/projects.py:174-188`, `routes/logging.py:58-64`, `routes/objective.py:204-210`
  - **Issue:** `per_page` capped at max 100 but no minimum validation. Negative/zero values pass to SQLAlchemy.
  - **Remediation:** Validate minimum bounds.

- **[SRV-M7] Inconsistent Response Status Codes** (Reviewer: Server)
  - **Files:** `routes/focus.py:108`, `routes/respond.py:149`
  - **Issue:** Same error type (missing pane ID) returns 500 in one route and 400 in another.
  - **Remediation:** Standardize error codes.

- **[SRV-M8] Inconsistent Error Response Format** (Reviewer: Server)
  - **Files:** Various routes
  - **Issue:** Routes return `{"error": "..."}`, `{"status": "error", "message": "..."}`, or `{"ok": false, "reason": "..."}` inconsistently.
  - **Remediation:** Adopt a standard error response format across all routes.

- **[TST-M6] Route Tests Mock DB So Heavily That SQLAlchemy Bugs Won't Surface** (Reviewer: Test)
  - **Files:** Multiple route tests
  - **Issue:** Route tests mock `db.session` with chained MagicMocks. Real query construction errors, lazy/eager loading issues never surface.
  - **Remediation:** Add integration tests exercising routes with real database.

- **[TST-M11] Integration Tests Don't Test Cross-Service Flows** (Reviewer: Test)
  - **Files:** `tests/integration/`
  - **Issue:** No tests exercise hook → correlator → lifecycle → summarisation → card state → SSE broadcast with real services.
  - **Remediation:** Add integration tests for full hook processing flow.

- **[DOC-C3] CLAUDE.md Service Count and Coverage Wrong** (Reviewer: Tech Writer)
  - **Files:** `CLAUDE.md`
  - **Issue:** States "37 service modules" (actual: 40). Omits HookLifecycleBridge, TranscriptReader, OpenRouterClient, PermissionSummarizer, and 7 other services from Key Services section.
  - **Remediation:** Update count and add missing services.

- **[DOC-M1] Sequence Diagram Missing AWAITING_INPUT** (Reviewer: Tech Writer)
  - **Files:** `docs/diagrams/full-cycle-sequence-diagram.md`
  - **Issue:** Only shows IDLE→COMMANDED→PROCESSING→COMPLETE. Missing pre/post-tool-use and AWAITING_INPUT cycles.
  - **Remediation:** Add AWAITING_INPUT transitions to diagram.

- **[DOC-M2] Conceptual Overview Missing END_OF_TASK Intent** (Reviewer: Tech Writer)
  - **Files:** `docs/conceptual/claude_headspace_v3.1_conceptual_overview.md`
  - **Issue:** Lists 5 intents, actual enum has 6 (missing END_OF_TASK).
  - **Remediation:** Add END_OF_TASK to intent list and mapping table.

### Low

- **[INT-L13] Notification Service Global Singleton Not Thread-Safe** (Reviewer: Integration)
  - **Files:** `services/notification_service.py:185-199`
  - **Issue:** Two threads could create two instances simultaneously (harmless race, one discarded).
  - **Remediation:** Add threading lock or document as intentional.

- **[INT-L15] iTerm Focus AppleScript O(n^3) Search** (Reviewer: Integration)
  - **Files:** `services/iterm_focus.py:68-108`
  - **Issue:** Triple-nested loop through all windows/tabs/sessions. Slow with many iTerm windows.
  - **Remediation:** Cache pane-to-session mapping or use iTerm Python API.

- **[INT-L16] Config Editor Password in Plaintext YAML** (Reviewer: Integration)
  - **Files:** `services/config_editor.py:96`
  - **Issue:** DB password stored in plaintext config.yaml with no file permission enforcement.
  - **Remediation:** Set file permissions to 0600 after save, or document expected permissions.

- **[INT-L18] Install Script Modifies Settings Without Backup** (Reviewer: Integration)
  - **Files:** `bin/install-hooks.sh:328-359`
  - **Issue:** Modifies `~/.claude/settings.json` in-place. Interrupted write could corrupt file.
  - **Remediation:** Add backup before modification.

- **[INT-L20] Project Decoder Lossy for Paths with Dashes** (Reviewer: Integration)
  - **Files:** `services/project_decoder.py:6-31`
  - **Issue:** Dashes in paths decode as slashes. Claude Code upstream limitation, not fully reversible.
  - **Remediation:** Document the limitation.

- **[DB-L1] No Temporal CHECK Constraints** (Reviewer: Database)
  - **Files:** All models with started_at/completed_at pairs
  - **Issue:** No DB constraint ensuring `completed_at >= started_at`.
  - **Remediation:** Add CHECK constraints in future migration.

- **[DB-L4] Redundant Timestamps on HeadspaceSnapshot** (Reviewer: Database)
  - **Files:** `models/headspace_snapshot.py`
  - **Issue:** Both `timestamp` and `created_at` always have the same value.
  - **Remediation:** Remove `created_at` in cleanup migration.

- **[FE-L17] Multiple SSE Event Type Aliases** (Reviewer: Frontend)
  - **Files:** `dashboard-sse.js:229-248`
  - **Issue:** `state_changed`/`state_transition`/`agent_state_changed` all map to same handler. Unclear which is canonical.
  - **Remediation:** Standardize event names server-side and document.

- **[SRV-L5] Cache Bust Regenerated Per-Render** (Reviewer: Server)
  - **Files:** `app.py:277-280`
  - **Issue:** `int(time.time())` regenerated on every template render. Should be set once at startup.
  - **Remediation:** Set once during app factory creation.

- **[SRV-L8] Excessive Logging in Hot Paths** (Reviewer: Server)
  - **Files:** `card_state.py:259-294`, `intent_detector.py:393-422`
  - **Issue:** INFO-level logs on every card_refresh and intent detection. ~7200 lines/hour with 20 agents.
  - **Remediation:** Reduce to DEBUG level.

- **[TST-L2] Root conftest `temp_config` Fixture is Dead Code** (Reviewer: Test)
  - **Files:** `tests/conftest.py:61-78`
  - **Issue:** `app` fixture takes `temp_config` as parameter but never uses it. Wasted setup on every test.
  - **Remediation:** Either use it in `create_app()` or remove the dependency.

- **[DOC-L1] Dashboard Help Missing Kanban Sort Mode** (Reviewer: Tech Writer)
  - **Files:** `docs/help/dashboard.md`
  - **Issue:** Only documents "By Project" and "By Priority". Missing "Kanban" (default mode).
  - **Remediation:** Add Kanban to sort modes documentation.

- **[DOC-M9] CLI Shebang Hardcoded to Dev Environment** (Reviewer: Tech Writer)
  - **Files:** `bin/claude-headspace`
  - **Issue:** Shebang `#!/Users/samotage/dev/.../venv/bin/python3` is non-portable.
  - **Remediation:** Change to `#!/usr/bin/env python3`.

## Module Alignment Assessment

**Overall alignment is good.** The codebase follows consistent patterns in most areas:
- Services are registered in `app.extensions` and accessed uniformly
- Database transactions follow try-except-rollback pattern (with one exception: `dismiss_agent`)
- SSE broadcasts happen after `db.session.commit()` consistently
- Background threads use `threading.Event()` for shutdown signaling
- Error handling degrades gracefully without crashing the server

**Areas of divergence:**

1. **State transition paths:** The state machine exists as a clean validation layer, but at least 3 code paths bypass it entirely (AWAITING_INPUT via hook_receiver, stop hook, and task_lifecycle direct sets). This is the most significant alignment issue — the state machine should be the single authority.

2. **Error response format:** Routes return errors in 3+ different JSON shapes (`{"error": ...}`, `{"status": "error", ...}`, `{"ok": false, ...}`). This makes client-side error handling inconsistent.

3. **Frontend module patterns:** JS files use 4 different module patterns (IIFE with global, IIFE without, revealing module, bare globals). utility functions are duplicated across files rather than shared. Three independent markdown renderers exist.

4. **Config defaults vs config.yaml:** config.py defaults have drifted from config.yaml values (port 5050 vs 5055, host 127.0.0.1 vs 0.0.0.0, stale model names). Several newer config sections have no fallback defaults at all.

5. **DB interaction patterns:** Most services use Flask-SQLAlchemy's `db.session`, but EventWriter and InferenceService use independent engines. This is intentional (isolation) but not well-documented and could confuse contributors.

## Recommendations

### Phase 1 — Critical Fixes (Immediate)

1. **Harden state transitions:** Route ALL state changes through `validate_transition()`. Add AWAITING_INPUT rules to VALID_TRANSITIONS. Add `with_for_update=True` for pessimistic locking on state-changing queries. *(SRV-C1, SRV-C2, SRV-M3)*

2. **Fix migration chain for fresh installs:** Remove duplicate `ended_at` column addition from the timezone-awareness migration. *(DB-C1)*

3. **Fix XSS in markdown renderers:** Consolidate three renderers into a single `CHUtils.renderMarkdown()` with proper sanitisation. *(FE-C1, FE-C2)*

4. **Sync config.py defaults with config.yaml:** Fix wrong port (5050→5055), wrong host, stale model names, add missing section defaults. *(DOC-C2, DOC-H5)*

### Phase 2 — High-Impact Improvements (This Sprint)

5. **Bound in-memory structures:** Add maxsize to InferenceCache, SSE client queues, and add watchdog handler cleanup. *(INT-H2, INT-H4, INT-M5)*

6. **Fix N+1 queries:** Add eager loading for projects→agents, task→turns, and cache `get_current_task()` in card_state builds. *(DB-H1, DB-H2, SRV-M2)*

7. **Fix dashboard project lookup bug:** Use dict lookup instead of linear search to prevent agents rendering under wrong project. *(SRV-H5)*

8. **Remove blocking sleeps from hook receiver:** Move transcript retry to background thread. *(INT-H1)*

9. **Add rate limiting to hook endpoints:** Prevent abuse of unauthenticated hook API. *(SRV-C7)*

10. **Write NotificationService tests:** Zero coverage on a core service with threading, subprocesses, and rate limiting. *(TST-H1)*

### Phase 3 — Documentation and Consistency (Backlog)

11. **Rewrite hooks architecture doc:** Cover all 8 hooks, correct port, update state diagram, document AWAITING_INPUT. *(DOC-C1)*

12. **Update CLAUDE.md:** Fix service count (40), add missing Key Services (HookLifecycleBridge, TranscriptReader, OpenRouterClient, PermissionSummarizer), update event types, fix rate limit values. *(DOC-C3, DOC-H3, DOC-M6)*

13. **Standardise error response format:** Adopt `{"error": string, "detail": optional}` across all routes. *(SRV-M7, SRV-M8)*

14. **Consolidate frontend utilities:** Extract duplicated chart/metric functions to utils.js. Standardise JS module pattern. *(FE-M7, FE-M8)*

15. **Expand thin route tests:** Inference (4 tests → 20+), projects page (3 tests → 15+), summarisation (10 tests → 25+). *(TST-H3, TST-H4, TST-H7)*

### Phase 4 — Tech Debt (Opportunistic)

16. **Add cross-service integration tests** for hook→lifecycle→summarisation→SSE flow. *(TST-M11)*
17. **Fix Flask app context in timer callbacks** (file_watcher inference timer). *(INT-M6)*
18. **Add CSRF protection** for destructive endpoints. *(FE-H5, SRV-H4)*
19. **Fix portable setup:** Change config.yaml db user, fix CLI shebang, update README stats. *(DOC-H7, DOC-M9, DOC-H2)*
20. **Reduce hot-path logging** to DEBUG level. *(SRV-L8)*
