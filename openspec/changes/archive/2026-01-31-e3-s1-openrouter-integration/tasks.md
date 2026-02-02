## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Configuration

- [x] 2.1 Add `openrouter` section to config.yaml defaults and env mappings in config.py
- [x] 2.2 Add openrouter section to config.yaml with model mapping, rate limits, cache, retry settings

### 2.2 Data Model

- [x] 2.3 Create InferenceCall model in `src/claude_headspace/models/inference_call.py`
- [x] 2.4 Update `src/claude_headspace/models/__init__.py` to export InferenceCall and InferenceLevel
- [x] 2.5 Create Alembic migration for inference_calls table with indexes

### 2.3 Core Services

- [x] 2.6 Create OpenRouter API client (`src/claude_headspace/services/openrouter_client.py`)
- [x] 2.7 Create inference cache service (`src/claude_headspace/services/inference_cache.py`)
- [x] 2.8 Create inference rate limiter (`src/claude_headspace/services/inference_rate_limiter.py`)
- [x] 2.9 Create inference service (`src/claude_headspace/services/inference_service.py`)

### 2.4 API Endpoints

- [x] 2.10 Create inference routes blueprint (`src/claude_headspace/routes/inference.py`)
- [x] 2.11 Register inference blueprint and init service in app.py

### 2.5 Integration Tests

- [x] 2.12 Create integration tests for InferenceCall model persistence
- [x] 2.13 Create unit tests for OpenRouter client
- [x] 2.14 Create unit tests for inference cache
- [x] 2.15 Create unit tests for inference rate limiter
- [x] 2.16 Create unit tests for inference service
- [x] 2.17 Create unit tests for inference routes

## 3. Testing (Phase 3)

- [ ] 3.1 Run `pytest tests/` and verify all tests pass
- [ ] 3.2 Verify InferenceCall model persists correctly via integration tests
- [ ] 3.3 Verify rate limiting behavior under simulated burst
- [ ] 3.4 Verify cache hit/miss behavior
- [ ] 3.5 Verify graceful degradation when OpenRouter unreachable

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Alembic migration applies cleanly
- [ ] 4.4 API endpoints return expected responses
