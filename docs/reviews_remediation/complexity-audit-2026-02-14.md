# Complexity Audit Report

**Date:** 2026-02-14
**Scope:** Services only (`src/claude_headspace/services/` — 50 files, 17,075 lines)
**Depth:** Quick scan
**Focus patterns:** All (abstraction without payoff, deep call chains, parallel mechanisms, state management sprawl, defensive complexity, configuration-driven indirection)

## Executive Summary

The services layer is **moderately over-engineered** for a single-developer project. The total codebase is 17,075 lines across 50 service files (including `__init__.py`). The core complexity tax comes from three sources:

1. **Dead code and unused abstractions.** `hook_lifecycle_bridge.py` (535 lines) is completely unused — `hook_receiver.py` bypasses it and calls `task_lifecycle.py` directly. `process_monitor.py` (181 lines) is exported but never called from production code. These add cognitive load and maintenance surface for zero value.

2. **Parallel monitoring mechanisms.** The file watcher system (`file_watcher.py` + `jsonl_parser.py` + `session_registry.py` = ~1,010 lines) was the original monitoring path before Claude Code hooks were implemented. Hooks are now the primary path, but the file watcher still runs in production, processing the same events through a separate pipeline. This creates two competing state channels.

3. **Hook receiver sprawl.** The hook processing pipeline spans 6 tightly-coupled modules (`hook_receiver.py`, `hook_helpers.py`, `hook_extractors.py`, `hook_agent_state.py`, `hook_deferred_stop.py`, plus `task_lifecycle.py`) totalling ~2,891 lines. The decomposition into helpers/extractors was done for testability, but the modules are so tightly coupled that they're effectively one module split across files. The ~240-line `hook_helpers.py` is pure pass-through facade.

The estimated complexity tax is **15-20%** — meaning changes to hook processing, state management, or the intelligence layer take roughly 15-20% longer than they should due to unnecessary indirection, dead code to navigate around, and parallel systems to reason about.

## Service Dependency Graph

| Service | Lines | Deps | Dependents | Flags |
|---------|-------|------|------------|-------|
| hook_receiver | 1,223 | 7 services | routes/hooks | **Hub** — largest service, orchestrates 8 hook types |
| tmux_bridge | 1,074 | 0 | routes/respond, commander_availability, agent_reaper | Utility — large but self-contained |
| summarisation_service | 826 | 3 (inference, prompts, broadcaster) | hook_helpers, routes | **Hub** — 5 summarisation types |
| config_editor | 675 | 0 | routes/config | Self-contained — large schema registry |
| card_state | 670 | 0 | 6+ callers (routes, reaper, hooks) | Helper library — stateless, justified size |
| file_watcher | 654 | 7 (session_registry, git_metadata, jsonl_parser, project_decoder, prompt_registry, transcript_reader, intent_detector) | app.py (startup only) | **Parallel mechanism** — legacy monitoring |
| intent_detector | 600 | 1 (prompt_registry) | hook_receiver, task_lifecycle, file_watcher | Heuristic classifier — 70+ regex patterns |
| task_lifecycle | 565 | 3 (event_writer, state_machine, intent_detector) | hook_receiver | **Core** — state machine orchestrator |
| session_correlator | 542 | 1 (card_state) | hook_receiver | Session mapper — 4-strategy cascade |
| hook_lifecycle_bridge | 535 | 3 (event_writer, task_lifecycle, intent_detector) | **NONE** | **Dead code** — completely unused |
| headspace_monitor | 498 | 1 (broadcaster) | routes, summarisation | Stateful — rolling windows, alerts |
| iterm_focus | 497 | 0 | agent_reaper, routes/focus | Self-contained — AppleScript wrapper |
| permission_summarizer | 493 | 0 | hook_extractors | Self-contained — command classifier |
| agent_reaper | 439 | 3 (iterm_focus, card_state, hook_helpers) | app.py (background thread) | Background service |
| inference_service | 429 | 3 (cache, rate_limiter, client) | 54 accesses — **most-accessed hub** |
| priority_scoring | 383 | 3 (inference, prompts, waypoint_editor) | hook_helpers, routes | Debounced async scoring |
| agent_lifecycle | 382 | 2 (tmux_bridge, context_parser) | routes | Agent creation orchestrator |
| activity_aggregator | 381 | 0 (direct DB) | app.py (background thread) | Background service |
| broadcaster | 364 | 0 | **141 accesses** — most-depended-on service | **Hub** — SSE distribution |
| git_analyzer | 336 | 1 (config) | progress_summary | Subprocess-based git analysis |
| archive_service | 308 | 1 (path_constants) | brain_reboot, waypoint_editor, routes | Artifact archiving |
| progress_summary | 306 | 3 (git_analyzer, inference, prompts) | routes/projects | LLM + git orchestrator |
| brain_reboot | 283 | 1 (path_constants) | routes/projects | File composition — no LLM |
| hook_deferred_stop | 256 | 5 (agent_state, helpers, intent, card_state, transcript_reader) | hook_receiver | Background worker for race condition |
| transcript_reader | 257 | 0 | hook_deferred_stop, hook_helpers, file_watcher | Tail-based .jsonl reader |
| waypoint_editor | 244 | 1 (archive_service) | routes/projects, priority_scoring | Thin file I/O wrapper |
| file_upload | 242 | 0 | routes/voice | File storage + validation |
| hook_helpers | 239 | 4 (task_lifecycle, broadcaster, notification, transcript_reader) | hook_receiver, hook_deferred_stop, agent_reaper | **Thin facade** — pass-through wrappers |
| prompt_registry | 232 | 0 | summarisation, priority, progress, file_watcher, intent_detector | Static template dict |
| event_schemas | 220 | 0 | event_writer, hook_receiver | Schema definitions |
| commander_availability | 218 | 1 (tmux_bridge) | routes, card_state | Background health checker |
| hook_agent_state | 206 | 0 | hook_receiver, hook_deferred_stop | **State holder** — thread-safe per-agent state |
| notification_service | 202 | 0 | hook_helpers, routes | macOS notifications |
| event_writer | 200 | 1 (event_schemas) | task_lifecycle, hook_receiver, agent_reaper | Persistence with independent DB engine |
| git_metadata | 189 | 0 | file_watcher, routes | Cached git info |
| jsonl_parser | 184 | 0 | file_watcher only | **Single-caller** — legacy pipeline |
| process_monitor | 181 | 0 | **__init__.py only** | **Orphan** — exported but never called |
| session_registry | 172 | 0 | file_watcher, hook_agent_state | **Parallel mechanism** — CLI registration path |
| voice_formatter | 160 | 0 | routes/voice | Response formatting |
| hook_extractors | 160 | 2 (permission_summarizer, tmux_bridge) | hook_receiver | Extraction utilities |
| state_machine | 140 | 0 | task_lifecycle | Pure validator — log-only (not enforced) |
| voice_auth | 119 | 0 | routes/voice | Token auth + rate limiting |
| inference_cache | 119 | 0 | inference_service | LRU cache with TTL |
| staleness | 115 | 0 | brain_reboot, routes | Freshness classification |
| __init__.py | 104 | all | all | Package exports |
| inference_rate_limiter | 101 | 0 | inference_service | Sliding window limiter |
| project_decoder | 99 | 0 | file_watcher, routes | Stateless path encoding |
| context_parser | 49 | 0 | agent_lifecycle | Regex extraction |
| path_constants | 24 | 0 | archive_service, brain_reboot, progress_summary | Pure constants |

## Findings

Sorted by impact (highest first):

### [DEAD CODE] hook_lifecycle_bridge.py is completely unused

- **Files:** `src/claude_headspace/services/hook_lifecycle_bridge.py:1-535`
- **Impact:** 535 lines of code that no production code imports. `hook_receiver.py` imports `task_lifecycle.py` directly (line 39). The bridge exists only in its own file and its test (`tests/services/test_hook_lifecycle_bridge.py`). Developers must understand why two paths exist and which one is live. New contributors may accidentally use the bridge thinking it's the active path.
- **Current state:** Adapter that translates hook events into task lifecycle operations. Contains duplicated logic for stop processing, text deduplication, and transcript extraction that mirrors `hook_receiver.py`.
- **Simpler alternative:** Delete `hook_lifecycle_bridge.py` and its test. If the adapter pattern is needed in the future, it can be recreated from the git history.
- **Risk:** None — it's unused. Verify with `grep -r "hook_lifecycle_bridge\|HookLifecycleBridge" src/` (only hits itself).
- **Effort:** Low

### [PARALLEL MECHANISMS] File watcher and hooks monitor overlapping state

- **Files:** `services/file_watcher.py` (654 lines), `services/jsonl_parser.py` (184 lines), `services/session_registry.py` (172 lines)
- **Impact:** Two independent monitoring pipelines process session state: (1) hooks fire HTTP requests on lifecycle events (the primary path), and (2) file watcher polls `.jsonl` files and transcripts for changes. Both detect turns, questions, and session activity. The file watcher pulls in 7 service dependencies and runs background threads with debouncing, timers, and watchdog observers. When both systems fire on the same event, the duplication must be handled defensively.
- **Current state:** File watcher runs as a background thread in production alongside the hook system. It was the original monitoring approach before Claude Code hooks existed.
- **Simpler alternative:** If hooks are reliable, the file watcher can be demoted to a fallback-only role (disabled by default, enabled via config flag for environments where hooks fail). This removes ~1,010 lines from the active codepath and eliminates a class of state-synchronization bugs. The `session_registry.py` (CLI registration path) may still be needed for the `claude-headspace start` command but could be simplified.
- **Risk:** Medium — some environments or edge cases may depend on file watcher as primary. Needs testing with file watcher disabled to confirm hook coverage is sufficient.
- **Effort:** Medium

### [ABSTRACTION WITHOUT PAYOFF] hook_helpers.py is a pass-through facade

- **Files:** `src/claude_headspace/services/hook_helpers.py:1-239`
- **Impact:** Every function in this module is a thin wrapper that gets a service from `app.extensions` and calls one method on it. Example: `broadcast_state_change()` just calls `get_broadcaster().broadcast()`. `get_lifecycle_manager()` just instantiates `TaskLifecycleManager(db.session, event_writer)`. These add an indirection layer that obscures which service is actually being called, making debugging harder. Callers must look through the facade to understand what's actually happening.
- **Current state:** 9 functions, each 5-15 lines, wrapping direct service calls.
- **Simpler alternative:** Inline these calls at their 3 call sites (`hook_receiver.py`, `hook_deferred_stop.py`, `agent_reaper.py`). The callers already have Flask app context and can access `current_app.extensions` directly — which is what every other service in the codebase does.
- **Risk:** Low — mechanical refactoring. The test for hook_helpers can be removed too.
- **Effort:** Low

### [DEEP CALL CHAINS] Hook processing traverses 6+ service boundaries

- **Files:** `hook_receiver.py` → `hook_helpers.py` → `task_lifecycle.py` → `state_machine.py` + `intent_detector.py` → `event_writer.py` → `broadcaster.py` → `card_state.py`
- **Impact:** A single hook event (e.g., `process_stop()`) passes through 6-8 service boundaries. Debugging a state transition bug requires tracing through `hook_receiver` → `hook_helpers.get_lifecycle_manager()` → `TaskLifecycleManager.process_turn()` → `StateMachine.validate_transition()` → `EventWriter.write_event()` → `Broadcaster.broadcast()`. Each boundary has its own error handling, logging, and None-guards. When something fails silently in the middle, the debugging surface is large.
- **Current state:** The decomposition was done for testability, but the tight coupling between modules means they can't be tested in true isolation anyway — `hook_receiver` tests need to mock 7 service dependencies.
- **Simpler alternative:** After inlining `hook_helpers`, the chain shortens to: `hook_receiver` → `task_lifecycle` → `state_machine` + `intent_detector` → `event_writer` → `broadcaster`. The elimination of the facade removes one hop from every call. Further consolidation of `hook_extractors` (160 lines) into `hook_receiver` would eliminate another boundary.
- **Risk:** Low — reduces indirection without changing behavior.
- **Effort:** Low-Medium

### [STATE MANAGEMENT SPRAWL] Per-agent state tracked in 3+ locations

- **Files:** `hook_agent_state.py` (in-memory dicts), `models/agent.py` + `models/task.py` (database), `session_correlator.py` (session cache), `commander_availability.py` (availability cache)
- **Impact:** Agent state is tracked in: (1) `AgentHookState` — 6 in-memory dicts for transient hook processing state, (2) database Agent/Task/Turn models for persistent state, (3) `session_correlator._session_cache` for session-to-agent mapping, (4) `commander_availability._availability` for tmux health, (5) `git_metadata._cache` for repo info, (6) `iterm_focus._pane_cache` for pane existence. When an agent is reaped, all caches must be manually invalidated. If any cache diverges from the database, the dashboard shows stale data.
- **Current state:** `AgentHookState.on_session_end()` clears hook state, but doesn't touch session_correlator cache or commander_availability cache. The agent_reaper handles some cleanup but the cache invalidation is scattered.
- **Simpler alternative:** Centralize cache invalidation in a single `agent_cleanup(agent_id)` function called from reaper and session-end processing. This doesn't eliminate the caches (they serve valid performance purposes) but ensures they're invalidated consistently.
- **Risk:** Low — additive change, doesn't remove caches.
- **Effort:** Low

### [ORPHAN] process_monitor.py is exported but never used

- **Files:** `src/claude_headspace/services/process_monitor.py:1-181`
- **Impact:** Exported in `__init__.py` but not imported or called anywhere in `src/` outside of the init. 181 lines of PID file management and health checking with no callers.
- **Current state:** Defines `ProcessMonitor` class and module-level `write_pid_file()`/`remove_pid_file()` functions for tracking a watcher process.
- **Simpler alternative:** Delete. If PID file management is needed later, it's a simple utility to recreate.
- **Risk:** None — no callers.
- **Effort:** Low

### [DEFENSIVE COMPLEXITY] State machine validates but doesn't enforce

- **Files:** `src/claude_headspace/services/state_machine.py:1-140`, `src/claude_headspace/services/task_lifecycle.py` (validation call sites)
- **Impact:** The state machine defines 48 valid transitions and has a `validate_transition()` function, but `task_lifecycle.py` only logs warnings on invalid transitions — it never blocks them. This means the state machine is documentation-as-code (valuable) but the validation infrastructure (function signatures, return types, error messages) is heavier than needed for a log-only check.
- **Current state:** `task_lifecycle.py` calls `validate_transition()`, logs the result, then proceeds regardless. The defensive posture was likely chosen because blocking invalid transitions during development would cause hard failures.
- **Simpler alternative:** Either (a) enforce transitions (raise on invalid, handle in callers) to get the full value of the state machine, or (b) simplify to a lookup + log (reduce the validation infrastructure). The current middle ground has the maintenance cost of both approaches and the reliability benefits of neither.
- **Risk:** (a) may surface hidden bugs that are currently swallowed; (b) loses future enforcement option.
- **Effort:** Low

### [PARALLEL MECHANISMS] Dual singleton patterns for broadcaster and notification_service

- **Files:** `services/broadcaster.py` (global `_broadcaster` + `app.extensions["broadcaster"]`), `services/notification_service.py` (global `_notification_service` + `app.extensions["notification_service"]`)
- **Impact:** These services are registered in `app.extensions` AND maintained as module-level global singletons. Code accesses them through both patterns: 141 references to broadcaster, most via `get_broadcaster()` global, some via `app.extensions`. This creates two paths to the same object and makes it unclear which is canonical.
- **Current state:** The dual pattern is intentional — SSE connections need the broadcaster to persist across Flask request contexts. However, the `app.extensions` registration is redundant for these two services since nothing accesses them that way in production.
- **Simpler alternative:** Pick one pattern. Since these services need to outlive request context, the global singleton is correct. Remove the `app.extensions` registration (or keep it only for shutdown cleanup) and standardize all access through `get_broadcaster()` / `get_notification_service()`.
- **Risk:** Low — access pattern consolidation.
- **Effort:** Low

### [CONFIGURATION-DRIVEN INDIRECTION] Prompt registry is a static dict pretending to be a service

- **Files:** `src/claude_headspace/services/prompt_registry.py:1-232`
- **Impact:** `build_prompt()` is a pure function that looks up a key in a module-level `_PROMPT_TEMPLATES` dict and substitutes placeholders. It's not a class, has no state, and has no instance. Yet it's accessed via import from 5+ services, which is fine — but calling it a "registry" implies dynamic registration, which never happens.
- **Current state:** Static dict of 18 prompt templates. `build_prompt(key, **kwargs)` does `.format(**kwargs)` with a fallback.
- **Simpler alternative:** This is already simple. The name "registry" is slightly misleading (it's really `prompt_templates.py`) but the implementation is correct. Leave alone.
- **Risk:** N/A
- **Effort:** N/A

## Complexity Scores

| Subsystem | Complexity | Justified? | Notes |
|-----------|-----------|------------|-------|
| Hook processing (6 modules, 2,891 lines) | High | Partially | Core pipeline is sound but facade layer and dead bridge add unnecessary weight. `hook_receiver.py` at 1,223 lines is doing too much. |
| State management (state_machine + task_lifecycle + hook_agent_state) | Medium | Yes | Three layers serve distinct purposes (validation, orchestration, transient state). Log-only enforcement is the main concern. |
| Intelligence/inference (6 modules, 2,767 lines) | Medium | Yes | Clean three-tier architecture (client → service → consumers). Cache, rate limiter, and client are appropriately thin. |
| Real-time SSE (broadcaster + card_state) | Medium | Yes | Broadcaster is well-designed. card_state at 670 lines is large but stateless — it computes display state from models. |
| Monitoring (headspace_monitor + agent_reaper + activity_aggregator + commander_availability) | Low-Medium | Yes | Background threads are straightforward. Headspace monitor's rolling window logic is inherently complex but well-contained. |
| Session management (correlator + registry) | Medium | Partially | Correlator's 4-strategy cascade is justified. The separate session_registry adds a parallel path that may no longer be needed as primary. |
| File watcher (file_watcher + jsonl_parser + session_registry) | High | No | Legacy system running alongside hooks. 1,010 lines of active code for a backup monitoring path. Should be demoted to fallback. |
| Utilities (remaining 18 modules) | Low | Yes | Appropriately thin. Most are pure functions or self-contained subprocess wrappers. |

## Recommended Simplification Sequence

Ordered by effort (lowest first) and impact (highest first):

1. **Delete hook_lifecycle_bridge.py** — Remove 535 lines of dead code + its test. Immediate cognitive load reduction. | Effort: **Low** | Unblocks: cleaner mental model of hook pipeline

2. **Delete process_monitor.py** — Remove 181 lines of unused code. Update `__init__.py` exports. | Effort: **Low** | Unblocks: nothing (cleanup)

3. **Inline hook_helpers.py** — Move 9 wrapper functions into their 3 callers. Removes one hop from every hook processing chain. | Effort: **Low** | Unblocks: shorter call chains, easier debugging

4. **Centralize cache invalidation** — Create `invalidate_agent_caches(agent_id)` called from reaper and session-end. Ensures all 4+ caches are cleared consistently. | Effort: **Low** | Unblocks: fewer stale-state bugs

5. **Consolidate broadcaster access pattern** — Standardize on `get_broadcaster()` global, remove redundant `app.extensions["broadcaster"]` registration (keep for shutdown only). Same for notification_service. | Effort: **Low** | Unblocks: single canonical access pattern

6. **Decide on state machine enforcement** — Either enforce transitions (raise on invalid) or simplify to log + lookup. Remove the middle ground. | Effort: **Low** | Unblocks: clearer contract for task_lifecycle callers

7. **Demote file watcher to fallback** — Add config flag `file_watcher.enabled: false` (default off), keep code but don't start it in production. Test that hooks provide full coverage. | Effort: **Medium** | Unblocks: eliminates parallel monitoring pipeline, simplifies mental model

8. **Merge hook_extractors into hook_receiver** — 160 lines of extraction functions called only by hook_receiver. Inlining removes a module boundary with no independence. | Effort: **Low-Medium** | Unblocks: fewer files to navigate when debugging hooks

## Leave Alone

These modules look complex but earn their complexity:

- **intent_detector.py (600 lines):** 70+ regex patterns with multi-stage scoring is inherently complex. The heuristic pipeline (tail extraction → code block stripping → pattern matching → LLM fallback) is well-structured and each stage adds real value. Simplifying would mean worse intent detection.

- **session_correlator.py (542 lines):** The 4-strategy cascade (cache → DB → headspace UUID → working directory) exists because no single strategy works reliably in all cases. The cache is necessary to avoid N+1 DB queries on every hook. The query timeout protection is a real safeguard.

- **summarisation_service.py (826 lines):** Handles 5 distinct summarisation types with frustration extraction, trivial bypass, and response cleaning. The complexity maps directly to business requirements.

- **tmux_bridge.py (1,074 lines):** Large but self-contained with zero service dependencies. The size comes from handling real subprocess complexity (ANSI stripping, pane validation, permission dialog parsing, error classification). Each function addresses a real tmux interaction need.

- **card_state.py (670 lines):** Stateless helper library computing display state from Agent/Task/Turn models. Large because the dashboard has many display states and fallbacks. No state management or service coordination — just view logic.

- **headspace_monitor.py (498 lines):** Rolling-window frustration tracking with flow detection and traffic-light alerts. The state management (10-turn, 30-min, 3-hr windows) is inherently stateful and the thread safety is required.

- **inference_service.py (429 lines):** Clean orchestrator delegating to cache, rate limiter, and HTTP client. Independent DB engine for async logging is a pragmatic solution. The three delegates are each under 120 lines.

- **config_editor.py (675 lines):** Large because it contains schema definitions for 17 config sections as dataclasses. The schema is documentation and validation in one. Atomic writes via tempfile are correct.
