# Proposal Summary: e3-s1-openrouter-integration

## Architecture Decisions
- Use OpenRouter as the LLM gateway (provides access to multiple model providers via single API)
- Two-tier model selection: lightweight (Haiku) for turn/task-level, capable (Sonnet) for project/objective-level
- In-memory caching by content hash with configurable TTL (not Redis — keep it simple for single-process Flask)
- Thread-safe rate limiting using threading.Lock (calls/min and tokens/min)
- Exponential backoff retries for transient errors (429, 5xx, timeouts)
- InferenceCall model logs every call for cost tracking and audit
- Graceful degradation: service starts in degraded mode if OPENROUTER_API_KEY is missing

## Implementation Approach
- Follow existing patterns: model in models/, service in services/, routes as blueprint in routes/
- Config follows established pattern: DEFAULTS dict in config.py + section in config.yaml + ENV_MAPPINGS
- OpenRouter client is a thin HTTP wrapper (requests library) returning structured dataclasses/dicts
- Inference service orchestrates: check rate limits → check cache → call client → log result → cache result
- All new code is additive — no modifications to existing models, services, or routes

## Files to Modify

### New Files
- `src/claude_headspace/models/inference_call.py` — InferenceCall SQLAlchemy model + InferenceLevel enum
- `src/claude_headspace/services/openrouter_client.py` — HTTP client for OpenRouter API
- `src/claude_headspace/services/inference_cache.py` — In-memory cache with TTL and content hash keys
- `src/claude_headspace/services/inference_rate_limiter.py` — Thread-safe rate limiter (calls/min, tokens/min)
- `src/claude_headspace/services/inference_service.py` — Orchestration: model selection, caching, rate limiting, logging
- `src/claude_headspace/routes/inference.py` — Blueprint with /api/inference/status and /api/inference/usage
- `migrations/versions/xxx_add_inference_calls.py` — Alembic migration

### Modified Files
- `src/claude_headspace/models/__init__.py` — Export InferenceCall and InferenceLevel
- `src/claude_headspace/app.py` — Register inference blueprint, init inference service
- `src/claude_headspace/config.py` — Add openrouter DEFAULTS and ENV_MAPPINGS
- `config.yaml` — Add openrouter section

### Test Files
- `tests/integration/test_inference_call.py` — Integration tests for InferenceCall model persistence
- `tests/services/test_openrouter_client.py` — Unit tests for OpenRouter client
- `tests/services/test_inference_cache.py` — Unit tests for cache
- `tests/services/test_inference_rate_limiter.py` — Unit tests for rate limiter
- `tests/services/test_inference_service.py` — Unit tests for inference service
- `tests/routes/test_inference.py` — Unit tests for inference routes

## Acceptance Criteria
- OpenRouter client authenticates and returns structured responses (text, tokens, model, latency)
- Model selection maps turn/task→Haiku, project/objective→Sonnet via configurable mapping
- Every inference call is logged to inference_calls table with full metadata
- Rate limits reject requests when exceeded, with retry-after feedback
- Cache returns cached results for matching content hash within TTL
- Retryable errors (429, 5xx, timeout) are retried with exponential backoff
- Non-retryable errors (401, 400) fail immediately
- Service degrades gracefully when API key is missing
- GET /api/inference/status returns service state, connectivity, models, rate limits
- GET /api/inference/usage returns call counts, token counts, cost breakdown
- Alembic migration creates inference_calls table with indexes

## Constraints and Gotchas
- OPENROUTER_API_KEY must be set as environment variable (not stored in config.yaml)
- Rate limiter must be thread-safe (Flask may run with threads)
- Cache is in-memory only — will be cleared on server restart (acceptable for v1)
- Cost tracking uses per-model pricing rates from config — must be kept up to date manually
- InferenceCall model has project_id FK but it's nullable (inference can happen without project context)
- The input_hash column is used for both caching and deduplication — use SHA-256 of input content

## Git Change History

### Related Files
- Models: `project.py`, `agent.py`, `task.py`, `turn.py`, `event.py`, `objective.py`
- Config: `config.py`, `config.yaml`
- App: `app.py`
- Database: `database.py`
- Migrations: `migrations/versions/`

### OpenSpec History
- First change to inference capability (new subsystem)
- Previous sprint (integration-testing-framework) established integration test patterns with Factory Boy

### Implementation Patterns
- Models: SQLAlchemy declarative with `db.Model`, UUID primary keys, `created_at` timestamps
- Config: DEFAULTS dict → config.yaml merge → ENV_MAPPINGS override
- Routes: Flask blueprints registered in `create_app()`
- Services: Injected into `app.extensions` dict in `create_app()`
- Tests: pytest with fixtures in conftest.py, integration tests use real PostgreSQL

## Q&A History
- No clarifications needed — PRD was sufficiently detailed
- No conflicts detected with existing codebase

## Dependencies
- `requests` — HTTP client for OpenRouter API (already in requirements or add if missing)
- No new database dependencies (uses existing Flask-SQLAlchemy + Alembic)
- No external service dependencies beyond OpenRouter API

## Testing Strategy
- Integration tests: InferenceCall model persistence, factory creation, constraint validation
- Unit tests for OpenRouter client: mock HTTP responses, test auth, error handling, retries
- Unit tests for cache: hit/miss/expiry/hash computation
- Unit tests for rate limiter: within limits/exceeded/window reset/thread safety
- Unit tests for inference service: model selection, caching integration, rate limit enforcement, logging
- Unit tests for routes: status endpoint response, usage endpoint response, error cases
- Full suite regression: run all existing tests to confirm no breakage

## OpenSpec References
- proposal.md: openspec/changes/e3-s1-openrouter-integration/proposal.md
- tasks.md: openspec/changes/e3-s1-openrouter-integration/tasks.md
- spec.md: openspec/changes/e3-s1-openrouter-integration/specs/inference/spec.md
