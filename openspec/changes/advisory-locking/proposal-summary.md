# Advisory Locking -- Proposal Summary

## Architecture Decisions

1. **Session-scoped advisory locks on dedicated connections** -- Transaction-scoped locks (`pg_advisory_xact_lock`) release on commit. The hook processing pipeline does 2-8 intermediate `db.session.commit()` calls within critical sections. Session-scoped locks on a separate connection survive all application commits.

2. **Single AGENT namespace** -- A single `pg_advisory_lock(1, agent_id)` per agent, rather than fine-grained namespaces (per-command, per-turn, etc.). Fine-grained namespaces (8 explored) caused 7 nested lock scenarios and deadlock risk. Single namespace eliminates nesting entirely.

3. **Blocking for hooks, non-blocking for background** -- Hook routes MUST process their events (data loss if skipped). Background threads (reaper, reconciler, poller, watchdog) can safely skip and retry on their next cycle.

4. **Thread-local reentrancy detection** -- Nested `advisory_lock()` calls for the same key on different connections would deadlock. Thread-local tracking raises `AdvisoryLockError` immediately instead.

5. **Unconditional unlock in finally** -- PostgreSQL Bug #17686: `lock_timeout` can fire AFTER the lock is granted but BEFORE the result is returned. Unconditional `pg_advisory_unlock` in the finally block prevents phantom lock leaks.

6. **`fcntl.flock()` for config** -- Config editing is a file operation that may not have a DB session available. File-level locking is the appropriate mechanism.

7. **No third-party library** -- The advisory lock service is ~80 lines of code with full control over connection lifecycle. No unnecessary dependencies.

## Implementation Approach

### Phased Rollout (3 phases + 1 separate workstream)

**Phase 1 (Foundation + CRITICAL):**
- Create `advisory_lock.py` service module
- Increase connection pool size (pool_size: 10->15, max_overflow: 5->10)
- Wrap all 8 mutating hook routes with `advisory_lock(AGENT, agent.id)`
- Add `db.session.refresh(agent)` defence in depth to skill injector

**Phase 2 (HIGH fixes):**
- Restructure deferred stop: sleep loop first, advisory lock second, state re-check after acquisition
- Agent reaper: per-agent `advisory_lock_or_skip` with commit-inside-lock
- Transcript reconciler: `advisory_lock_or_skip`, remove `get_reconcile_lock()`
- Summarisation service: `SELECT ... FOR UPDATE NOWAIT` on turn row
- Handoff executor: `advisory_lock(AGENT, agent_id)`, remove `_handoff_lock`
- Remote agent service: `advisory_lock(AGENT, agent.id)` around readiness-to-send
- Config editor: `fcntl.flock()` around read-modify-write
- Remove superseded in-memory locks from hook_agent_state.py, hook_receiver.py

**Phase 3 (MEDIUM/LOW + Monitoring):**
- Context poller: per-agent `advisory_lock_or_skip`
- Tmux watchdog: per-agent `advisory_lock_or_skip`
- `/api/advisory-locks` monitoring endpoint

**Phase 4 (Separate workstream -- session hygiene):**
- Not in this change. Covers stale ORM reads, Card State staleness, savepoints.

## Files to Modify

### New Files
| File | Purpose |
|------|---------|
| `src/claude_headspace/services/advisory_lock.py` | Advisory lock service (context managers + utilities) |
| `tests/services/test_advisory_lock.py` | Unit tests |
| `tests/integration/test_advisory_lock_concurrency.py` | Multi-threaded concurrency tests |

### Modified -- Phase 1 (CRITICAL)
| File | Changes |
|------|---------|
| `src/claude_headspace/routes/hooks.py` | Add `advisory_lock(AGENT, agent.id)` to 8 hook routes |
| `src/claude_headspace/services/skill_injector.py` | Add `db.session.refresh(agent)` before `prompt_injected_at` check |

### Modified -- Phase 2 (HIGH)
| File | Changes |
|------|---------|
| `src/claude_headspace/services/hook_deferred_stop.py` | Restructure: sleep first, lock second, state re-check |
| `src/claude_headspace/services/agent_reaper.py` | Per-agent `advisory_lock_or_skip`, commit inside lock |
| `src/claude_headspace/services/transcript_reconciler.py` | `advisory_lock_or_skip`, remove `get_reconcile_lock()` |
| `src/claude_headspace/services/summarisation_service.py` | `SELECT ... FOR UPDATE NOWAIT` in `summarise_turn()` |
| `src/claude_headspace/services/handoff_executor.py` | `advisory_lock(AGENT, agent_id)`, remove `_handoff_lock` |
| `src/claude_headspace/services/remote_agent_service.py` | `advisory_lock(AGENT, agent.id)` around readiness-to-send |
| `src/claude_headspace/services/config_editor.py` | `fcntl.flock()` around read-modify-write |
| `src/claude_headspace/services/hook_agent_state.py` | Remove `_progress_capture_locks` |
| `src/claude_headspace/services/hook_receiver.py` | Remove `_progress_capture_locks` usage |

### Modified -- Phase 3 (MEDIUM/LOW + Monitoring)
| File | Changes |
|------|---------|
| `src/claude_headspace/services/context_poller.py` | Per-agent `advisory_lock_or_skip` |
| `src/claude_headspace/services/tmux_watchdog.py` | Per-agent `advisory_lock_or_skip` |
| `src/claude_headspace/routes/debug.py` | `/api/advisory-locks` endpoint |
| `config.yaml` | `pool_size: 15`, `max_overflow: 10` |

## Acceptance Criteria

1. All 3 CRITICAL race conditions eliminated (state machine transitions, concurrent hooks, skill injector double injection)
2. All 8 HIGH race conditions addressed (reaper vs hooks, summarisation dedup, deferred stop vs session_end, progress capture vs reconciler, config editor TOCTOU, handoff double initiation, remote agent stale reads; Card State deferred to Phase 4)
3. MEDIUM/LOW races either subsumed by AGENT lock or explicitly deferred with rationale
4. No in-memory `threading.Lock()` remains where an advisory lock replaces it
5. Connection pool sized for peak concurrent scenarios with headroom
6. `/api/advisory-locks` endpoint operational for monitoring
7. All unit and concurrency tests passing
8. No regressions in existing test suites

## Constraints and Gotchas

1. **Dual-connection cost** -- Each locked operation uses 2 connections (1 lock, 1 work). Pool increased to 25 total to accommodate.
2. **Lock contention on rapid hooks** -- Claude Code fires hooks synchronously per agent, so normal operation is uncontested. Under rapid stop+session_end, the second hook waits up to 15s. This is correct behaviour (serialisation is the goal).
3. **Reaper must commit inside lock** -- Current reaper does batch commit after loop, which is incompatible with per-agent advisory locking. Must restructure to commit per-agent inside lock scope.
4. **Background task starvation** -- If an agent is perpetually locked (pathological case), background threads skip it indefinitely. Mitigated by 60s retry and monitoring for repeated skips.
5. **No multi-worker deployment** -- Advisory locks work across connections to the same database, so they are multi-worker safe. However, the application currently runs single-worker (debug mode). Advisory locks provide future-proofing.
6. **EventWriter and InferenceService have independent pools** -- They do NOT count against the main pool's 25 connections. No changes needed for those pools.
7. **Stale ORM reads are OUT OF SCOPE** -- Pattern #4 (SQLAlchemy identity map caching) is a separate workstream. Advisory locks serialise writes but do not fix stale reads from background threads.

## Git Change History

### Related Files (from git_context)
- `src/claude_headspace/services/card_state.py`
- `src/claude_headspace/services/hook_agent_state.py`
- `src/claude_headspace/services/state_machine.py`
- `tests/services/test_card_state.py`
- `tests/services/test_hook_agent_state.py`
- `tests/services/test_state_machine.py`
- `static/voice/voice-state.js`

### OpenSpec History
- `e1-s6-state-machine` (archived 2026-01-29) -- state machine spec. The state machine itself is unchanged; advisory locks wrap around callers (hook routes, background threads) that invoke state transitions.

### Relevant Patterns Detected
- Modules + tests + static file structure
- Recent commits show hook_receiver modularisation, skill_injector prompt_injected_at migration, agent_reaper restructuring, turn capture reliability model, and respond race condition fixes -- all directly related to the race conditions this PRD addresses

### Key Recent Commits
| SHA | Date | Message |
|-----|------|---------|
| `8739cca4` | 2026-02-24 | fix: persist prompt_injected_at after skill injection |
| `37f2cabb` | 2026-02-24 | fix: replace in-memory injection cooldown with DB-level prompt_injected_at column |
| `4399fb19` | 2026-02-24 | fix: defend against runaway hook storm & skip inference for persona injection |
| `39ae2892` | 2026-02-18 | fix: harden turn capture reliability with two-commit pattern and race fixes |
| `8d6a31e1` | 2026-02-18 | feat: three-tier turn capture reliability model |
| `f91c9ec5` | 2026-02-17 | refactor: simplify voice-tmux pipeline and fix respond race condition |
| `1adfb3aa` | 2026-02-13 | refactor(hooks): modularise hook_receiver.py with thread-safe state |

## Q&A History

No clarification questions were needed. The PRD is comprehensive with full code samples, explicit decision rationale, and a complete race-by-race fix specification.

## Dependencies

### Python (already installed)
- `sqlalchemy` (already in use -- `text`, `db.engine.connect()`, `with_for_update`)
- `hashlib`, `struct`, `threading`, `contextlib`, `fcntl` (stdlib)

### No new dependencies required
The advisory lock service uses only existing SQLAlchemy infrastructure and Python stdlib.

### Database
- PostgreSQL 14+ (advisory locks available since PostgreSQL 8.0)
- No new migrations required (advisory locks are runtime primitives, not schema changes)

## Testing Strategy

### Unit Tests (`tests/services/test_advisory_lock.py`)
1. Lock acquisition and release
2. Timeout behaviour (`AdvisoryLockError`)
3. Non-blocking skip (`advisory_lock_or_skip` yields `False`)
4. Connection cleanup on exceptions
5. Lock key hashing (`lock_key_from_string` determinism)
6. Nested context manager safety

### Concurrency Tests (`tests/integration/test_advisory_lock_concurrency.py`)
1. Two threads, same lock -- verify serialisation
2. Two threads, different agents -- verify independence
3. Hook + reaper contention -- verify reaper skips
4. Deferred stop + session_end -- verify deferred stop sees COMPLETE
5. Pool exhaustion safety -- 15+ concurrent attempts timeout (not deadlock)
6. Reentrancy detection -- nested same-agent raises `AdvisoryLockError`
7. Reaper per-iteration commit -- max 2 connections at any point
8. Exception during body with intermediate commits -- lock released
9. Unconditional unlock safety -- `pg_advisory_unlock` returns FALSE gracefully
10. `advisory_lock_or_skip` reentrancy -- yields False (not deadlock)

### Regression Tests
Each modified service file should have targeted tests verifying the lock integration does not change functional behaviour.

## OpenSpec References

- **Proposal:** `openspec/changes/advisory-locking/proposal.md`
- **Tasks:** `openspec/changes/advisory-locking/tasks.md`
- **Spec:** `openspec/changes/advisory-locking/specs/advisory-locking/spec.md`
