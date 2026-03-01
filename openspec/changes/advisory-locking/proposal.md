## Why

The Claude Headspace application has 26 identified race conditions (3 CRITICAL, 8 HIGH, 9 MEDIUM, 6 LOW) caused by check-then-act without atomicity, in-memory locks that do not cross process boundaries, and multiple unsynchronised writers to the same database rows. These manifest as duplicate database records, corrupted state machine transitions, duplicate LLM inference calls, and duplicated UI elements.

## What Changes

### Core Infrastructure

- **New advisory lock service** (`advisory_lock.py`) providing PostgreSQL session-scoped advisory locks on dedicated connections, independent of `db.session` transactions
  - Blocking context manager (`advisory_lock`) for hook routes and API endpoints
  - Non-blocking context manager (`advisory_lock_or_skip`) for background threads
  - Thread-local reentrancy detection to prevent deadlocks
  - Unconditional unlock in finally block to handle PostgreSQL Bug #17686 (phantom locks)
  - String-to-key hashing utility via BLAKE2b

### Hook Routes (Pattern A -- Blocking)

- **BREAKING** (internal behaviour): All 8 mutating hook routes in `routes/hooks.py` acquire `advisory_lock(AGENT, agent.id)` after session correlation, serialising all per-agent hook processing

### Background Threads (Pattern C -- Non-Blocking Skip)

- `agent_reaper.py` -- per-agent `advisory_lock_or_skip` with commit-inside-lock restructure
- `transcript_reconciler.py` -- per-agent `advisory_lock_or_skip`; removes `get_reconcile_lock()` in-memory lock
- `context_poller.py` -- per-agent `advisory_lock_or_skip`
- `tmux_watchdog.py` -- per-agent `advisory_lock_or_skip`

### Deferred Stop (Pattern B -- Blocking Post-Sleep)

- `hook_deferred_stop.py` -- restructured to acquire AGENT lock AFTER sleep/retry loop, before state mutation; adds state re-check

### API Routes (Pattern D -- Blocking with Timeout)

- `handoff_executor.py` -- `advisory_lock(AGENT, agent_id)` around precondition check + execution; removes `_handoff_lock`
- `remote_agent_service.py` -- `advisory_lock(AGENT, agent.id)` around readiness-to-send window

### Supplementary Locking

- `summarisation_service.py` -- `SELECT ... FOR UPDATE NOWAIT` on turn row before LLM call
- `config_editor.py` -- `fcntl.flock()` for file-level TOCTOU protection

### Defence in Depth

- `skill_injector.py` -- `db.session.refresh(agent)` before `prompt_injected_at` check

### In-Memory Lock Removal

- Remove `_progress_capture_locks` from `hook_agent_state.py` and `hook_receiver.py`
- Remove `_handoff_lock` from `handoff_executor.py`
- Remove `get_reconcile_lock()` from `transcript_reconciler.py`

### Connection Pool

- Increase `pool_size` from 10 to 15 and `max_overflow` from 5 to 10 (total 25) to accommodate dual-connection locking pattern

### Monitoring

- New `/api/advisory-locks` endpoint showing currently held advisory locks via `pg_locks` + `pg_stat_activity`

## Impact

- Affected specs: state-machine (archived: e1-s6-state-machine)
- Affected code:
  - **New:** `src/claude_headspace/services/advisory_lock.py`, `tests/services/test_advisory_lock.py`, `tests/integration/test_advisory_lock_concurrency.py`
  - **Modified (Phase 1 -- CRITICAL):** `routes/hooks.py`, `services/skill_injector.py`
  - **Modified (Phase 2 -- HIGH):** `services/hook_deferred_stop.py`, `services/agent_reaper.py`, `services/transcript_reconciler.py`, `services/summarisation_service.py`, `services/handoff_executor.py`, `services/remote_agent_service.py`, `services/config_editor.py`, `services/hook_agent_state.py`, `services/hook_receiver.py`
  - **Modified (Phase 3 -- MEDIUM/LOW):** `services/context_poller.py`, `services/tmux_watchdog.py`, `routes/debug.py`, `config.yaml`
- Git context: recent commits (Feb 2026) show extensive work on hook_receiver modularisation, skill_injector prompt_injected_at migration, agent_reaper, and turn capture reliability -- all stable and complementary to this change
- OpenSpec history: e1-s6-state-machine (archived 2026-01-29) -- state machine itself is unchanged; advisory locks wrap around callers
