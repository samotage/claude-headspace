## Why

Claude Headspace maintains 10 separate in-memory ephemeral state systems (broadcaster replay buffer, notification rate limits, inference cache, hook agent state, session registry, etc.) that are all wiped on every server restart. This causes SSE clients to lose event history, duplicate notifications to fire, inference cache misses to trigger redundant LLM API calls, and agent hook state to lose conversation context. Redis provides a durable backing store that survives restarts while preserving the existing service APIs.

This is Phase 2 of restart resilience. Phase 1 (Channel Delivery Restart Resilience — DB reconstruction) should ship first.

## What Changes

- **New dependency:** `redis` Python package added to `pyproject.toml`
- **New service:** `RedisManager` — connection pool management, health checks, graceful degradation
- **New config section:** `redis` in `config.yaml` (host, port, password, db, pool_size, key_prefix)
- **Modified:** `Broadcaster` — replay buffer backed by Redis Stream (XADD/XRANGE), event ID via Redis INCR
- **Modified:** `NotificationService` — rate limit timestamps backed by Redis keys with TTL (SET EX/GET)
- **Modified:** `InferenceCache` — cache entries backed by Redis keys with TTL, replacing in-memory LRU dict
- **Modified:** `AgentHookState` — 10 per-agent state dicts backed by Redis hashes/sets with TTL
- **Modified:** `SessionRegistry` — session dict backed by Redis hash with per-entry TTL refresh
- **Modified:** `EventWriter` — metrics (counters, timestamps) backed by Redis hash (HINCRBY/HSET)
- **Modified:** `CommandLifecycleManager` — pending summarisation list backed by Redis list (LPUSH/RPOP)
- **Modified:** `PriorityScoringService` — debounce state backed by Redis key with TTL
- **Modified:** `SessionTokenService` — token store backed by Redis hash (optional, lowest priority)
- **Modified:** Health endpoint — reports Redis connection status, memory usage, fallback mode per service
- **Modified:** `app.py` — RedisManager initialisation in app factory, startup state recovery orchestration
- All services implement graceful fallback to in-memory if Redis is unavailable

## Impact

- Affected specs: broadcaster, notification-service, inference-cache, hook-agent-state, session-registry, event-writer, command-lifecycle, priority-scoring, session-token, health
- Affected code:
  - `src/claude_headspace/services/redis_manager.py` (new)
  - `src/claude_headspace/services/broadcaster.py`
  - `src/claude_headspace/services/notification_service.py`
  - `src/claude_headspace/services/inference_cache.py`
  - `src/claude_headspace/services/hook_agent_state.py`
  - `src/claude_headspace/services/session_registry.py`
  - `src/claude_headspace/services/event_writer.py`
  - `src/claude_headspace/services/command_lifecycle.py`
  - `src/claude_headspace/services/priority_scoring.py`
  - `src/claude_headspace/services/session_token.py`
  - `src/claude_headspace/routes/health.py`
  - `src/claude_headspace/app.py`
  - `src/claude_headspace/config.py`
  - `config.yaml`
  - `pyproject.toml`
