# Advisory Lock Design — Iteration 3 (Final)

## Design Evolution

**Iteration 1:** Transaction-scoped locks (`pg_advisory_xact_lock`)
→ Failed: hook processing does 2-8 intermediate commits that release the lock.

**Iteration 2:** Session-scoped locks on dedicated connection, 8 fine-grained namespaces
→ Failed: call graphs cross namespace boundaries creating 7 nested lock scenarios and deadlock risk.

**Iteration 3 (Final):** Single per-agent session-scoped lock on dedicated connection + supplementary row-level locks.
→ Eliminates all nesting. Zero deadlock risk. Covers all CRITICAL and HIGH races.

## Core Principle

**One lock per agent. Period.**

Almost every race condition in the audit involves concurrent operations on the same agent's state. By serialising all state-mutating operations per agent with a single lock, we eliminate the entire class of per-agent races without any risk of deadlock or nesting violations.

## Design Decisions

1. **Single per-agent lock** — `advisory_lock(AGENT, agent.id)` for all per-agent operations
2. **Session-scoped on dedicated connection** — lock survives `db.session.commit()` calls; independent of work connection
3. **Blocking with timeout for hooks** — hooks MUST be processed, not skipped (timeout: 15s)
4. **Non-blocking try-lock for background tasks** — reaper, reconciler skip if lock held (retry next cycle)
5. **Supplementary row-level locks** — `SELECT ... FOR UPDATE NOWAIT` for specific narrow critical sections (summarisation dedup)
6. **File-level lock for config** — `fcntl.flock()` for config.yaml TOCTOU
7. **No nesting** — each code path acquires at most one advisory lock
8. **BLAKE2b for string keys** — available for future use; primary path uses integer IDs

## Lock Namespace Registry (Simplified)

```python
class LockNamespace:
    AGENT = 1  # All per-agent operations (hooks, reaper, reconciler, deferred stop, handoff)
```

That's it. One namespace. The entity_id (second integer) is always `agent.id`.
