---
validation:
  status: valid
  validated_at: '2026-03-01T19:24:15+11:00'
---

# PRD: Advisory Locking for Race Condition Prevention

**Status:** Draft — Pending Design Review
**Author:** Shorty (Technical Architect)
**Date:** 2026-03-01
**Subsystem:** State Management / Infrastructure
**Priority:** Critical

---

## 1. Problem Statement

The Claude Headspace application has **26 identified race conditions** across the codebase (3 CRITICAL, 8 HIGH, 9 MEDIUM, 6 LOW). These manifest as duplicate database records, corrupted state machine transitions, duplicate LLM inference calls, and duplicated UI elements.

### Root Cause

Four structural anti-patterns account for all 26 races:

1. **Check-then-act without atomicity** — read state, make decision, write state with no lock held across all three steps
2. **In-memory locks don't cross process boundaries** — `threading.Lock()` instances are useless if Flask runs multiple workers
3. **Multiple unsynchronised writers to the same DB rows** — no `SELECT ... FOR UPDATE`, no advisory locks, no optimistic locking
4. **Stale ORM reads from background threads** — SQLAlchemy identity map caching (separate workstream)

### Impact

- **Duplicate turns** surface as duplicate chat bubbles in voice/embed UI
- **State machine corruption** causes commands stuck in wrong states
- **Duplicate LLM calls** waste inference budget (~$0.002/call, but adds up)
- **Double skill injection** sends priming messages to agent twice
- **Data integrity** — five dedup layers have all been bypassed at various points

---

## 2. Solution Overview

### Primary Mechanism: Per-Agent Advisory Lock

A single PostgreSQL session-scoped advisory lock per agent, held on a **dedicated connection** independent of the application's `db.session`.

```
┌─────────────────────────────────────────────────┐
│  Dedicated Lock Connection (from pool)          │
│  SELECT pg_advisory_lock(1, agent_id)  ──held─► │
│                                                 │
│  Application Connection (db.session)            │
│  INSERT turn ... ; COMMIT  ← lock unaffected    │
│  UPDATE command ... ; COMMIT  ← lock unaffected │
│                                                 │
│  Dedicated Lock Connection                      │
│  SELECT pg_advisory_unlock(1, agent_id)  ─done─►│
│  conn.close() → return to pool                  │
└─────────────────────────────────────────────────┘
```

**Why session-scoped on dedicated connection?**

Transaction-scoped locks (`pg_advisory_xact_lock`) release on commit. The hook processing pipeline does 2-8 intermediate `db.session.commit()` calls within critical sections, which would prematurely release the lock. Session-scoped locks on a dedicated connection survive all application commits.

### Supplementary Mechanisms

| Mechanism | Use Case |
|-----------|----------|
| `SELECT ... FOR UPDATE NOWAIT` | Summarisation dedup (per-turn row lock before LLM call) |
| `fcntl.flock()` | Config editor TOCTOU (file-level lock) |
| `db.session.refresh()` | Stale ORM reads (separate workstream) |

### What This Does NOT Cover

- **Pattern #4 (Stale ORM reads)** — session hygiene is a separate workstream
- **Card State staleness** — `db.session.refresh()` fix, not a locking concern
- **Session Token overwrites** — in-memory thread lock, already present
- **Broadcaster event ordering** — eventual consistency, not harmful

---

## 3. Detailed Design

### 3.1 Advisory Lock Service

**New file:** `src/claude_headspace/services/advisory_lock.py`

```python
"""
PostgreSQL advisory lock service for race condition prevention.

Uses session-scoped advisory locks on dedicated connections,
independent of db.session transactions. Locks survive intermediate
commits in the application code.

Lock key format: pg_advisory_lock(namespace_int, entity_id_int)
  - namespace: LockNamespace.AGENT (= 1)
  - entity_id: agent.id (integer primary key)

Usage:
    # Blocking (for hook routes — MUST process):
    with advisory_lock(LockNamespace.AGENT, agent.id):
        process_hook(agent)  # Multiple commits inside are safe

    # Non-blocking (for background tasks — skip if busy):
    with advisory_lock_or_skip(LockNamespace.AGENT, agent.id) as acquired:
        if not acquired:
            return  # Another process is handling this agent
        reap_agent(agent)

Reentrancy Safety:
    Each advisory_lock() call creates a NEW dedicated connection.
    If code inside a `with advisory_lock(AGENT, X)` block calls
    `advisory_lock(AGENT, X)` again, the second call attempts to
    acquire the same lock on a DIFFERENT connection — which will
    DEADLOCK (the outer connection holds the lock, the inner
    connection waits for it, but the outer is blocked waiting for
    the inner to complete).

    To prevent this, a thread-local set tracks currently held locks.
    Nested acquisition of the same (namespace, key) raises
    AdvisoryLockError immediately instead of deadlocking.
"""

import hashlib
import struct
import logging
import threading
from contextlib import contextmanager
from sqlalchemy import text
from ..database import db

logger = logging.getLogger(__name__)

# Thread-local storage for reentrancy detection.
# Each thread tracks which (namespace, key) pairs it currently holds.
_thread_local = threading.local()


def _held_locks() -> set:
    """Get the set of (namespace, key) locks held by the current thread."""
    if not hasattr(_thread_local, "held_locks"):
        _thread_local.held_locks = set()
    return _thread_local.held_locks


class LockNamespace:
    """
    Advisory lock namespace constants.

    Used as the first integer in pg_advisory_lock(key1, key2).
    Currently only AGENT is used. Additional namespaces reserved
    for future use if per-agent granularity proves too coarse.
    """
    AGENT = 1
    # Reserved for future use:
    # CONFIG = 2  (if file-level locking proves insufficient)


class AdvisoryLockError(Exception):
    """Raised when an advisory lock cannot be acquired within timeout."""
    pass


@contextmanager
def advisory_lock(namespace: int, key: int, timeout: float = 15.0):
    """
    Blocking advisory lock on a dedicated connection.

    Acquires a PostgreSQL session-scoped advisory lock. Blocks until
    the lock is acquired or timeout is reached. The lock is held on
    a dedicated connection, independent of db.session — so intermediate
    db.session.commit() calls do NOT release it.

    Args:
        namespace: Lock namespace (LockNamespace.AGENT)
        key: Entity ID (e.g., agent.id)
        timeout: Max seconds to wait (default 15s). Uses PostgreSQL
                 lock_timeout to cancel the blocking call.

    Raises:
        AdvisoryLockError: If lock cannot be acquired within timeout,
                          or if the same (namespace, key) is already
                          held by this thread (reentrancy detection).

    Example:
        with advisory_lock(LockNamespace.AGENT, agent.id):
            # All operations here are serialised per agent.
            # db.session.commit() does NOT release the lock.
            process_hook(agent)
            db.session.commit()
            do_more_work(agent)
            db.session.commit()
        # Lock released here.
    """
    lock_id = (namespace, key)
    held = _held_locks()

    # Reentrancy detection: fail-fast instead of deadlocking.
    if lock_id in held:
        raise AdvisoryLockError(
            f"Deadlock prevented: advisory lock (ns={namespace}, key={key}) "
            f"is already held by this thread. Check call graph for nested "
            f"advisory_lock() calls."
        )

    conn = db.engine.connect()
    try:
        # Use lock_timeout (not statement_timeout) — this is the correct
        # PostgreSQL parameter for lock wait timeouts. It specifically
        # cancels lock acquisition waits without affecting other statement
        # execution timing.
        timeout_ms = int(timeout * 1000)
        # Note: SET does not support parameterised values in PostgreSQL.
        # The value is an integer from a controlled source (not user input).
        conn.execute(text(f"SET lock_timeout = {timeout_ms}"))

        try:
            conn.execute(
                text("SELECT pg_advisory_lock(:ns, :key)"),
                {"ns": namespace, "key": key}
            )
            held.add(lock_id)
            logger.debug(f"advisory_lock acquired: ns={namespace} key={key}")
        except Exception as e:
            raise AdvisoryLockError(
                f"Timeout acquiring advisory lock "
                f"(ns={namespace}, key={key}, timeout={timeout}s)"
            ) from e

        yield

    finally:
        held.discard(lock_id)
        # ALWAYS attempt unlock regardless of whether we think we acquired.
        #
        # PostgreSQL Bug #17686: lock_timeout can fire AFTER the lock was
        # actually granted but BEFORE the result is returned to the client.
        # With session-scoped locks, this leaves a "phantom lock" — the
        # timeout error propagates, we think we didn't acquire, but the
        # lock is actually held on the connection.
        #
        # pg_advisory_unlock returns FALSE if the lock was not held —
        # safe to call unconditionally. If it returns TRUE unexpectedly
        # (lock was acquired despite timeout error), we log a warning.
        try:
            result = conn.execute(
                text("SELECT pg_advisory_unlock(:ns, :key)"),
                {"ns": namespace, "key": key}
            )
            unlocked = result.scalar()
            if unlocked:
                logger.debug(
                    f"advisory_lock released: ns={namespace} key={key}"
                )
            # If unlocked is True but we didn't think we acquired,
            # that's the Bug #17686 case — lock was silently acquired
            # despite the timeout error. We just cleaned it up.
        except Exception as e:
            logger.warning(
                f"advisory_lock unlock failed "
                f"(ns={namespace}, key={key}): {e}"
            )
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def advisory_lock_or_skip(namespace: int, key: int):
    """
    Non-blocking advisory lock. Yields True if acquired, False if not.

    For background tasks that should skip work if another process/thread
    is already handling this entity. Does NOT raise on failure — the
    caller checks the yielded boolean and decides what to do.

    Example:
        with advisory_lock_or_skip(LockNamespace.AGENT, agent.id) as acquired:
            if not acquired:
                logger.info(f"Skipping agent {agent.id} — lock held")
                return
            reap_agent(agent)
    """
    lock_id = (namespace, key)
    held = _held_locks()

    # Reentrancy: if we already hold this lock, skip (don't deadlock).
    if lock_id in held:
        logger.debug(
            f"advisory_lock_or_skip: already held by this thread, "
            f"skipping: ns={namespace} key={key}"
        )
        yield False
        return

    conn = db.engine.connect()
    acquired = False
    try:
        result = conn.execute(
            text("SELECT pg_try_advisory_lock(:ns, :key)"),
            {"ns": namespace, "key": key}
        )
        acquired = result.scalar()

        if acquired:
            held.add(lock_id)
            logger.debug(
                f"advisory_lock_or_skip acquired: ns={namespace} key={key}"
            )
        else:
            logger.debug(
                f"advisory_lock_or_skip skipped: ns={namespace} key={key}"
            )

        yield acquired

    finally:
        if acquired:
            held.discard(lock_id)
            try:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :key)"),
                    {"ns": namespace, "key": key}
                )
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def lock_key_from_string(name: str) -> int:
    """
    Convert a string to a 64-bit advisory lock key via BLAKE2b.

    For use cases where the lock target doesn't have an integer ID
    (e.g., file paths, function names). Not needed for the primary
    per-agent locking pattern.

    NOTE: Returns a 64-bit key for use with the single-argument form
    pg_advisory_lock(bigint), NOT the two-argument (int4, int4) form
    used by advisory_lock(). Do not pass this value as 'key' to
    advisory_lock() — int4 overflow will occur for large values.
    """
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return struct.unpack("q", digest)[0]
```

### 3.2 Connection Pool Impact

Each locked operation uses **2 connections**: 1 for the advisory lock, 1 for `db.session`.

| Current Pool Config | Value |
|---------------------|-------|
| `pool_size` | 10 |
| `max_overflow` | 5 |
| **Total available** | **15** |

| Concurrent Scenario | Lock Connections | Work Connections | Total |
|---------------------|-----------------|------------------|-------|
| 1 agent processing hook | 1 | 1 | 2 |
| 3 agents processing hooks | 3 | 3 | 6 |
| 3 hooks + reaper + reconciler | 5 | 5 | 10 |
| 5 hooks + reaper + reconciler + context poller | 8 | 8 | 16 |
| 5 hooks + reaper + reconciler + poller + watchdog + 2 deferred stops | 10 | 10 | 20 |

**Note:** EventWriter and InferenceService use independent engines with their own pools (5 and 3 connections respectively) — they do NOT count against the main pool.

**Recommendation:** Increase `pool_size` from 10 to 15 and `max_overflow` from 5 to 10 (total 25) to provide headroom for peak concurrent scenarios. This adds ~5 idle PostgreSQL connections — negligible cost. Under the realistic worst case (20 connections), this leaves 5 connections of headroom.

**Config change:** `config.yaml` → `database.pool_size: 15`, `database.max_overflow: 10`

### 3.3 Lock Acquisition Patterns

#### Pattern A: Hook Routes (Blocking)

All 8 hook routes that process agent state acquire `advisory_lock(AGENT, agent.id)` after session correlation. The `hook_status` route is read-only and does NOT need a lock.

```python
# routes/hooks.py — applied to each hook route
@hooks_bp.route("/hook/user-prompt-submit", methods=["POST"])
@rate_limited
def hook_user_prompt_submit():
    # ... extract payload ...
    agent = correlate_session(...)
    db.session.commit()  # agent.id is now persisted

    with advisory_lock(LockNamespace.AGENT, agent.id):
        result = process_user_prompt_submit(agent, ...)
        # Multiple db.session.commit() calls inside are safe

    return jsonify(result)
```

**Routes requiring AGENT lock:**
| Route | Handler |
|-------|---------|
| `/hook/session-start` | `process_session_start()` |
| `/hook/session-end` | `process_session_end()` |
| `/hook/user-prompt-submit` | `process_user_prompt_submit()` |
| `/hook/stop` | `process_stop()` |
| `/hook/notification` | `process_notification()` |
| `/hook/post-tool-use` | `process_post_tool_use()` |
| `/hook/pre-tool-use` | `process_pre_tool_use()` |
| `/hook/permission-request` | `process_permission_request()` |

**Routes NOT requiring lock:**
| Route | Reason |
|-------|--------|
| `/hook/status` | Read-only status check |

#### Pattern B: Deferred Stop Thread (Blocking, Post-Sleep)

The deferred stop thread does a sleep/retry loop to wait for transcript content. The lock is acquired **AFTER** the sleep loop, just before state mutation.

```python
# hook_deferred_stop.py — _run_deferred_stop()
def _run_deferred_stop(self, agent_id, command_id, ...):
    # Phase 1: Sleep/retry WITHOUT lock
    agent_text = None
    for delay in [0.5, 1.0, 1.5, 2.0]:
        time.sleep(delay)
        agent_text = self._extract_transcript(...)
        if agent_text:
            break

    if not agent_text:
        return  # No transcript found after retries

    # Phase 2: State mutation WITH lock
    with self._app.app_context():
        with advisory_lock(LockNamespace.AGENT, agent_id, timeout=30.0):
            command = db.session.get(Command, command_id)
            db.session.refresh(command)

            if command.state == CommandState.COMPLETE:
                return  # Already completed by session_end hook

            lifecycle.complete_command(command, ...)
            db.session.commit()
```

**Timeout 30s:** Deferred stop may wait for an in-progress hook (up to 15s) plus processing time.

#### Pattern C: Background Threads (Non-Blocking, Skip)

Background threads use `advisory_lock_or_skip` — if the lock is held (by a hook or another background thread), they skip this agent and retry on the next cycle.

```python
# agent_reaper.py — _reap_agent()
def _reap_agent(self, agent, reason, now):
    with advisory_lock_or_skip(LockNamespace.AGENT, agent.id) as acquired:
        if not acquired:
            logger.info(f"Skipping reap for agent {agent.id} — lock held")
            return ReapResult(skipped=True)

        agent.ended_at = now
        self._complete_orphaned_commands(agent)
        db.session.commit()  # MUST commit inside the lock scope
```

**Critical — two rules for the reaper:**

**Rule 1: Commit inside the lock.** The current reaper does a batch commit after the loop (`if result.reaped > 0: db.session.commit()`). This is **incompatible** with per-agent advisory locking — the lock releases before the commit, creating a window where another thread reads uncommitted state. The reaper must be restructured to **commit per-agent inside the lock scope**.

**Rule 2: Lock per iteration, not across the loop.** Each agent gets its own lock-acquire-work-commit-release cycle. This prevents pool exhaustion when processing many agents.

```python
# CORRECT: lock + commit per iteration
for agent in agents_to_reap:
    with advisory_lock_or_skip(LockNamespace.AGENT, agent.id) as acquired:
        if acquired:
            self._reap_agent(agent, reason, now)
            db.session.commit()  # Commit INSIDE the lock
    # Lock connection returned to pool before next iteration

# WRONG: batch commit after loop (lock released before commit)
for agent in agents_to_reap:
    with advisory_lock_or_skip(LockNamespace.AGENT, agent.id) as acquired:
        if acquired:
            self._reap_agent(agent, reason, now)
db.session.commit()  # TOO LATE — locks already released
```

**Services using Pattern C:**
| Service | Lock Key | Skip Behaviour |
|---------|----------|----------------|
| AgentReaper | `agent.id` | Skip agent, retry next cycle (60s) |
| TranscriptReconciler | `agent.id` | Skip reconciliation, retry next cycle |
| ContextPoller | `agent.id` | Skip poll, retry next cycle |
| TmuxWatchdog | `agent.id` | Skip check, retry next cycle |

#### Pattern D: API Routes (Blocking with Timeout)

API endpoints that mutate agent state (handoff, dismiss, respond) acquire the lock with a shorter timeout.

```python
# Handoff executor
def trigger_handoff(self, agent_id, reason, ...):
    with advisory_lock(LockNamespace.AGENT, agent_id, timeout=10.0):
        validation = self.validate_preconditions(agent_id)
        if not validation.success:
            return validation

        agent = db.session.get(Agent, agent_id)
        # ... send instruction, create record ...
        db.session.commit()
```

---

## 4. Race-by-Race Fix Specifications

### 4.1 Phase 1: CRITICAL Fixes

#### CRITICAL 1: State Machine Transitions

**Race:** Two threads read `command.state`, both validate, both transition.

**Fix:** Subsumed by AGENT lock. All state transitions happen within hook processing (Pattern A) or background threads (Pattern C). Only one thread operates on an agent at a time.

**Code changes:**
- `routes/hooks.py` — wrap all hook routes with `advisory_lock` (Pattern A)
- No changes to `command_lifecycle.py` or `state_machine.py` — they don't commit, so they work within the caller's lock scope

**Verification:** Under the agent lock, `command.state` reads are always fresh (only one writer). The existing `db.session.refresh(command)` calls in lifecycle methods provide additional safety.

---

#### CRITICAL 2: Concurrent Hooks Per Agent

**Race:** Two hook requests for the same agent process simultaneously.

**Fix:** Pattern A in `routes/hooks.py`. All 8 mutating hook routes acquire `advisory_lock(AGENT, agent.id)` before calling `process_*()`.

**Code changes:**
- `routes/hooks.py` — add lock acquisition to each of 8 hook route handlers (see Section 3.3, Pattern A)
- Add import of `advisory_lock` and `LockNamespace`

**Claude Code impact:** Claude Code fires hooks synchronously and waits for the HTTP response. Under normal operation, locks are uncontested (one hook at a time per agent). Under contention (e.g., rapid stop + session_end), the second hook waits up to 15s. This is correct behaviour — serialisation is the goal.

---

#### CRITICAL 3: Skill Injector Double Injection

**Race:** Two threads check `prompt_injected_at IS NULL`, both inject.

**Fix:** Subsumed by AGENT lock. Skill injection is called from `process_session_start()`, which runs inside the AGENT lock (Pattern A). Two concurrent session_start hooks for the same agent are serialised — the second one re-reads `prompt_injected_at` and finds it already set.

**Code changes:** None to `skill_injector.py`. The fix is the AGENT lock in `routes/hooks.py`.

**Defence in depth:** Add `db.session.refresh(agent)` before the `prompt_injected_at` check in `inject_persona_skills()` to ensure a fresh read even if called from an unexpected path.

---

### 4.2 Phase 2: HIGH Fixes

#### HIGH 1: AgentReaper vs Hooks

**Race:** Reaper and hooks both call `complete_command()` on the same command.

**Fix:** Pattern C in `agent_reaper.py`. Reaper uses `advisory_lock_or_skip(AGENT, agent.id)`. If a hook holds the lock, reaper skips this agent (retries in 60s).

**Code changes:**
- `agent_reaper.py` — wrap `_reap_agent()` with `advisory_lock_or_skip`
- Ensure lock is per-agent-iteration, not across the loop

---

#### HIGH 2: Summarisation Duplicate LLM Calls

**Race:** Two threads check `turn.summary IS NULL`, both call LLM.

**Fix:** Two-layer approach:
1. Primary: Most summarisation is triggered from hook processing (inside AGENT lock) or from reaper (inside AGENT lock). Under the agent lock, only one thread processes an agent's turns.
2. Supplementary: For edge cases where summarisation is triggered from outside a lock (e.g., dashboard backfill), add `SELECT ... FOR UPDATE NOWAIT` on the turn row before the LLM call:

```python
# summarisation_service.py — summarise_turn()
def summarise_turn(self, turn, db_session=None):
    if turn.summary:
        return turn.summary  # Fast path

    # Atomic check under row lock
    session = db_session or db.session
    try:
        locked_turn = (
            session.query(Turn)
            .filter_by(id=turn.id)
            .with_for_update(nowait=True)
            .first()
        )
    except OperationalError:
        return None  # Another thread is summarising this turn

    if locked_turn and locked_turn.summary:
        return locked_turn.summary

    # ... proceed with LLM call ...
```

**Code changes:**
- `summarisation_service.py` — add `with_for_update(nowait=True)` check in `summarise_turn()`

---

#### HIGH 3: Deferred Stop vs Session End

**Race:** Both call `complete_command()` on the same command.

**Fix:** Pattern B for deferred stop (lock AFTER sleep loop). Session_end hook uses Pattern A. Both acquire the same AGENT lock — serialised.

**Code changes:**
- `hook_deferred_stop.py` — restructure `_run_deferred_stop()` to acquire AGENT lock after sleep/retry, before state mutation
- Add `db.session.refresh(command)` + state check after lock acquisition

**Sequence under fix:**
1. `stop` hook fires → holds AGENT lock → sees empty transcript → schedules deferred stop → releases lock
2. `session_end` hook fires → acquires AGENT lock → calls `complete_command()` → command.state = COMPLETE → releases lock
3. Deferred stop wakes up → acquires AGENT lock → re-reads command.state = COMPLETE → skips

---

#### HIGH 4: Progress Capture vs Reconciler

**Race:** Both create turns from the same JSONL entries.

**Fix:** Pattern C for reconciler. Progress capture runs within hook processing (Pattern A, inside AGENT lock). Reconciler uses `advisory_lock_or_skip(AGENT, agent.id)` — skips if a hook is processing this agent.

**Code changes:**
- `transcript_reconciler.py` — wrap `reconcile_agent_session()` and `reconcile_transcript_entries()` with `advisory_lock_or_skip(AGENT, agent.id)`
- **Remove** the existing per-agent `threading.Lock` in `get_reconcile_lock()` — superseded by advisory lock
- `hook_agent_state.py` — **remove** the `_progress_capture_locks` dict in `AgentHookState` — superseded by AGENT lock
- `hook_receiver.py` — **remove** `_progress_capture_locks` usage from the progress capture path

---

#### HIGH 5: Card State Stale ORM Reads *(Deferred to Phase 4)*

**Not a locking issue. Separate workstream: session hygiene.**

**Fix:** Add `db.session.expire(agent)` or `db.session.refresh(agent)` at the start of `build_card_state()`.

---

#### HIGH 6: Config Editor TOCTOU

**File-level concern. Use `fcntl.flock()`.**

**Code changes:**
- `config_editor.py` — wrap read-modify-write with file lock:

```python
import fcntl

def save_config(self, updates):
    lock_path = str(self._config_path) + ".lock"
    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            current = self._load_config()
            merged = self._deep_merge(current, updates)
            self._validate(merged)
            self._write_atomic(merged)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
```

---

#### HIGH 7: Handoff Executor Double Initiation

**Race:** Two API calls both pass precondition validation before either creates a record.

**Fix:** Pattern D. `advisory_lock(AGENT, agent_id)` around precondition check + execution.

**Code changes:**
- `handoff_executor.py` — wrap `trigger_handoff()` with `advisory_lock(AGENT, agent_id)`
- Remove module-level `_handoff_lock = threading.Lock()` — superseded by advisory lock

---

#### HIGH 8: Remote Agent Service Stale Reads

**Race:** Agent reaped between readiness check and prompt send.

**Fix:** `advisory_lock(AGENT, agent.id)` around the readiness-to-send window. Reaper can't reap while this lock is held.

**Code changes:**
- `remote_agent_service.py` — after polling loop detects readiness, acquire AGENT lock, re-check `agent.ended_at`, then send prompt

---

### 4.3 Phase 3: MEDIUM/LOW Fixes

Most MEDIUM/LOW races are automatically resolved by the AGENT lock from Phases 1-2. Remaining items:

| Race | Resolution |
|------|------------|
| ContextPoller stale reads | Pattern C — skip if AGENT lock held |
| TmuxWatchdog concurrent reconciliation | Pattern C — skip if AGENT lock held |
| FileWatcher + polling timer | Subsumed by reconciler's AGENT lock |
| PriorityScoring debounce | Existing debounce lock sufficient; advisory lock not needed |
| Notification + stop race | Subsumed by AGENT lock on hook routes |
| Stop hook + deferred stop hash bypass | Subsumed by AGENT lock (deferred stop waits) |
| Two-commit incomplete | Transactional integrity — not a concurrency issue; deferred to Phase 4 (savepoints) |
| Agent creation race | `ON CONFLICT` already handles; cache coherence is session hygiene |
| NotificationService rate limiter | Subsumed by AGENT lock on hooks |
| SessionToken overwrite | In-memory thread lock sufficient for single-process |
| Persona registration slug | DB unique constraint handles it |
| Respond inflight timeout | Subsumed by AGENT lock on hooks |
| Broadcaster event ordering | Eventual consistency, acceptable |
| Voice Bridge upload quota | Low risk; `fcntl.flock()` on upload directory if needed |

### 4.4 Monitoring

**New endpoint:** `GET /api/advisory-locks`

```python
# routes/debug.py (or similar)
@debug_bp.route("/api/advisory-locks")
def advisory_locks():
    """Show currently held advisory locks."""
    result = db.session.execute(text("""
        SELECT l.pid, a.application_name, a.state, a.query_start,
               l.classid AS namespace, l.objid AS entity_id,
               l.mode, l.granted,
               now() - a.query_start AS duration
        FROM pg_locks l
        JOIN pg_stat_activity a ON l.pid = a.pid
        WHERE l.locktype = 'advisory'
        ORDER BY a.query_start
    """))
    locks = [dict(row._mapping) for row in result]
    return jsonify({"advisory_locks": locks, "count": len(locks)})
```

**Logging:** All lock acquisitions, releases, skips, and timeouts are logged at DEBUG level. Lock contention (timeout errors) logged at WARNING.

---

## 5. In-Memory Locks to Remove

After advisory locks are in place, these in-memory locks become redundant:

| Current Lock | Location | Replaced By |
|-------------|----------|-------------|
| `_progress_capture_locks` (per-agent dict) | `hook_agent_state.py:54-58` | AGENT advisory lock |
| `get_reconcile_lock()` (per-agent dict) | `transcript_reconciler.py:33-38` | AGENT advisory lock |
| `_handoff_lock` (global Lock) | `handoff_executor.py:38` | AGENT advisory lock |

**DO NOT remove** these locks:
| Lock | Location | Reason to Keep |
|------|----------|----------------|
| `Broadcaster._lock` | `broadcaster.py:86` | Protects in-memory client registry (not a DB concern) |
| `SessionRegistry._lock` | `session_registry.py:32` | Protects in-memory session dict |
| `SessionTokenService._lock` | `session_token.py:36` | Protects in-memory token store |
| `InferenceCache._lock` | `inference_cache.py:36` | Protects in-memory LRU cache |
| `InferenceRateLimiter._lock` | `inference_rate_limiter.py:29` | Protects in-memory sliding window |
| `NotificationService._rate_limit_lock` | `notification_service.py:34` | Protects in-memory rate tracker |
| `PriorityScoringService._debounce_lock` | `priority_scoring.py:22` | Debounce timer coordination |
| `PriorityScoringService._scoring_lock` | `priority_scoring.py:23` | Prevents concurrent scoring runs |
| `AgentHookState._lock` | `hook_agent_state.py:31` | Protects in-memory state dicts |
| `TmuxWatchdog._lock` | `tmux_watchdog.py:42` | Protects in-memory hash/gap dicts |
| `EventWriterMetrics._lock` | `event_writer.py:42` | Protects in-memory metrics |

---

## 6. Code Modification Summary

### New Files

| File | Purpose |
|------|---------|
| `src/claude_headspace/services/advisory_lock.py` | Advisory lock service (context managers + utilities) |
| `tests/services/test_advisory_lock.py` | Unit tests for lock service |
| `tests/integration/test_advisory_lock_concurrency.py` | Concurrency tests (multi-threaded) |

### Modified Files — Phase 1 (CRITICAL)

| File | Changes |
|------|---------|
| `src/claude_headspace/routes/hooks.py` | Add `advisory_lock(AGENT, agent.id)` to 8 hook routes |
| `src/claude_headspace/services/skill_injector.py` | Add `db.session.refresh(agent)` before `prompt_injected_at` check (defence in depth) |

### Modified Files — Phase 2 (HIGH)

| File | Changes |
|------|---------|
| `src/claude_headspace/services/hook_deferred_stop.py` | Restructure: sleep loop first, advisory lock second; add state re-check |
| `src/claude_headspace/services/agent_reaper.py` | Add `advisory_lock_or_skip(AGENT, agent.id)` per-agent in reap loop |
| `src/claude_headspace/services/transcript_reconciler.py` | Add `advisory_lock_or_skip(AGENT, agent.id)`; remove `get_reconcile_lock()` |
| `src/claude_headspace/services/summarisation_service.py` | Add `with_for_update(nowait=True)` check in `summarise_turn()` |
| `src/claude_headspace/services/handoff_executor.py` | Add `advisory_lock(AGENT, agent_id)` in `trigger_handoff()`; remove `_handoff_lock` |
| `src/claude_headspace/services/remote_agent_service.py` | Add `advisory_lock(AGENT, agent.id)` around readiness-to-send window |
| `src/claude_headspace/services/config_editor.py` | Add `fcntl.flock()` around read-modify-write |
| `src/claude_headspace/services/hook_agent_state.py` | Remove `_progress_capture_locks` dict |
| `src/claude_headspace/services/hook_receiver.py` | Remove `_progress_capture_locks` usage from progress capture path |

### Modified Files — Phase 3 (MEDIUM/LOW + Monitoring)

| File | Changes |
|------|---------|
| `src/claude_headspace/services/context_poller.py` | Add `advisory_lock_or_skip(AGENT, agent.id)` per-agent |
| `src/claude_headspace/services/tmux_watchdog.py` | Add `advisory_lock_or_skip(AGENT, agent.id)` per-agent |
| `src/claude_headspace/routes/debug.py` (or new) | Add `/api/advisory-locks` monitoring endpoint |
| `config.yaml` | Increase `pool_size` to 15, `max_overflow` to 10 |

---

## 7. Testing Strategy

### Unit Tests (`tests/services/test_advisory_lock.py`)

1. **Lock acquisition and release** — verify lock is acquired, held during block, and released after
2. **Timeout behaviour** — verify `AdvisoryLockError` raised after timeout
3. **Non-blocking skip** — verify `advisory_lock_or_skip` yields `False` when lock is held
4. **Connection cleanup** — verify connection returned to pool even on exceptions
5. **Lock key hashing** — verify `lock_key_from_string` produces consistent, deterministic keys
6. **Nested context manager safety** — verify no resource leaks when exceptions occur in the body

### Concurrency Tests (`tests/integration/test_advisory_lock_concurrency.py`)

1. **Two threads, same lock** — verify serialisation (thread 2 waits for thread 1)
2. **Two threads, different agents** — verify no interference (both proceed)
3. **Hook + reaper contention** — verify reaper skips when hook holds lock
4. **Deferred stop + session_end** — verify deferred stop sees COMPLETE state after session_end
5. **Pool exhaustion safety** — verify 15+ concurrent lock attempts don't deadlock (they should timeout)
6. **Reentrancy detection** — verify nested `advisory_lock()` for the same agent raises `AdvisoryLockError` immediately (does not deadlock)
7. **Reaper per-iteration commit** — verify processing N agents uses at most 2 connections at any point (1 lock + 1 work), not 2*N
8. **Exception during body with intermediate commits** — verify lock is released when exception occurs after `db.session.commit()` calls inside the `with` block
9. **Unconditional unlock safety** — verify `pg_advisory_unlock` in finally block returns FALSE gracefully when lock was not acquired (simulates Bug #17686 cleanup)
10. **advisory_lock_or_skip reentrancy** — verify yields False (not deadlock) when same thread already holds the lock

### Regression Tests

Each race condition fix should include a targeted test that reproduces the original race (using `threading.Barrier` or `threading.Event` to synchronise two threads at the critical point) and verifies the lock prevents it.

---

## 8. Rollout Plan

### Phase 1: Foundation + CRITICAL (Week 1)
1. Implement `advisory_lock.py`
2. Write unit tests
3. Increase pool_size in config.yaml
4. Add AGENT lock to all hook routes
5. Add `db.session.refresh()` to skill injector
6. Write concurrency tests for CRITICAL races
7. Deploy and monitor lock contention via logs

### Phase 2: HIGH Fixes (Week 2)
1. Apply advisory locks to reaper, deferred stop, reconciler
2. Add row-level lock to summarisation service
3. Add advisory locks to handoff executor and remote agent service
4. Add file lock to config editor
5. Remove superseded in-memory locks
6. Write concurrency tests for HIGH races

### Phase 3: MEDIUM/LOW + Monitoring (Week 3)
1. Apply advisory locks to context poller, tmux watchdog
2. Add `/api/advisory-locks` monitoring endpoint
3. Add lock contention metrics
4. Address remaining MEDIUM/LOW items
5. Full regression test suite

### Phase 4: Session Hygiene (Separate Workstream)
1. Audit all `db.session` usage in background threads
2. Add `db.session.refresh()` / `db.session.expire()` at appropriate points
3. Address Card State staleness (HIGH 5)
4. Address stale ORM reads in context poller, file watcher

---

## 9. Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Lock contention degrades hook response time | Medium | Low (hooks are sequential per agent) | 15s timeout; monitoring endpoint |
| Pool exhaustion from lock connections | High | Low (max ~10 concurrent locks typical) | Increased total pool to 25 (pool_size=15, max_overflow=10); per-iteration release in loops |
| Leaked lock on crash | Medium | Very Low (PostgreSQL releases on disconnect) | Session-scoped locks auto-release; unconditional unlock in finally; pool_recycle=3600 as backstop |
| Deadlock from nested locking | Critical | None (reentrancy detection) | Thread-local held-lock tracking raises AdvisoryLockError on nested acquisition attempt |
| PostgreSQL Bug #17686 (phantom lock on timeout) | High | Very Low (requires lock contention + exact timing) | Unconditional `pg_advisory_unlock` in finally block; returns FALSE if lock not held |
| Lock connection drop mid-operation | Medium | Very Low (requires PostgreSQL restart mid-request) | PostgreSQL releases all session-scoped locks on backend termination; accepted risk — broader app failure would occur regardless |
| Background task starvation | Low | Low (skip + retry next cycle) | 60s retry; monitoring for repeated skips |
| Regression in hook processing | High | Medium (touching all hook routes) | Phased rollout; comprehensive testing |
| Agent record orphaned on lock timeout | Low | Very Low (new agent = no contention) | Reaper cleans up orphaned agents after grace period |

---

## 10. Design Decisions Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Session-scoped locks (not transaction-scoped) | Hook processing does 2-8 intermediate commits; transaction-scoped locks release on commit | Transaction-scoped: pool-safe but breaks on intermediate commits |
| Dedicated connection per lock | Lock independence from `db.session`; survives application commits | Same-session locks: risk of pool contamination if connection returned with lock held |
| Single AGENT namespace (not fine-grained) | Fine-grained namespaces (8) caused 7 nested lock scenarios and deadlock risk | Fine-grained: more concurrency but violates single-lock-per-path rule |
| Blocking for hooks, non-blocking for background | Hooks MUST process (data loss if skipped); background can retry next cycle | All blocking: background threads hold up each other unnecessarily |
| `lock_timeout` (not `statement_timeout`) | `lock_timeout` is the correct PostgreSQL parameter for lock wait timeouts; does not interfere with statement execution timing | `statement_timeout`: measures total statement time, less precise for lock waits |
| Unconditional unlock in finally block | PostgreSQL Bug #17686: timeout can fire after lock is acquired; unconditional unlock prevents phantom lock leaks | Conditional unlock: simpler but risks leaked locks under contention + timeout race |
| Thread-local reentrancy detection | Nested `advisory_lock()` calls for the same key on different connections would deadlock; fail-fast prevents this | No detection: relies on code review to prevent nesting (fragile) |
| `fcntl.flock()` for config (not advisory lock) | Config editing is a file operation; may not have a DB session available | Advisory lock: works but requires DB connection for a file operation |
| No third-party library | ~80 lines of code; full control; no unnecessary dependencies | PALs: brings its own pool. sqlalchemy-dlock: adds dependency for simple functionality |
| BLAKE2b for string keys | Deterministic, fast, 64-bit, cross-process safe | Python `hash()`: not cross-process safe. CRC32: too small (32-bit) |

---

## Appendix A: PostgreSQL Advisory Lock Reference

```sql
-- Session-scoped (used in this design)
SELECT pg_advisory_lock(key1, key2);       -- Blocking acquire
SELECT pg_try_advisory_lock(key1, key2);   -- Non-blocking (returns bool)
SELECT pg_advisory_unlock(key1, key2);     -- Explicit release
SELECT pg_advisory_unlock_all();           -- Release ALL session locks

-- Transaction-scoped (NOT used — releases on commit)
SELECT pg_advisory_xact_lock(key1, key2);
SELECT pg_try_advisory_xact_lock(key1, key2);

-- Monitoring
SELECT pid, classid AS namespace, objid AS entity_id, mode, granted
FROM pg_locks WHERE locktype = 'advisory';
```

**Key properties:**
- Session-scoped locks survive COMMIT and ROLLBACK
- Session-scoped locks are released on connection close (or explicit unlock)
- Session-scoped locks are reentrant **on the same connection** (same session can acquire N times; must unlock N times). **Caution:** This design uses a NEW dedicated connection per `advisory_lock()` call — nested calls for the same key on different connections will deadlock. The thread-local reentrancy detection in Section 3.1 prevents this.
- Advisory locks work across all connections to the same database
- Advisory locks are stored in shared memory, not on disk — very fast

## Appendix B: Race Condition Audit Cross-Reference

| # | Race Condition | Severity | Phase | Fix Mechanism |
|---|---------------|----------|-------|---------------|
| C1 | State machine transitions | CRITICAL | 1 | AGENT lock on hook routes |
| C2 | Concurrent hooks per agent | CRITICAL | 1 | AGENT lock on hook routes |
| C3 | Skill injector double injection | CRITICAL | 1 | AGENT lock on hook routes + refresh |
| H1 | AgentReaper vs hooks | HIGH | 2 | AGENT lock_or_skip in reaper |
| H2 | Summarisation duplicate LLM | HIGH | 2 | SELECT FOR UPDATE NOWAIT on turn |
| H3 | Deferred stop vs session_end | HIGH | 2 | AGENT lock in deferred stop (post-sleep) |
| H4 | Progress capture vs reconciler | HIGH | 2 | AGENT lock; remove in-memory locks |
| H5 | Card State stale ORM | HIGH | 4 | Session hygiene (separate workstream) |
| H6 | Config Editor TOCTOU | HIGH | 2 | fcntl.flock() |
| H7 | Handoff Executor double init | HIGH | 2 | AGENT lock in trigger_handoff |
| H8 | Remote Agent stale reads | HIGH | 2 | AGENT lock around send window |
| M1 | ContextPoller stale reads | MEDIUM | 3 | AGENT lock_or_skip |
| M2 | TmuxWatchdog reconciliation | MEDIUM | 3 | AGENT lock_or_skip |
| M3 | FileWatcher races | MEDIUM | 3 | Subsumed by reconciler lock |
| M4 | PriorityScoring debounce | MEDIUM | — | Existing lock sufficient |
| M5 | Notification + stop race | MEDIUM | 1 | Subsumed by AGENT lock on hooks |
| M6 | Stop + deferred stop hash | MEDIUM | 2 | Subsumed by AGENT lock |
| M7 | Two-commit incomplete | MEDIUM | 4 | Transactional integrity — not a concurrency race. Deferred to session hygiene workstream. Fix: use `db.session.begin_nested()` (savepoint) so turn + state transition can be rolled back atomically on failure |
| M8 | Agent creation race | MEDIUM | — | ON CONFLICT already handles |
| M9 | Respond inflight timeout | MEDIUM | 1 | Subsumed by AGENT lock on hooks |
| L1 | NotificationService rate limiter | LOW | 1 | Subsumed by AGENT lock on hooks |
| L2 | SessionToken overwrite | LOW | — | Existing thread lock sufficient |
| L3 | Tmux Bridge stop delay | LOW | — | Design limitation, not race |
| L4 | Persona registration slug | LOW | — | DB unique constraint handles |
| L5 | Broadcaster event order | LOW | — | Eventual consistency, acceptable |
| L6 | Voice Bridge upload quota | LOW | — | fcntl.flock if needed |
