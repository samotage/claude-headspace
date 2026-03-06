# Complexity Audit Report

**Date:** 2026-03-06
**Scope:** Full codebase (80 service modules, 30 route files, 21 model files, app factory)
**Depth:** Quick scan
**Focus patterns:** All — abstraction without payoff, deep call chains, parallel mechanisms, state management sprawl, defensive complexity, configuration-driven indirection

## Executive Summary

The codebase is well-modularised — 80 service modules with clear separation of concerns, 26 blueprints focused by feature, and 28 lean data models. The architecture earns most of its complexity: the hook processing pipeline, inference orchestration, and real-time SSE broadcasting are genuinely complex domains handled cleanly.

The three-tier turn detection system (hooks, file watcher, tmux watchdog) is intentionally redundant — none of the three mechanisms are individually reliable enough, so all three run together to form one reliable system. This is earned complexity. The remaining concern is **state divergence**: `SessionRegistry.last_activity_at` and `Agent.last_seen_at` track the same concept independently, and context usage is fetched by both a background poller AND opportunistically on every hook event.

The second pattern is **defensive complexity in the hook handler pipeline**. After a recent modularisation (splitting hook_receiver into 7 handler modules), compatibility shims remain: a 76-line re-export facade, 167 lines of proxy classes wrapping a single state object, and nested try/except layers that swallow errors as warnings. These add indirection without protecting against real failure modes.

Estimated complexity tax: ~10% of service code (roughly 1,800 lines) could be removed or simplified without losing functionality. The biggest wins are eliminating the hook receiver compatibility layer, consolidating exception handling, and removing the context double-fetch.

## Service Dependency Graph

| Service | Lines | Deps | Dependents | Flags |
|---------|-------|------|------------|-------|
| channel_service | 2092 | 2 | 3 | hub |
| tmux_bridge | 1873 | 0 | 12 | hub |
| config_editor | 1248 | 0 | 2 | |
| summarisation_service | 1064 | 2 | 1 | |
| card_state | 896 | 2 | 8 | hub |
| command_lifecycle | 831 | 7 | 4 | hub |
| agent_lifecycle | 776 | 2 | 3 | |
| handoff_executor | 776 | 4 | 1 | |
| intent_detector | 753 | 1 | 3 | |
| iterm_focus | 696 | 0 | 1 | |
| channel_delivery | 668 | 4 | 1 | |
| file_watcher | 665 | 5 | 0 | orphan (disabled) |
| transcript_reconciler | 622 | 3 | 2 | |
| session_correlator | 618 | 0 | 2 | |
| permission_summarizer | 572 | 0 | 1 | |
| headspace_monitor | 550 | 1 | 1 | state holder |
| hook_handler_stop | 549 | 4 | 1 | |
| agent_reaper | 540 | 2 | 0 | |
| activity_aggregator | 490 | 0 | 0 | |
| hook_deferred_stop | 469 | 3 | 1 | |
| inference_service | 461 | 3 | 4 | hub |
| hook_handler_awaiting_input | 454 | 4 | 1 | |
| hook_handler_user_prompt | 431 | 5 | 1 | |
| persona_assets | 413 | 0 | 3 | |
| priority_scoring | 408 | 2 | 1 | |
| hook_agent_state | 379 | 0 | 6 | state holder |
| broadcaster | 377 | 0 | 8 | hub |
| hook_receiver_helpers | 368 | 8 | 7 | hub |
| remote_agent_service | 347 | 4 | 1 | |
| tmux_watchdog | 343 | 2 | 0 | |
| voice_channel_handlers | 335 | 3 | 1 | |
| git_analyzer | 331 | 0 | 1 | |
| transcript_export | 314 | 0 | 1 | |
| transcript_reader | 313 | 0 | 2 | |
| progress_summary | 312 | 5 | 1 | |
| notification_service | 311 | 0 | 3 | |
| archive_service | 307 | 1 | 3 | |
| advisory_lock | 303 | 0 | 5 | |
| commander_availability | 299 | 1 | 0 | |
| hook_handler_session_start | 296 | 4 | 1 | |
| brain_reboot | 290 | 2 | 1 | |
| file_upload | 283 | 0 | 1 | |
| team_content_detector | 266 | 0 | 4 | |
| skill_injector | 261 | 2 | 2 | |
| voice_formatter | 260 | 1 | 2 | |
| hook_handler_post_tool_use | 255 | 4 | 1 | |
| api_call_logger | 253 | 0 | 1 | |
| context_poller | 251 | 4 | 0 | |
| state_machine | 243 | 0 | 2 | |
| waypoint_editor | 242 | 2 | 1 | |
| prompt_registry | 231 | 0 | 4 | |
| event_schemas | 222 | 0 | 1 | |
| event_writer | 217 | 1 | 2 | |
| voice_channel_intent | 199 | 0 | 1 | |
| hook_extractors | 196 | 1 | 3 | |
| git_metadata | 188 | 0 | 2 | |
| jsonl_parser | 183 | 0 | 2 | |
| openrouter_client | 182 | 0 | 1 | |
| session_registry | 173 | 0 | 1 | orphan (file_watcher only) |
| hook_receiver_proxies | 167 | 1 | 1 | thin wrapper |
| guardrail_sanitiser | 164 | 0 | 1 | |
| session_token | 159 | 0 | 2 | |
| voice_matchers | 156 | 0 | 2 | |
| revival_service | 151 | 1 | 1 | |
| exception_reporter | 147 | 0 | 2 | |
| handoff_detection | 135 | 1 | 1 | thin wrapper |
| hook_receiver_types | 133 | 0 | 7 | |
| inference_cache | 126 | 0 | 1 | |
| voice_auth | 124 | 0 | 1 | |
| hook_handler_session_end | 124 | 4 | 1 | |
| voice_agent_helpers | 116 | 1 | 1 | |
| staleness | 115 | 0 | 1 | thin wrapper |
| persona_registration | 115 | 1 | 1 | |
| caller_identity | 115 | 0 | 1 | |
| inference_rate_limiter | 105 | 0 | 1 | |
| project_decoder | 99 | 0 | 2 | |
| hook_receiver | 76 | 7 | 1 | thin wrapper (re-export facade) |
| voice_channel_helpers | 61 | 1 | 1 | |
| context_parser | 37 | 0 | 2 | |
| path_constants | 22 | 0 | 4 | |

**Hub services** (high blast radius, many dependents): tmux_bridge (12), card_state (8), broadcaster (8), command_lifecycle (7 deps, 4 dependents), hook_receiver_helpers (7), inference_service (4)

**Flagged services:** 4 thin wrappers, 2 in-memory state holders

## Findings

### [STATE MANAGEMENT SPRAWL] SessionRegistry duplicates Agent.last_seen_at

- **Files:** `services/session_registry.py:18` (`last_activity_at`), `models/agent.py:68` (`last_seen_at`)
- **Impact:** The file watcher's `SessionRegistry` maintains `last_activity_at` timestamps in memory that track the same concept as `Agent.last_seen_at` in the database. These can diverge silently. The tmux watchdog queries the DB fresh every cycle (no drift on restarts) — the file watcher could do the same.
- **Current state:** Two independent liveness timestamps for the same agents. The agent reaper uses DB `last_seen_at`. The file watcher uses memory `last_activity_at`.
- **Simpler alternative:** Have the file watcher read/write `Agent.last_seen_at` via the DB instead of maintaining a parallel in-memory timestamp. This keeps the file watcher as a full participant in the reliability tier without state divergence.
- **Risk:** Low — the file watcher already has app context for DB access.
- **Effort:** Low

### [PARALLEL MECHANISMS] Context usage double-fetched (poller + every hook)

- **Files:** `services/context_poller.py:~170` (background thread), `services/hook_receiver_helpers.py:65-68` (`_fetch_context_opportunistically`)
- **Impact:** Context window usage is polled by `ContextPoller` every 60s AND read opportunistically on every hook event via `broadcast_card_refresh` → `_fetch_context_opportunistically`. The opportunistic fetch runs a subprocess (`tmux capture-pane`), parses statusline, and writes to DB if data is >15s stale. This means every hook event potentially fires a subprocess as a side effect of what appears to be a simple SSE broadcast. With active agents producing multiple hooks per second, this is significant unnecessary load.
- **Current state:** `broadcast_card_refresh` calls `_fetch_context_opportunistically` which calls tmux subprocess. The function name "broadcast_card_refresh" doesn't suggest it will read tmux panes.
- **Simpler alternative:** Remove `_fetch_context_opportunistically` from `broadcast_card_refresh`. Trust the `ContextPoller` background thread. If fresher context data is needed for specific events, call the fetch explicitly at those call sites rather than hiding it inside every card broadcast.
- **Risk:** Context data may be up to 60s stale instead of near-real-time. Acceptable for a status indicator.
- **Effort:** Low

### [ABSTRACTION WITHOUT PAYOFF] Hook receiver compatibility shims (proxies + facade)

- **Files:** `services/hook_receiver_proxies.py` (167 lines), `services/hook_receiver.py` (76 lines)
- **Impact:** Six proxy classes (`_AwaitingToolProxy`, `_RespondPendingProxy`, etc.) wrap single methods on `AgentHookState` to provide dict/set-like interfaces. `_RespondPendingProxy.__getitem__` unconditionally raises `KeyError` (comment: "Not needed"). `__len__` returns 0 on several. `clear()` is a no-op on two. These exist for "backwards compatibility" after the hook_receiver modularisation, but all callers are internal handler modules that could import `AgentHookState` directly. The 76-line `hook_receiver.py` is pure re-exports (`noqa: F401`) with no logic.
- **Current state:** The handler modules already import from `hook_agent_state` for most operations. The proxies are used for a few remaining dict-syntax call sites.
- **Simpler alternative:** Delete `hook_receiver_proxies.py`. Update remaining call sites to use `AgentHookState` methods directly. Optionally delete `hook_receiver.py` facade and have `routes/hooks.py` import from handler modules directly.
- **Risk:** Low — internal refactor only, no external API.
- **Effort:** Low

### [DEFENSIVE COMPLEXITY] Nested exception swallowing in hook handlers

- **Files:** `services/hook_handler_session_end.py`, `services/hook_receiver_helpers.py`, all hook handler files
- **Impact:** Hook handlers use 3-4 layers of nested try/except blocks that catch `Exception` and log warnings. Each helper function wraps its broadcast call in try/except. The handler wraps the helper call in try/except. The route wraps the handler call in try/except. Errors become warnings at each layer, making bugs invisible. In `hook_receiver_helpers.py` alone, there are 9 instances of `try: broadcast(); except Exception: logger.warning(...)`. The outer handler catch blocks handle cases that are realistically only DB errors or coding bugs — both of which should propagate.
- **Current state:** A broadcast failure in a hook handler is silently swallowed as a warning in the log. The hook returns success to Claude Code. If the failure is persistent, no alert fires.
- **Simpler alternative:** Create a `best_effort(fn, *args)` context manager/decorator for broadcast calls that centralises the swallow-and-log pattern. Remove the redundant outer catch blocks or make them propagate. Let genuine errors (DB failures, coding bugs) surface.
- **Risk:** Medium — removing exception handling requires careful auditing of what can actually fail at each point.
- **Effort:** Medium

### [STATE MANAGEMENT SPRAWL] Agent activity tracked in three places

- **Files:** `models/agent.py:68` (`last_seen_at`), `services/session_registry.py:18` (`last_activity_at`), `services/hook_agent_state.py` (per-event timestamps)
- **Impact:** Agent liveness is determined by: (a) `Agent.last_seen_at` in DB (updated by 21+ files on every hook), (b) `RegisteredSession.last_activity_at` in file watcher memory (updated by polling loop), (c) `AgentHookState._respond_pending` timestamps for TTL-based liveness in hook processing. All three can disagree silently. The agent reaper uses DB `last_seen_at`. The file watcher uses memory `last_activity_at`. The hook handlers use `_respond_pending` timestamps.
- **Current state:** With file watcher disabled, (b) is dormant. But (a) and (c) still operate independently.
- **Simpler alternative:** Collapse to `Agent.last_seen_at` as the single source of truth. Remove `SessionRegistry.last_activity_at`. Ensure `AgentHookState` TTL checks read from the DB field.
- **Risk:** Low — follows from removing SessionRegistry.
- **Effort:** Low

### [ABSTRACTION WITHOUT PAYOFF] Single-method service classes

- **Files:** `services/staleness.py` (115 lines — `StalenessService`), `services/handoff_detection.py` (135 lines — `HandoffDetectionService`)
- **Impact:** `StalenessService` holds two config integers and provides `classify_project(project)` — a pure function. Registered as app extension, called from one place (`routes/dashboard.py`). `HandoffDetectionService` has one method `detect_and_emit(agent)`, stores `self.app` but never uses it. Both could be plain module-level functions.
- **Current state:** Each is a class instantiated at startup, registered in `app.extensions`, and called from one location.
- **Simpler alternative:** Module-level functions with config passed as arguments.
- **Risk:** None.
- **Effort:** Low

### [CONFIGURATION-DRIVEN INDIRECTION] HookMode polling fallback that changes nothing

- **Files:** `services/hook_receiver_types.py:49-103`
- **Impact:** `HookReceiverState` tracks whether the system is in `HOOKS_ACTIVE` or `POLLING_FALLBACK` mode. The mode switches when no hooks arrive for 300 seconds. However, no background thread or service changes behaviour based on this mode. The tmux watchdog always polls at its fixed interval. The file watcher is disabled. `get_polling_interval()` is only surfaced in the `/hook/status` API response — it's a display metric, not a control signal.
- **Current state:** The mode enum and switching logic exist but are purely informational.
- **Simpler alternative:** Keep the status reporting (useful diagnostics) but document it as display-only. Remove `get_polling_interval()` since nothing consumes it as a control value. Or, actually wire it into the tmux watchdog so the mode switch has teeth.
- **Risk:** None.
- **Effort:** Low

## Background Thread Assessment

| Thread | Interval | Justified? | Notes |
|--------|----------|------------|-------|
| AgentReaper | 60s | Yes | Safety net for unclean exits. Advisory locks prevent contention. |
| ActivityAggregator | 300s | Partially | Could be computed on-demand at page load with short cache. Runs regardless of whether anyone views activity page. |
| CommanderAvailability | 30s | Partially | 30s polling is aggressive. Could be event-driven (triggered by SSE reconnection or card open). ThreadPoolExecutor with 5 workers for health checks is heavyweight. |
| ContextPoller | 60s | Yes | Sidecar fallback for narrow terminals is genuinely useful. But redundant with opportunistic fetch in hook helpers (see finding above). |
| FileWatcher | 2s (disabled) | No | Disabled by default. Tmux watchdog covers the same gap. Infrastructure cost without benefit. |
| TmuxWatchdog | 3s | Yes | Genuine safety net for missed hooks. 60s reconciliation sweep is the final catch-all. |

**Additional background threads:** SSE cleanup (broadcaster), priority-scoring (fire-and-forget), debounce timers (priority scoring), per-agent inference timers (file watcher), deferred-stop threads (hook processing), shutdown threads (remote agent), handoff-poll threads (handoff executor). Total: 13 thread types, 6 persistent + 7 short-lived.

**No thread lifecycle monitoring.** If a persistent thread crashes past its own `except Exception`, no watchdog restarts it. The `is_alive()` guards in `start()` prevent double-starts but don't detect dead threads.

## Complexity Scores

| Subsystem | Complexity | Justified? | Notes |
|-----------|-----------|------------|-------|
| Hook processing | High | Partially | 7 handler modules + helpers + proxies + facade + types = 10 files. The modularisation was correct but compatibility shims remain. |
| State management | Medium | Partially | StateMachine is clean (243 lines, pure). CommandLifecycleManager (831 lines) is complex but earns it. HookAgentState (379 lines) is well-structured. |
| Intelligence/inference | Medium | Yes | Clean 3-layer stack: InferenceService → cache/rate-limiter → OpenRouterClient. PromptRegistry centralises templates. |
| Real-time (SSE) | Low | Yes | Broadcaster (377 lines) is focused and clean. CardState (896 lines) is large but handles genuine complexity. |
| Monitoring | High | Partially | 6 persistent background threads + 7 short-lived thread types. Overlapping turn detection (3 systems). Context double-fetch. |
| Session management | Medium | Partially | SessionCorrelator (618 lines, 5-strategy cascade) is complex but handles real edge cases. SessionRegistry is orphaned. |
| Channels | Medium | Yes | ChannelService (2092 lines) is the largest service but handles CRUD, membership, lifecycle, and broadcasting in one place. |
| Voice bridge | Medium | Yes | Well-decomposed into 6 focused modules (auth, formatter, matchers, intent, handlers, helpers). |

## Recommended Simplification Sequence

1. **Remove dormant file watcher infrastructure** — Delete `SessionRegistry` (173 lines). Gate `FileWatcher` instantiation so it doesn't create infrastructure when disabled. | Effort: Low | Unblocks: cleaner mental model of turn detection (2 systems, not 3)

2. **Delete hook receiver compatibility shims** — Remove `hook_receiver_proxies.py` (167 lines). Update call sites to use `AgentHookState` directly. Optionally remove `hook_receiver.py` facade (76 lines). | Effort: Low | Unblocks: clearer hook handler code paths

3. **Remove context opportunistic fetch** — Delete `_fetch_context_opportunistically` from `broadcast_card_refresh`. Trust the `ContextPoller`. | Effort: Low | Unblocks: no subprocess calls on hot path

4. **Consolidate exception handling** — Create a `best_effort()` utility for broadcast calls. Remove redundant nested try/except layers in hook handlers. | Effort: Medium | Unblocks: errors become visible, debugging becomes possible

5. **Collapse single-method service classes** — Convert `StalenessService` and `HandoffDetectionService` to module-level functions. | Effort: Low | Unblocks: fewer app.extensions registrations

6. **Evaluate CommanderAvailability polling** — Consider event-driven availability checks instead of 30s polling with ThreadPoolExecutor. | Effort: Medium | Unblocks: reduced background thread load

## Leave Alone

- **SessionCorrelator** (618 lines, 5-strategy cascade) — looks complex but each strategy handles a real edge case (new session, reconnect, headspace UUID, working directory match, create new). The cascade order matters.
- **IntentDetector** (753 lines, 70+ regex patterns) — pattern-matching complexity is inherent to the domain. The regex/LLM fallback architecture is clean.
- **TmuxBridge** (1873 lines) — large because tmux interaction has many edge cases (paste buffer fallback, enter verification, per-pane locking, health checks). Each method handles a real scenario.
- **CommandLifecycleManager** (831 lines) — manages 5-state transitions with turn processing, intent detection, and summarisation queueing. The complexity matches the state space.
- **InferenceService** stack (cache + rate limiter + client) — clean layered architecture. Each layer has a single responsibility.
- **AdvisoryLock** (303 lines) — PostgreSQL advisory locks with reentrancy detection. The complexity prevents deadlocks across background threads and hook routes.
- **ChannelService** (2092 lines) — large but handles the full channel lifecycle in one place rather than scattering across multiple services.
