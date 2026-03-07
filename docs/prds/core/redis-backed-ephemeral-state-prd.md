---
validation:
  status: valid
  validated_at: '2026-03-07T17:00:39+11:00'
---

## Product Requirements Document (PRD) — Redis-Backed Ephemeral State

**Project:** Claude Headspace
**Scope:** Migrate 10 in-memory ephemeral state systems to Redis for server restart survivability
**Author:** Shorty (with Mark)
**Status:** Draft

---

## Executive Summary

Claude Headspace maintains critical operational state in 10 separate in-memory data structures across its service layer. Every server restart — whether a werkzeug debug reload during development or a full process restart in production — wipes all of this state simultaneously. The consequences include: SSE clients losing event history and requiring full page refreshes, duplicate macOS notifications firing, LLM inference cache misses causing redundant API calls (cost and latency), session tracking losing active agent metadata, and agent hook state losing conversation context.

This PRD specifies the requirements for introducing Redis as a durable backing store for all ephemeral state that currently lives in Python dicts, sets, deques, and Queues. Redis is already installed and running on the host machine. The migration must preserve existing service APIs (internal implementation swap only) and degrade gracefully if Redis becomes unavailable.

This is Phase 2 of a two-phase approach to server restart resilience. Phase 1 (Channel Delivery Restart Resilience — DB reconstruction) addresses the most acute pain point and should be shipped first. Phase 2 builds on Phase 1 by providing a comprehensive infrastructure-level solution.

---

## 1. Context & Purpose

### 1.1 Context

A comprehensive audit identified 10 in-memory systems that lose state on restart:

1. **Broadcaster replay buffer** — 500-event deque for SSE client reconnection
2. **Broadcaster per-client queues** — Queue(maxsize=1000) per connected SSE client
3. **Notification rate limits** — Per-agent and per-channel timestamp dicts preventing duplicate notifications
4. **EventWriter metrics** — Write success/failure counters
5. **Pending summarisations** — List of queued LLM summarisation requests awaiting execution
6. **Hook agent state** — 10 separate dicts tracking per-agent transient state (tool awaiting, respond pending, deferred stops, transcript positions, progress texts, file metadata, skill injection, prompt dedup hashes, command creation rate limits)
7. **Session registry** — Active session metadata for file watcher coordination
8. **Session tokens** — Remote agent authentication tokens (ephemeral by design, but Redis enables graceful reconnection)
9. **Inference cache** — 500-entry LRU cache with 5-minute TTL for LLM response deduplication
10. **Priority scoring debounce** — Pending async scoring timer

The current architecture is fully synchronous: process inline, broadcast once, forget. There are no background queue workers and no persistent state between requests beyond PostgreSQL. This makes every restart a clean-slate event that silently degrades multiple features.

### 1.2 Target User

Operators and developers running Claude Headspace, particularly during active development where werkzeug reloads are frequent. Also benefits production stability by ensuring state survives planned restarts and unexpected crashes.

### 1.3 Success Moment

The server restarts (werkzeug reload or full restart). SSE clients reconnect and seamlessly resume from where they left off. No duplicate notifications fire. The inference cache retains recent results. Agent hook state is intact. The operator notices nothing — the restart is invisible to the running system's behaviour.

---

## 2. Scope

### 2.1 In Scope

- Introduction of Redis as a dependency for ephemeral state persistence
- Redis connection management with configuration in `config.yaml`
- Migration of all 10 identified in-memory state systems to Redis-backed storage
- Graceful degradation: if Redis is unavailable, services fall back to in-memory operation with logged warnings
- SSE replay via Redis Streams replacing the in-memory deque
- Rate limiting via Redis keys with TTL replacing in-memory timestamp dicts
- Inference caching via Redis keys with TTL replacing in-memory LRU dict
- Pending summarisation queue via Redis list replacing in-memory Python list
- Agent hook state via Redis hashes with TTL replacing in-memory dicts
- Session registry via Redis hash with TTL replacing in-memory dict
- Atomic event ID counter via Redis INCR replacing in-memory counter
- EventWriter metrics via Redis hash replacing in-memory dataclass

### 2.2 Out of Scope

- PostgreSQL schema changes or migrations
- Changes to service public APIs (method signatures, return types)
- Redis Sentinel or Redis Cluster (single-instance Redis is sufficient for this use case)
- Migration of database-persisted state (Agent, Command, Turn, Message records)
- Redis-backed session storage for Flask (Flask sessions are not used)
- UI changes
- Performance optimisation beyond parity with current in-memory operations

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. All 10 identified in-memory state systems survive a werkzeug debug reload without data loss
2. All 10 systems survive a full server process restart (kill + restart) without data loss
3. SSE clients that reconnect after a restart receive missed events from Redis Streams using Last-Event-ID
4. Notification rate limits persist across restarts — no duplicate notifications fire after a reload
5. Inference cache entries with remaining TTL are available after restart — no redundant LLM API calls for recently cached results
6. Pending summarisation requests queued before a restart are drained after the server comes back up
7. Agent hook state (deferred stops, transcript positions, prompt dedup hashes) survives restarts
8. If Redis is unavailable at startup, all services start normally using in-memory fallback and log a warning
9. If Redis becomes unavailable during operation, services continue operating with in-memory state and log warnings — no crashes or request failures

### 3.2 Non-Functional Success Criteria

1. Redis operations on hot paths (SSE broadcast, rate limit checks, cache lookups) complete in under 1ms (local Redis, single-instance)
2. Redis connection overhead does not measurably increase server startup time (target: <100ms additional)
3. Redis memory usage stays under 50MB for typical operation (10 active agents, 5 active channels, 500-event replay buffer)
4. No new single points of failure: Redis unavailability degrades performance (cache misses, lost rate limits) but does not break functionality

---

## 4. Functional Requirements (FRs)

**FR1: Redis connection management**

The system must establish and manage a Redis connection pool on application startup. Connection parameters (host, port, password, database number, connection pool size) must be configurable via `config.yaml`. The connection must support authentication (Redis on the host requires a password).

**FR2: Graceful degradation on Redis unavailability**

Every service that uses Redis must implement a fallback to in-memory operation. If a Redis operation fails (connection error, timeout, command error), the service must:
- Log a warning with the service name and operation that failed
- Fall back to the equivalent in-memory operation
- Continue processing the request without raising an exception
- Periodically attempt to reconnect (not on every request — use a backoff strategy)

**FR3: SSE replay buffer migration**

The Broadcaster's 500-event replay buffer must be backed by a Redis Stream. Requirements:
- New SSE events are appended to the stream with their event ID
- Stream is capped at the configured replay buffer size (default 500 entries)
- Reconnecting clients provide Last-Event-ID and receive all events after that ID from the stream
- The in-memory event ID counter must use Redis INCR for atomicity and persistence

**FR4: SSE per-client queue handling**

Per-client SSE event queues remain in-memory (they are inherently tied to an active TCP connection). On client reconnection after restart, the client replays from the Redis Stream (FR3) rather than recovering its old queue. The gap detection mechanism (`has_gap` flag) must integrate with Redis Stream replay.

**FR5: Notification rate limit migration**

Per-agent and per-channel notification rate limit timestamps must be stored in Redis keys with TTL. Requirements:
- Each rate limit entry is a Redis key with TTL matching the rate limit window (5 seconds for agent, 30 seconds for channel)
- Rate limit checks use Redis GET; rate limit sets use Redis SET with EX (expiry)
- On Redis unavailability, rate limiting falls back to in-memory (accepts the risk of duplicate notifications during Redis outage)

**FR6: Pending summarisation queue migration**

The `_pending_summarisations` list in CommandLifecycleManager must be backed by a Redis list. Requirements:
- Summarisation requests are serialised (JSON) and pushed to a Redis list
- After DB commit, the service pops and executes requests from the Redis list
- On startup, the service checks for and drains any pending requests left from a previous process
- Requests that fail execution are not re-queued (matches current best-effort semantics)

**FR7: Hook agent state migration**

The 10 per-agent state dicts in HookAgentState must be backed by Redis hashes with per-key TTL. Requirements:
- Each state category (awaiting_tool, respond_pending, etc.) uses a Redis hash keyed by agent ID
- TTL-based entries (respond_pending: 10s, recent_prompt_hashes: 1 hour) use Redis key expiry
- Set-based entries (deferred_stop_pending, skill_injection_pending) use Redis sets
- Thread-safety is handled by Redis atomicity (replaces Python threading.Lock)

**FR8: Session registry migration**

The session registry's `_sessions` dict must be backed by a Redis hash. Requirements:
- Each registered session is stored as a JSON-serialised hash entry keyed by session UUID
- Entries have a TTL matching the agent reaper timeout (default 5 minutes), refreshed on activity
- On startup, the session registry is pre-populated from Redis (surviving sessions from previous process)

**FR9: Inference cache migration**

The inference cache's `_cache` dict must be backed by Redis keys with TTL. Requirements:
- Cache entries are stored as Redis keys with the content hash as key and JSON-serialised result as value
- TTL matches the configured cache TTL (default 300 seconds)
- LRU eviction is replaced by Redis TTL expiry (Redis handles memory management)
- Max cache size enforcement uses Redis MAXMEMORY policy or application-level key count checks

**FR10: EventWriter metrics migration**

EventWriter metrics (total/successful/failed write counts, last write timestamp, last error) must be stored in a Redis hash. Requirements:
- Counters use Redis HINCRBY for atomic increments
- Timestamps and error messages use Redis HSET
- Metrics are readable for the health/status endpoint

**FR11: Priority scoring debounce migration**

The priority scoring debounce timer state must be stored as a Redis key with TTL. Requirements:
- When a scoring request is debounced, a Redis key is set with TTL matching the debounce window (default 5 seconds)
- On startup, if the key exists, a scoring run is triggered immediately (deferred scoring from previous process)

**FR12: Key namespace isolation**

All Redis keys must be namespaced under a configurable prefix (default: `headspace:`) to avoid conflicts with other applications sharing the same Redis instance. The namespace must be configurable in `config.yaml`.

**FR13: Startup state recovery**

On application startup, services must recover state from Redis before accepting requests. The recovery process must:
- Be ordered: connection pool first, then individual service recovery
- Log what was recovered (number of sessions, cache entries, pending summarisations, etc.)
- Complete before the Flask app starts serving HTTP requests
- Handle corrupt or incompatible Redis data gracefully (clear and start fresh, log warning)

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Connection pooling**

Redis connections must use a connection pool to avoid per-request connection overhead. Pool size must be configurable (default: 10 connections). Connections must be health-checked before use (ping on checkout or equivalent).

**NFR2: Serialisation format**

Data stored in Redis must use JSON serialisation for debuggability. Binary formats (pickle, msgpack) are not acceptable due to version coupling and security risks. Datetime values must be serialised as ISO 8601 strings.

**NFR3: Key expiry hygiene**

All Redis keys must have an explicit TTL or be stored in capped structures (streams with MAXLEN). No keys may be written without expiry unless they are explicitly long-lived (event ID counter). This prevents Redis memory growth from orphaned keys.

**NFR4: Monitoring and observability**

The health endpoint must report Redis connection status (connected/disconnected), memory usage, and key count. Services operating in fallback (in-memory) mode must be identifiable from the health endpoint response.

**NFR5: Testing**

Tests must not depend on a running Redis instance. A mock or fake Redis implementation must be used for unit tests. Integration tests that exercise Redis directly must use a dedicated test Redis database (different DB number from development/production).

---

## 6. Migration Strategy

The migration must be phased to manage risk. Services should be migrated incrementally, with each migration independently deployable and testable.

**Tier 1 — Highest impact, simplest migration:**
- Inference cache (FR9) — direct key-value mapping, TTL-native
- Notification rate limits (FR5) — direct key-value with TTL
- Event ID counter (FR3, partial) — single INCR key

**Tier 2 — Medium complexity:**
- SSE replay buffer (FR3) — Redis Streams
- Hook agent state (FR7) — multiple hash types
- Session registry (FR8) — hash with TTL refresh

**Tier 3 — Highest complexity or lowest priority:**
- Pending summarisations (FR6) — queue semantics, startup drain
- EventWriter metrics (FR10) — atomic counters
- Priority scoring debounce (FR11) — timer state
- Session tokens (FR8) — by-design ephemeral, optional migration

---

## Changelog

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-03-07 | Shorty | Initial draft from workshop #workshop-mark-shorty-21 |
