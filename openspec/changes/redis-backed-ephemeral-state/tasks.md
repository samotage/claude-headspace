## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Foundation (Phase 2)

- [ ] 2.1 Add `redis` package dependency to `pyproject.toml`
- [ ] 2.2 Add `redis` configuration section to `config.py` defaults and `config.yaml`
- [ ] 2.3 Create `RedisManager` service (`src/claude_headspace/services/redis_manager.py`)
  - Connection pool management with configurable host/port/password/db/pool_size
  - Health check (ping on init)
  - Key namespace prefix (`headspace:` default)
  - Graceful degradation: `is_available` property, exponential backoff reconnect
  - Helper methods: `get`, `set`, `delete`, `incr`, `hset`, `hget`, `hgetall`, `hincrby`, `lpush`, `rpop`, `llen`, `sadd`, `srem`, `sismember`, `smembers`, `xadd`, `xrange`, `xlen`, `xtrim`
- [ ] 2.4 Register `RedisManager` in `app.py` app factory (`app.extensions["redis_manager"]`)
- [ ] 2.5 Add Redis status to health endpoint (`routes/health.py`)
- [ ] 2.6 Write unit tests for `RedisManager` using `fakeredis`

## 3. Tier 1 Migrations — Highest Impact, Simplest (Phase 3)

- [ ] 3.1 Migrate `InferenceCache` to Redis-backed storage
  - Redis keys: `{prefix}cache:{input_hash}` with TTL
  - JSON-serialised CacheEntry values
  - Fallback to in-memory dict on Redis failure
  - Update hit/miss counters
- [ ] 3.2 Write tests for Redis-backed InferenceCache (fakeredis + fallback scenarios)
- [ ] 3.3 Migrate `NotificationService` rate limits to Redis
  - Agent rate limits: `{prefix}ratelimit:agent:{agent_id}` with 5s TTL
  - Channel rate limits: `{prefix}ratelimit:channel:{channel_key}` with 30s TTL
  - SET EX for write, GET for check
  - Fallback to in-memory dict on Redis failure
- [ ] 3.4 Write tests for Redis-backed notification rate limits
- [ ] 3.5 Migrate Broadcaster event ID counter to Redis INCR
  - Key: `{prefix}sse:event_id`
  - No TTL (long-lived counter)
  - Fallback to in-memory counter on Redis failure
- [ ] 3.6 Write tests for Redis-backed event ID counter

## 4. Tier 2 Migrations — Medium Complexity (Phase 4)

- [ ] 4.1 Migrate Broadcaster replay buffer to Redis Stream
  - Stream key: `{prefix}sse:replay`
  - XADD with MAXLEN cap (default 500)
  - XRANGE for replay on client reconnection (Last-Event-ID)
  - Fallback to in-memory deque on Redis failure
  - Integrate gap detection (`has_gap`) with Redis Stream replay
- [ ] 4.2 Write tests for Redis Stream replay buffer
- [ ] 4.3 Migrate `AgentHookState` to Redis hashes/sets
  - Hash keys: `{prefix}hookstate:{category}:{agent_id}` with TTL per category
  - Set keys: `{prefix}hookstate:set:{category}:{agent_id}`
  - Per-category TTLs: respond_pending (10s), respond_inflight (10s), recent_prompt_hashes (1hr), command_creation_times (1hr)
  - Other categories: default 24hr TTL (transcript_positions, progress_texts, file_metadata, awaiting_tool)
  - Fallback to in-memory dicts on Redis failure
  - Remove threading.Lock (Redis provides atomicity)
- [ ] 4.4 Write tests for Redis-backed AgentHookState
- [ ] 4.5 Migrate `SessionRegistry` to Redis hash
  - Hash key: `{prefix}sessions`
  - Per-session TTL via separate keys: `{prefix}session:{uuid}` with 5min TTL, refreshed on activity
  - JSON-serialised RegisteredSession values
  - Startup recovery: load existing sessions from Redis
  - Fallback to in-memory dict on Redis failure
- [ ] 4.6 Write tests for Redis-backed SessionRegistry

## 5. Tier 3 Migrations — Highest Complexity or Lowest Priority (Phase 5)

- [ ] 5.1 Migrate `CommandLifecycleManager` pending summarisations to Redis list
  - List key: `{prefix}pending_summarisations`
  - JSON-serialised SummarisationRequest entries
  - LPUSH to enqueue, RPOP to dequeue
  - Startup drain: process any leftover entries from previous process
  - Fallback to in-memory list on Redis failure
- [ ] 5.2 Write tests for Redis-backed pending summarisations
- [ ] 5.3 Migrate `EventWriter` metrics to Redis hash
  - Hash key: `{prefix}event_writer:metrics`
  - HINCRBY for counters (total_writes, successful_writes, failed_writes)
  - HSET for timestamps and error messages
  - Fallback to in-memory dataclass on Redis failure
- [ ] 5.4 Write tests for Redis-backed EventWriter metrics
- [ ] 5.5 Migrate `PriorityScoringService` debounce to Redis key
  - Key: `{prefix}priority:debounce` with TTL matching debounce_seconds (5s)
  - Startup: check key existence, trigger immediate scoring if present
  - Fallback to in-memory timer on Redis failure
- [ ] 5.6 Write tests for Redis-backed priority debounce
- [ ] 5.7 Migrate `SessionTokenService` to Redis hash (optional)
  - Hash key: `{prefix}session_tokens`
  - Reverse index: `{prefix}agent_token:{agent_id}`
  - JSON-serialised TokenInfo values
  - Fallback to in-memory dict on Redis failure
- [ ] 5.8 Write tests for Redis-backed SessionTokenService

## 6. Startup Recovery & Integration (Phase 6)

- [ ] 6.1 Implement ordered startup recovery in `app.py`
  - RedisManager connects first
  - Each service recovers state from Redis in dependency order
  - Log recovery stats (session count, cache entries, pending summarisations)
  - Handle corrupt data gracefully (clear and start fresh)
- [ ] 6.2 Write integration tests for startup recovery flow
- [ ] 6.3 Verify graceful degradation: all services start and operate with Redis unavailable
- [ ] 6.4 Write degradation integration tests (fakeredis disabled mid-operation)

## 7. Final Verification (Phase 7)

- [ ] 7.1 All unit tests passing (fakeredis)
- [ ] 7.2 All integration tests passing
- [ ] 7.3 Manual verification: restart server, confirm state survives
- [ ] 7.4 Manual verification: stop Redis, confirm services degrade gracefully
- [ ] 7.5 Health endpoint reports Redis status and fallback mode per service
- [ ] 7.6 No linter errors
