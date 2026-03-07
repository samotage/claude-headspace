# Proposal Summary: Redis-Backed Ephemeral State

## Architecture Decisions

1. **Single RedisManager service** — centralised connection pool management registered at `app.extensions["redis_manager"]`, providing namespaced key operations and health checks to all consuming services
2. **Graceful degradation over hard dependency** — every service maintains its existing in-memory data structures as fallback; Redis failure degrades performance (cache misses, lost rate limits) but never breaks functionality
3. **JSON serialisation only** — all Redis values use JSON for debuggability; no pickle/msgpack; datetime values as ISO 8601 strings
4. **Key namespace isolation** — all keys prefixed with configurable namespace (default `headspace:`) to share Redis instance safely
5. **TTL-based expiry over manual cleanup** — Redis key TTL replaces manual expiry checks; Redis MAXLEN caps replace manual deque size management
6. **Redis Streams for SSE replay** — replaces in-memory deque with XADD/XRANGE for durable, ID-based replay on client reconnection
7. **Tiered migration** — Tier 1 (cache, rate limits, counter) ships first as lowest-risk highest-impact; Tier 3 (summarisation queue, metrics, debounce, tokens) last
8. **fakeredis for testing** — unit tests use fakeredis mock; no real Redis dependency in CI

## Implementation Approach

The migration is a pure internal implementation swap. No service public API changes (method signatures, return types). Each service gains a `_redis` reference (from `app.extensions["redis_manager"]`) and wraps every Redis call in a try/except that falls back to the existing in-memory code path.

The `RedisManager` class owns the `redis.ConnectionPool`, exposes typed helper methods (get/set/hset/xadd/etc.), tracks `is_available` state with exponential backoff reconnect, and provides the `key()` method for namespace prefixing.

Services are migrated in 3 tiers, each independently deployable and testable. Each tier includes unit tests with fakeredis covering both Redis-available and Redis-unavailable scenarios.

## Files to Modify

### New Files
- `src/claude_headspace/services/redis_manager.py` — RedisManager service

### Service Files (internal implementation changes only)
- `src/claude_headspace/services/broadcaster.py` — replay buffer (Redis Stream), event ID (INCR)
- `src/claude_headspace/services/notification_service.py` — rate limit timestamps (SET EX/GET)
- `src/claude_headspace/services/inference_cache.py` — cache entries (SET EX/GET)
- `src/claude_headspace/services/hook_agent_state.py` — 10 per-agent state dicts (HSET/HGET, SADD/SREM)
- `src/claude_headspace/services/session_registry.py` — session dict (HSET/HGET with TTL refresh)
- `src/claude_headspace/services/event_writer.py` — metrics counters (HINCRBY/HSET)
- `src/claude_headspace/services/command_lifecycle.py` — pending summarisations (LPUSH/RPOP)
- `src/claude_headspace/services/priority_scoring.py` — debounce state (SET EX)
- `src/claude_headspace/services/session_token.py` — token store (HSET/HGET, optional Tier 3)

### Infrastructure Files
- `src/claude_headspace/app.py` — RedisManager init, startup recovery orchestration
- `src/claude_headspace/config.py` — redis section defaults
- `src/claude_headspace/routes/health.py` — Redis status reporting
- `config.yaml` — redis configuration section
- `pyproject.toml` — redis dependency

### Test Files (new)
- `tests/services/test_redis_manager.py`
- `tests/services/test_inference_cache_redis.py`
- `tests/services/test_notification_rate_limit_redis.py`
- `tests/services/test_broadcaster_redis.py`
- `tests/services/test_hook_agent_state_redis.py`
- `tests/services/test_session_registry_redis.py`
- `tests/services/test_event_writer_redis.py`
- `tests/services/test_command_lifecycle_redis.py`
- `tests/services/test_priority_scoring_redis.py`
- `tests/services/test_session_token_redis.py`
- `tests/integration/test_redis_startup_recovery.py`
- `tests/integration/test_redis_degradation.py`

## Acceptance Criteria

1. All 10 in-memory state systems survive werkzeug debug reload without data loss
2. All 10 systems survive full process restart (kill + restart) without data loss
3. SSE clients reconnecting after restart receive missed events via Redis Stream Last-Event-ID
4. No duplicate notifications fire after restart (rate limits persist)
5. Inference cache entries with remaining TTL available after restart
6. Pending summarisations from previous process are drained on startup
7. Agent hook state (deferred stops, transcript positions, prompt hashes) survives restarts
8. If Redis unavailable at startup, all services start normally with in-memory fallback + warning logs
9. If Redis becomes unavailable during operation, services continue with in-memory state + warning logs
10. Redis operations on hot paths complete in under 1ms (local Redis)
11. Health endpoint reports Redis status, memory usage, key count, and fallback mode per service
12. All tests pass with fakeredis (no real Redis dependency)

## Constraints and Gotchas

- **Phase 2 dependency:** This PRD is Phase 2 of restart resilience. Phase 1 (Channel Delivery Restart Resilience) should ship first.
- **No public API changes:** Method signatures and return types must remain identical. This is an internal implementation swap only.
- **No PostgreSQL changes:** No schema changes, no migrations.
- **No UI changes:** Dashboard behaviour is unchanged.
- **Redis password required:** The host Redis instance requires authentication; config must include password field.
- **werkzeug reloader creates new process:** On debug reload, the new process must recover state from Redis before serving requests. The old process's in-memory state is gone.
- **Thread safety:** Redis atomicity replaces Python threading.Lock in services like AgentHookState. Ensure the removal of locks doesn't introduce races for non-Redis fallback paths.
- **Serialisation round-trip:** datetime objects must survive JSON round-trip (serialize as ISO 8601, parse back). Test this explicitly.
- **fakeredis compatibility:** Ensure fakeredis supports Redis Streams (XADD/XRANGE/XLEN/XTRIM). If not, use a thin abstraction or mock at the RedisManager level.

## Git Change History

- **Related files:** No direct prior changes to the target service files in recent commit history related to Redis
- **OpenSpec history:** 1 prior change in archive (e5-s2-project-show-core) — unrelated
- **Patterns detected:** Standard service pattern with `app.extensions` registration, threading.Lock for thread safety, dataclass-based metrics
- **Recent activity:** Docs, persona work, handoff implementation, channel features — no overlap with this change

## Q&A History

No clarification questions were needed. The PRD was complete and unambiguous.

## Dependencies

- **Python package:** `redis>=5.0.0` (redis-py with connection pooling, Streams support)
- **Test package:** `fakeredis[lua]>=2.20.0` (mock Redis for unit tests, Lua scripting support for Streams)
- **Runtime:** Redis server (already installed and running on host)
- **No new migrations** (PostgreSQL is not touched)
- **No new APIs** (internal implementation change only)

## Testing Strategy

- **Unit tests:** Each migrated service gets a dedicated test file using fakeredis. Tests cover both Redis-available and Redis-unavailable (fallback) scenarios.
- **Integration tests:** Startup recovery flow tested with fakeredis. Degradation tested by disabling fakeredis mid-operation.
- **Manual verification:** Server restart with state persistence check. Redis stop/start with degradation check.
- **No E2E or agent-driven tests** (no UI or API changes).

## OpenSpec References

- **Proposal:** `openspec/changes/redis-backed-ephemeral-state/proposal.md`
- **Tasks:** `openspec/changes/redis-backed-ephemeral-state/tasks.md`
- **Spec:** `openspec/changes/redis-backed-ephemeral-state/specs/redis-ephemeral-state/spec.md`
