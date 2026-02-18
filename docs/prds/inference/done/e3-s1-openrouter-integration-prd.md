---
validation:
  status: valid
  validated_at: '2026-01-30T12:59:09+11:00'
---

## Product Requirements Document (PRD) — OpenRouter Integration & Inference Service

**Project:** Claude Headspace v3.1
**Scope:** Epic 3, Sprint 1 — LLM infrastructure foundation for all intelligence features
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace requires an LLM inference layer to power its intelligence features: turn summarisation, command summarisation, cross-project priority scoring, progress summary generation, and brain reboot. This PRD defines the foundational infrastructure — an OpenRouter API client, inference service with model selection by level, call logging, rate limiting, cost tracking, and caching — that all subsequent Epic 3 sprints depend on.

The inference service connects to OpenRouter's API to access multiple Anthropic models. It selects the appropriate model based on inference level: lightweight models (Haiku) for high-volume turn and task operations, and more capable models (Sonnet) for project-level and objective-level analysis. Every call is logged to the database with full metadata for auditability and cost visibility.

This is a backend infrastructure sprint with no frontend changes. Success is measured by the ability to make inference calls reliably, log them comprehensively, enforce rate limits, cache duplicate requests, and expose health and usage information via API endpoints.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. Epics 1 and 2 established the core event-driven architecture, state machine, dashboard UI, configuration, and notifications. Epic 3 adds an intelligence layer powered by LLM inference via OpenRouter.

All five Epic 3 sprints (turn/command summarisation, priority scoring, git analysis, brain reboot) depend on a shared inference infrastructure. This sprint establishes that foundation as a standalone, reusable service within the existing Flask application.

The system already has:
- Flask application with blueprints and service injection (`app.extensions`)
- PostgreSQL database with SQLAlchemy models and Alembic migrations
- Configuration via `config.yaml` with environment variable overrides
- Domain models for Project, Agent, Command, Turn, Event, and Objective
- `.env` with `OPENROUTER_API_KEY` already provisioned

### 1.2 Target User

This subsystem is infrastructure — not directly user-facing. Its consumers are:
- **Internal services** (E3-S2 through E3-S5) that make inference calls for summarisation, scoring, and generation
- **Operators/administrators** who monitor inference health and costs via the API endpoints

### 1.3 Success Moment

An internal service requests an inference call at a given level (e.g., "turn"). The inference service selects the correct model, calls OpenRouter, returns the result, logs the call with full metadata, and the operator can see the call in the usage endpoint with accurate cost information. If the same input is requested again, the cached result is returned instantly without an API call.

---

## 2. Scope

### 2.1 In Scope

- OpenRouter API client with authentication and request handling
- Inference service with model selection by inference level (turn, task, project, objective)
- InferenceCall database model for logging all LLM calls
- Database migration (Alembic) for the InferenceCall table
- Rate limiting with configurable calls per minute and tokens per minute
- Cost tracking based on token counts and configurable per-model pricing rates
- Caching by input content identity with configurable time-to-live
- Error handling for API failures (timeouts, rate limits, server errors) with configurable retry and increasing delays
- Health check for LLM connectivity
- Configuration schema additions to `config.yaml` for OpenRouter settings
- API key management via environment variable (`OPENROUTER_API_KEY`) with config fallback
- API endpoint: GET `/api/inference/status` — service health and configuration
- API endpoint: GET `/api/inference/usage` — usage statistics and cost breakdown

### 2.2 Out of Scope

- Turn summarisation service (E3-S2)
- Command summarisation service (E3-S2)
- Priority scoring service (E3-S3)
- Git analyzer and progress summary generation (E3-S4)
- Brain reboot generation (E3-S5)
- Prompt templates for any specific inference use case
- Dashboard UI changes (no frontend work)
- Cost budget caps or spending alerts
- Summary feedback mechanisms
- Async command queue infrastructure (background threads are sufficient for this sprint)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. The inference service connects to OpenRouter API and receives valid LLM responses
2. Model selection correctly routes inference calls by level: turn and task levels use a lightweight model; project and objective levels use a more capable model
3. All inference calls are logged to the InferenceCall table with: timestamp, level, purpose, model, input tokens, output tokens, input content hash, result text, latency, and optional associations to project/agent/command/turn
4. Rate limiting is enforced — requests exceeding the configured calls-per-minute or tokens-per-minute limits are queued or rejected gracefully with appropriate feedback
5. Identical inference inputs (same content hash) return cached results without making a duplicate API call; cached results expire after a configurable time-to-live
6. API failures are retried with configurable increasing delays before giving up; after retry exhaustion, the service degrades gracefully (returns error, does not crash)
7. GET `/api/inference/status` returns service health, OpenRouter connectivity status, and current configuration (models per level, rate limit settings)
8. GET `/api/inference/usage` returns usage statistics: total calls, calls by level, total tokens (input/output), and estimated cost breakdown by model
9. Configuration is loaded from the `config.yaml` openrouter section; the API key is resolved from the `OPENROUTER_API_KEY` environment variable with config fallback

### 3.2 Non-Functional Success Criteria

1. Inference calls do not block the Flask request/response cycle or SSE event stream
2. Rate limiter handles burst traffic without data loss (excess requests are deferred, not silently dropped)
3. InferenceCall logging does not fail silently — errors in logging are captured and reported
4. The service starts gracefully when OpenRouter is unreachable (degraded mode, not crash)
5. Cache lookup adds negligible latency to inference requests

---

## 4. Functional Requirements (FRs)

### API Client

**FR1:** The system shall provide an API client that authenticates with OpenRouter using a configured API key and sends chat completion requests.

**FR2:** The API client shall support configurable base URL, timeout, and request headers (including site URL and app name for OpenRouter identification).

**FR3:** The API client shall return structured responses including: generated text, input token count, output token count, model used, and latency.

### Inference Service

**FR4:** The inference service shall accept inference requests specifying: level (turn, task, project, objective), purpose (free-text description), input text, and optional associations (project ID, agent ID, command ID, turn ID).

**FR5:** The inference service shall select the appropriate model based on the inference level, using a configurable mapping of level-to-model in `config.yaml`.

**FR6:** The inference service shall return the LLM-generated result text to the caller along with metadata (model used, tokens consumed, latency).

### Logging

**FR7:** Every inference call (successful or failed) shall be recorded in the InferenceCall database table with: timestamp, level, purpose, model, input tokens, output tokens, input content hash, result text (or null on failure), latency in milliseconds, and error message (if failed).

**FR8:** Each InferenceCall record shall support optional foreign key associations to project, agent, task, and turn — allowing later sprints to link inference calls to specific domain entities.

### Rate Limiting

**FR9:** The system shall enforce rate limits on inference calls with two configurable thresholds: maximum calls per minute and maximum tokens per minute.

**FR10:** When a rate limit is reached, the system shall defer or reject the request and provide feedback to the caller indicating the limit was hit and when it can retry.

### Caching

**FR11:** Before making an API call, the system shall check for a cached result matching the same input content identity.

**FR12:** Cached results shall have a configurable time-to-live; expired cache entries shall be eligible for refresh on the next request.

**FR13:** Cache hits shall be distinguishable from fresh API calls in the response metadata.

### Cost Tracking

**FR14:** The system shall calculate estimated cost for each inference call based on input/output token counts and configurable per-model pricing rates.

**FR15:** The usage API endpoint shall provide aggregated cost breakdown by model and by inference level.

### Error Handling

**FR16:** On API failure (timeout, HTTP error, rate limit response from OpenRouter), the system shall retry with configurable increasing delays up to a maximum number of attempts.

**FR17:** After retry exhaustion, the system shall return an error result to the caller without crashing; the failed call shall still be logged with the error message.

**FR18:** The system shall distinguish between retryable errors (timeouts, 429, 500-series) and non-retryable errors (401 unauthorized, 400 bad request) and only retry retryable errors.

### Configuration

**FR19:** The `config.yaml` file shall include an `openrouter` section with: base URL, model mapping by level, rate limit settings, caching settings (enabled flag, TTL), and retry settings (max attempts, base delay, max delay).

**FR20:** The API key shall be resolved from the `OPENROUTER_API_KEY` environment variable; if not set, fall back to a value in `config.yaml`.

### API Endpoints

**FR21:** GET `/api/inference/status` shall return: service enabled/disabled state, OpenRouter connectivity (reachable or not), configured models per level, rate limit configuration, and cache configuration.

**FR22:** GET `/api/inference/usage` shall return: total inference calls, calls grouped by level, calls grouped by model, total input and output tokens, estimated total cost, and cost breakdown by model.

### Health Check

**FR23:** The inference service shall provide a health check that verifies OpenRouter API connectivity by making a lightweight validation request (e.g., a minimal completion or model list request).

### Data Model

**FR24:** The InferenceCall model shall be added to the database via an Alembic migration, with appropriate indexes on: timestamp, level, project_id, and input_hash (for cache lookup).

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Inference calls shall not block the main Flask request thread or SSE event delivery. Callers should be able to invoke inference asynchronously.

**NFR2:** The rate limiter shall be thread-safe and handle concurrent requests without race conditions.

**NFR3:** The caching mechanism shall add less than 5ms overhead per lookup.

**NFR4:** The service shall start and remain operational when OpenRouter is unreachable, operating in degraded mode (all calls return errors, health check reports unhealthy).

**NFR5:** The InferenceCall table shall support efficient querying for the usage endpoint without requiring full table scans (appropriate indexes required).

**NFR6:** Configuration changes to rate limits, models, or caching shall take effect on application restart (hot-reload not required).

---

## 6. UI Overview

Not applicable — this sprint has no user-facing UI changes. The API endpoints (`/api/inference/status` and `/api/inference/usage`) are JSON APIs for programmatic access and future dashboard integration.
