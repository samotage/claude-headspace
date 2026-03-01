# advisory-locking Specification

## Purpose
TBD - created by archiving change advisory-locking. Update Purpose after archive.
## Requirements
### Requirement: Advisory Lock Service

The system SHALL provide a PostgreSQL advisory lock service that uses session-scoped advisory locks on dedicated connections, independent of the application's `db.session` transactions.

#### Scenario: Blocking lock acquisition (hook routes)

- **WHEN** a hook route processes an agent event
- **AND** `advisory_lock(LockNamespace.AGENT, agent.id)` is called
- **THEN** the system SHALL acquire a PostgreSQL session-scoped advisory lock on a dedicated connection
- **AND** the lock SHALL survive all intermediate `db.session.commit()` calls within the block
- **AND** the lock SHALL be released when the context manager exits

#### Scenario: Lock timeout

- **WHEN** `advisory_lock(LockNamespace.AGENT, agent.id, timeout=15.0)` is called
- **AND** another connection holds the same advisory lock
- **AND** the lock is not released within the timeout period
- **THEN** the system SHALL raise `AdvisoryLockError`
- **AND** the dedicated connection SHALL be closed and returned to the pool

#### Scenario: Non-blocking lock (background threads)

- **WHEN** a background thread calls `advisory_lock_or_skip(LockNamespace.AGENT, agent.id)`
- **AND** another connection holds the same advisory lock
- **THEN** the context manager SHALL yield `False`
- **AND** the caller SHALL skip processing for this agent
- **AND** no exception SHALL be raised

#### Scenario: Non-blocking lock acquired

- **WHEN** a background thread calls `advisory_lock_or_skip(LockNamespace.AGENT, agent.id)`
- **AND** no other connection holds the same advisory lock
- **THEN** the context manager SHALL yield `True`
- **AND** the lock SHALL be held until the context manager exits

#### Scenario: Reentrancy detection

- **WHEN** code inside an `advisory_lock(AGENT, X)` block calls `advisory_lock(AGENT, X)` again
- **THEN** the system SHALL raise `AdvisoryLockError` immediately
- **AND** the system SHALL NOT deadlock
- **AND** the outer lock SHALL remain held

#### Scenario: Reentrancy in non-blocking mode

- **WHEN** code inside an `advisory_lock(AGENT, X)` block calls `advisory_lock_or_skip(AGENT, X)`
- **THEN** the context manager SHALL yield `False`
- **AND** the system SHALL NOT deadlock

#### Scenario: Connection cleanup on exception

- **WHEN** an exception occurs inside the `advisory_lock` block
- **THEN** the lock SHALL be released via `pg_advisory_unlock`
- **AND** the dedicated connection SHALL be closed and returned to the pool
- **AND** the exception SHALL propagate to the caller

#### Scenario: PostgreSQL Bug #17686 (phantom lock)

- **WHEN** `lock_timeout` fires after the lock was actually granted but before the result was returned
- **THEN** the finally block SHALL call `pg_advisory_unlock` unconditionally
- **AND** `pg_advisory_unlock` returning `TRUE` (lock was held) SHALL clean up the phantom lock
- **AND** `pg_advisory_unlock` returning `FALSE` (lock was not held) SHALL be a no-op

---

### Requirement: Hook Route Serialisation

All 8 mutating hook routes SHALL acquire `advisory_lock(LockNamespace.AGENT, agent.id)` after session correlation and before processing.

#### Scenario: Concurrent hooks for same agent

- **WHEN** two hook requests arrive simultaneously for the same agent
- **THEN** the first request SHALL acquire the lock and process immediately
- **AND** the second request SHALL block until the first completes (up to 15s timeout)
- **AND** the second request SHALL then acquire the lock and process with fresh state

#### Scenario: Hooks for different agents

- **WHEN** hook requests arrive simultaneously for different agents
- **THEN** each request SHALL acquire its own lock independently
- **AND** processing SHALL proceed in parallel without interference

#### Scenario: Read-only hook route

- **WHEN** the `/hook/status` route receives a request
- **THEN** no advisory lock SHALL be acquired
- **AND** the request SHALL be processed immediately

---

### Requirement: Background Thread Lock Pattern

Background threads (AgentReaper, TranscriptReconciler, ContextPoller, TmuxWatchdog) SHALL use `advisory_lock_or_skip` for per-agent processing.

#### Scenario: Background thread encounters locked agent

- **WHEN** a background thread processes an agent
- **AND** a hook route holds the AGENT advisory lock for that agent
- **THEN** the background thread SHALL skip processing for that agent
- **AND** the background thread SHALL retry on its next cycle

#### Scenario: Reaper commit-inside-lock

- **WHEN** the AgentReaper processes agents for reaping
- **THEN** each agent SHALL be processed in its own lock-acquire-work-commit-release cycle
- **AND** `db.session.commit()` SHALL occur inside the advisory lock scope
- **AND** the lock connection SHALL be returned to the pool before the next agent iteration

---

### Requirement: Deferred Stop Lock Acquisition

The deferred stop thread SHALL acquire the AGENT advisory lock AFTER its sleep/retry loop completes and BEFORE performing any state mutations.

#### Scenario: Deferred stop after session_end completes command

- **WHEN** the deferred stop thread wakes up and acquires the AGENT lock
- **AND** `session_end` has already completed the command
- **THEN** the deferred stop thread SHALL re-read `command.state` via `db.session.refresh(command)`
- **AND** the deferred stop thread SHALL find `state == COMPLETE`
- **AND** the deferred stop thread SHALL skip processing

#### Scenario: Deferred stop completes before session_end

- **WHEN** the deferred stop thread acquires the AGENT lock first
- **THEN** the deferred stop thread SHALL complete the command normally
- **AND** `session_end` SHALL subsequently acquire the lock and find the command already completed

---

### Requirement: Summarisation Dedup via Row Lock

The summarisation service SHALL use `SELECT ... FOR UPDATE NOWAIT` on the turn row before making an LLM call.

#### Scenario: Concurrent summarisation attempts

- **WHEN** two threads attempt to summarise the same turn simultaneously
- **THEN** the first thread SHALL acquire the row lock and proceed with the LLM call
- **AND** the second thread SHALL receive an `OperationalError` from `FOR UPDATE NOWAIT`
- **AND** the second thread SHALL return `None` without making an LLM call

#### Scenario: Turn already summarised

- **WHEN** a thread acquires the row lock for a turn
- **AND** `turn.summary` is already populated
- **THEN** the thread SHALL return the existing summary without making an LLM call

---

### Requirement: Config Editor File Lock

The config editor SHALL use `fcntl.flock()` around its read-modify-write cycle.

#### Scenario: Concurrent config saves

- **WHEN** two threads attempt to save config simultaneously
- **THEN** the first thread SHALL acquire the file lock and complete its save
- **AND** the second thread SHALL block until the first releases the lock
- **AND** the second thread SHALL then read the updated config before applying its merge

---

### Requirement: In-Memory Lock Removal

The following in-memory locks SHALL be removed after advisory locks are in place:

- `_progress_capture_locks` in `hook_agent_state.py` -- replaced by AGENT advisory lock
- `get_reconcile_lock()` in `transcript_reconciler.py` -- replaced by AGENT advisory lock
- `_handoff_lock` in `handoff_executor.py` -- replaced by AGENT advisory lock

#### Scenario: Existing in-memory locks retained

- **WHEN** an in-memory lock protects non-database state (broadcaster client registry, session registry, token store, inference cache, rate limiters)
- **THEN** the in-memory lock SHALL be retained
- **AND** the advisory lock system SHALL NOT interfere with these locks

---

### Requirement: Connection Pool Sizing

The database connection pool SHALL be sized to accommodate the dual-connection advisory lock pattern.

#### Scenario: Pool configuration

- **WHEN** the application starts
- **THEN** `pool_size` SHALL be 15 (increased from 10)
- **AND** `max_overflow` SHALL be 10 (increased from 5)
- **AND** total available connections SHALL be 25

---

### Requirement: Advisory Lock Monitoring

The system SHALL provide a monitoring endpoint for advisory lock visibility.

#### Scenario: Query advisory locks

- **WHEN** `GET /api/advisory-locks` is called
- **THEN** the system SHALL return all currently held advisory locks from `pg_locks`
- **AND** each lock entry SHALL include: pid, application_name, state, query_start, namespace, entity_id, mode, granted, duration
- **AND** the response SHALL include a total count

---

### Requirement: Skill Injector Defence in Depth

The skill injector SHALL refresh the agent record from the database before checking `prompt_injected_at`.

#### Scenario: Stale ORM read prevention

- **WHEN** `inject_persona_skills()` is called
- **THEN** the system SHALL call `db.session.refresh(agent)` before checking `agent.prompt_injected_at`
- **AND** if `prompt_injected_at` is not `None`, injection SHALL be skipped

