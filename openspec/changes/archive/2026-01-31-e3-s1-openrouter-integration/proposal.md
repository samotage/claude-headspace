## Why

Claude Headspace needs an LLM inference layer to power all Epic 3 intelligence features (summarisation, scoring, generation). This sprint builds the foundational OpenRouter API client, inference service, call logging, rate limiting, caching, and cost tracking that all subsequent E3 sprints depend on.

## What Changes

- Add OpenRouter API client with authentication and structured responses
- Add inference service with model selection by level (turn/command → Haiku, project/objective → Sonnet)
- Add InferenceCall database model and Alembic migration for call logging
- Add rate limiting (calls/min and tokens/min) with thread-safe enforcement
- Add caching by input content hash with configurable TTL
- Add cost tracking per call with per-model pricing rates
- Add error handling with retries and graceful degradation
- Add config.yaml `openrouter` section with all settings
- Add GET `/api/inference/status` endpoint for health and config
- Add GET `/api/inference/usage` endpoint for usage statistics and cost breakdown
- Add inference health check for OpenRouter connectivity

## Impact

- Affected specs: inference (new capability)
- Affected code:
  - `src/claude_headspace/services/openrouter_client.py` — new: API client
  - `src/claude_headspace/services/inference_service.py` — new: inference orchestration
  - `src/claude_headspace/services/inference_cache.py` — new: caching layer
  - `src/claude_headspace/services/inference_rate_limiter.py` — new: rate limiting
  - `src/claude_headspace/models/inference_call.py` — new: database model
  - `src/claude_headspace/routes/inference.py` — new: API endpoints blueprint
  - `src/claude_headspace/models/__init__.py` — updated: export InferenceCall
  - `src/claude_headspace/app.py` — updated: register inference blueprint, init service
  - `src/claude_headspace/config.py` — updated: add openrouter config defaults and env mappings
  - `config.yaml` — updated: add openrouter section
  - `migrations/versions/` — new: migration for inference_calls table
- No changes to existing models, routes, or services (additive only)
- No frontend changes
