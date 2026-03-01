## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation -- Foundation + CRITICAL (Phase 2)

- [x] 2.1 Create `src/claude_headspace/services/advisory_lock.py` with `advisory_lock`, `advisory_lock_or_skip`, `LockNamespace`, `AdvisoryLockError`, `lock_key_from_string`
- [x] 2.2 Increase connection pool in `config.yaml`: `pool_size: 15`, `max_overflow: 10`
- [x] 2.3 Add `advisory_lock(AGENT, agent.id)` to all 8 mutating hook routes in `routes/hooks.py`
- [x] 2.4 Add `db.session.refresh(agent)` before `prompt_injected_at` check in `skill_injector.py` (defence in depth)

## 3. Implementation -- HIGH Fixes (Phase 3)

- [x] 3.1 Restructure `hook_deferred_stop.py`: sleep/retry without lock, acquire AGENT lock before state mutation, add `db.session.refresh(command)` + state check
- [x] 3.2 Add `advisory_lock_or_skip(AGENT, agent.id)` per-agent in `agent_reaper.py` reap loop; restructure to commit inside lock scope
- [x] 3.3 Add `advisory_lock_or_skip(AGENT, agent.id)` in `transcript_reconciler.py`; remove `get_reconcile_lock()` in-memory lock
- [x] 3.4 Add `SELECT ... FOR UPDATE NOWAIT` check in `summarisation_service.py` `summarise_turn()`
- [x] 3.5 Add `advisory_lock(AGENT, agent_id)` in `handoff_executor.py` `trigger_handoff()`; remove `_handoff_lock`
- [x] 3.6 Add `advisory_lock(AGENT, agent.id)` in `remote_agent_service.py` around readiness-to-send window
- [x] 3.7 Add `fcntl.flock()` in `config_editor.py` around read-modify-write
- [x] 3.8 Remove `_progress_capture_locks` from `hook_agent_state.py` and `hook_receiver.py`

## 4. Implementation -- MEDIUM/LOW + Monitoring (Phase 4)

- [x] 4.1 Add `advisory_lock_or_skip(AGENT, agent.id)` per-agent in `context_poller.py`
- [x] 4.2 Add `advisory_lock_or_skip(AGENT, agent.id)` per-agent in `tmux_watchdog.py`
- [x] 4.3 Add `/api/advisory-locks` monitoring endpoint in `routes/debug.py`

## 5. Testing (Phase 5)

- [x] 5.1 Create `tests/services/test_advisory_lock.py` -- unit tests for lock acquisition, release, timeout, non-blocking skip, connection cleanup, key hashing, nested safety
- [x] 5.2 Create `tests/integration/test_advisory_lock_concurrency.py` -- multi-threaded concurrency tests: serialisation, different agents, hook+reaper contention, deferred stop+session_end, pool exhaustion, reentrancy detection, per-iteration commit, exception during body, unconditional unlock, lock_or_skip reentrancy
- [x] 5.3 Run existing test suites for all modified files to verify no regressions

## 6. Final Verification

- [x] 6.1 All tests passing
- [x] 6.2 No linter errors
- [x] 6.3 Manual verification: deploy and monitor lock contention via logs
- [x] 6.4 Verify `/api/advisory-locks` endpoint returns correct data
