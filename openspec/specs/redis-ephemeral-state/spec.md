# redis-ephemeral-state Specification

## Purpose
TBD - created by archiving change redis-backed-ephemeral-state. Update Purpose after archive.
## Requirements
### Requirement: Redis Connection Management (FR1)

The system SHALL establish and manage a Redis connection pool on application startup via a `RedisManager` service registered at `app.extensions["redis_manager"]`. Connection parameters (host, port, password, database number, pool size, key prefix) MUST be configurable via `config.yaml` under a `redis` section.

#### Scenario: Successful connection

- **WHEN** the application starts with valid Redis configuration
- **THEN** a connection pool is created with the configured pool size
- **AND** a health-check ping succeeds
- **AND** `RedisManager.is_available` returns `True`

#### Scenario: Redis unreachable at startup

- **WHEN** the application starts but Redis is unreachable
- **THEN** `RedisManager.is_available` returns `False`
- **AND** a warning is logged with the connection error details
- **AND** the application continues startup without Redis

#### Scenario: Key namespace isolation

- **WHEN** any Redis key is written by any service
- **THEN** the key MUST be prefixed with the configured namespace (default: `headspace:`)

---

### Requirement: Graceful Degradation (FR2)

Every service that uses Redis MUST implement a fallback to in-memory operation when Redis is unavailable.

#### Scenario: Redis operation failure during normal operation

- **WHEN** a Redis operation fails (connection error, timeout, command error)
- **THEN** the service logs a warning with the service name and operation that failed
- **AND** falls back to the equivalent in-memory operation
- **AND** continues processing the request without raising an exception

#### Scenario: Redis reconnection after outage

- **WHEN** Redis becomes available again after an outage
- **THEN** the service resumes using Redis on the next operation
- **AND** reconnection attempts use exponential backoff (not every request)

---

### Requirement: SSE Replay Buffer (FR3)

The Broadcaster's replay buffer MUST be backed by a Redis Stream.

#### Scenario: Event broadcast with Redis available

- **WHEN** an SSE event is broadcast
- **THEN** the event is appended to Redis Stream `{prefix}sse:replay` via XADD
- **AND** the stream is capped at the configured replay buffer size (default 500) via MAXLEN
- **AND** the event ID is generated via Redis INCR on key `{prefix}sse:event_id`

#### Scenario: Client reconnection with Last-Event-ID

- **WHEN** an SSE client reconnects with a Last-Event-ID header
- **THEN** all events after that ID are retrieved from the Redis Stream via XRANGE
- **AND** the events are delivered to the client before live event streaming begins

#### Scenario: Replay buffer fallback

- **WHEN** Redis is unavailable during broadcast
- **THEN** the event is stored in the in-memory deque (existing behaviour)
- **AND** the event ID is generated from an in-memory counter

---

### Requirement: Per-Client Queue Handling (FR4)

Per-client SSE event queues SHALL remain in-memory. On reconnection after restart, gap detection (`has_gap`) MUST integrate with Redis Stream replay.

#### Scenario: Client reconnects after server restart

- **WHEN** a client reconnects after a server restart
- **THEN** the client receives missed events from the Redis Stream
- **AND** `has_gap` is set based on whether replay covered the gap

---

### Requirement: Notification Rate Limits (FR5)

Notification rate limit timestamps MUST be stored in Redis keys with TTL.

#### Scenario: Agent rate limit check

- **WHEN** a notification is considered for an agent
- **THEN** the service checks Redis key `{prefix}ratelimit:agent:{agent_id}`
- **AND** if the key exists, the notification is suppressed (within rate limit window)
- **AND** if the key does not exist, the notification proceeds and a key is SET with 5-second TTL

#### Scenario: Channel rate limit check

- **WHEN** a notification is considered for a channel
- **THEN** the service checks Redis key `{prefix}ratelimit:channel:{channel_key}`
- **AND** if the key exists, the notification is suppressed
- **AND** if the key does not exist, the notification proceeds and a key is SET with 30-second TTL

---

### Requirement: Pending Summarisation Queue (FR6)

The pending summarisation list MUST be backed by a Redis list.

#### Scenario: Summarisation request enqueued

- **WHEN** a summarisation request is created
- **THEN** it is JSON-serialised and pushed to Redis list `{prefix}pending_summarisations` via LPUSH

#### Scenario: Startup drain

- **WHEN** the application starts and the Redis list contains entries from a previous process
- **THEN** all entries are popped (RPOP) and executed
- **AND** the count of drained entries is logged

#### Scenario: Failed execution

- **WHEN** a summarisation request fails during execution
- **THEN** it is NOT re-queued (best-effort semantics)

---

### Requirement: Hook Agent State (FR7)

The 10 per-agent state dicts in AgentHookState MUST be backed by Redis hashes and sets with per-key TTL.

#### Scenario: State write

- **WHEN** a per-agent state value is written (e.g., `set_awaiting_tool`)
- **THEN** it is stored in Redis hash `{prefix}hookstate:{category}:{agent_id}`
- **AND** the key has an appropriate TTL (respond_pending: 10s, recent_prompt_hashes: 1hr, etc.)

#### Scenario: Set-based state

- **WHEN** a set-based state value is written (e.g., `deferred_stop_pending`, `skill_injection_pending`)
- **THEN** it is stored in Redis set `{prefix}hookstate:set:{category}:{agent_id}`

#### Scenario: Session cleanup

- **WHEN** a session ends
- **THEN** all Redis keys for that agent's hook state are deleted atomically

---

### Requirement: Session Registry (FR8)

The session registry MUST be backed by a Redis hash with per-entry TTL refresh.

#### Scenario: Session registration

- **WHEN** a session is registered
- **THEN** the session data is JSON-serialised and stored in Redis
- **AND** a TTL key `{prefix}session:{uuid}` is set with the reaper timeout (default 5 minutes)

#### Scenario: Activity refresh

- **WHEN** activity is detected for a session
- **THEN** the TTL on the session key is refreshed

#### Scenario: Startup recovery

- **WHEN** the application starts
- **THEN** existing sessions are loaded from Redis into the registry
- **AND** the count of recovered sessions is logged

---

### Requirement: Inference Cache (FR9)

The inference cache MUST be backed by Redis keys with TTL.

#### Scenario: Cache write

- **WHEN** an inference result is cached
- **THEN** it is JSON-serialised and stored at Redis key `{prefix}cache:{input_hash}`
- **AND** the key TTL matches the configured cache TTL (default 300 seconds)

#### Scenario: Cache hit

- **WHEN** a cache lookup finds a matching Redis key
- **THEN** the JSON-deserialised result is returned
- **AND** the hit counter is incremented

#### Scenario: Cache miss

- **WHEN** a cache lookup finds no matching Redis key (or key has expired)
- **THEN** `None` is returned
- **AND** the miss counter is incremented

---

### Requirement: EventWriter Metrics (FR10)

EventWriter metrics MUST be stored in a Redis hash.

#### Scenario: Write success recorded

- **WHEN** a successful write is recorded
- **THEN** `total_writes` and `successful_writes` are incremented via HINCRBY on `{prefix}event_writer:metrics`
- **AND** `last_write_timestamp` is updated via HSET

#### Scenario: Write failure recorded

- **WHEN** a failed write is recorded
- **THEN** `total_writes` and `failed_writes` are incremented via HINCRBY
- **AND** `last_error` is updated via HSET

---

### Requirement: Priority Scoring Debounce (FR11)

The priority scoring debounce timer state MUST be stored as a Redis key with TTL.

#### Scenario: Scoring debounced

- **WHEN** a scoring request is debounced
- **THEN** a Redis key `{prefix}priority:debounce` is SET with TTL matching debounce_seconds (5s)

#### Scenario: Startup with pending debounce

- **WHEN** the application starts and `{prefix}priority:debounce` key exists
- **THEN** a scoring run is triggered immediately

---

### Requirement: Key Expiry Hygiene (FR12, NFR3)

All Redis keys MUST have an explicit TTL or be stored in capped structures, except explicitly long-lived keys (event ID counter).

#### Scenario: Key written without TTL

- **WHEN** any key is written to Redis (except `{prefix}sse:event_id`)
- **THEN** it MUST have a TTL set or be part of a capped stream (MAXLEN)

---

### Requirement: Startup State Recovery (FR13)

On application startup, services MUST recover state from Redis before accepting requests.

#### Scenario: Ordered recovery

- **WHEN** the application starts
- **THEN** RedisManager connects first
- **AND** each service recovers its state from Redis in dependency order
- **AND** recovery stats are logged (session count, cache entries, pending summarisations)

#### Scenario: Corrupt data handling

- **WHEN** Redis contains corrupt or incompatible data during recovery
- **THEN** the corrupt data is cleared
- **AND** the service starts fresh
- **AND** a warning is logged

---

### Requirement: Health Endpoint Integration (NFR4)

The health endpoint MUST report Redis status.

#### Scenario: Redis healthy

- **WHEN** `/health` is requested and Redis is connected
- **THEN** the response includes `redis: { status: "connected", memory_usage: "...", key_count: N }`

#### Scenario: Redis degraded

- **WHEN** `/health` is requested and Redis is unavailable
- **THEN** the response includes `redis: { status: "disconnected" }`
- **AND** lists services operating in fallback mode

---

### Requirement: Testing (NFR5)

Tests MUST NOT depend on a running Redis instance.

#### Scenario: Unit tests

- **WHEN** unit tests run
- **THEN** they use `fakeredis` as a mock Redis implementation
- **AND** no connection to a real Redis server is required

#### Scenario: Integration tests

- **WHEN** integration tests exercise Redis directly
- **THEN** they use a dedicated test Redis database (different DB number from dev/production)

