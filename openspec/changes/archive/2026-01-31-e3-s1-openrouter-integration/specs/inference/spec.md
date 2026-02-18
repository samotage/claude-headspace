## ADDED Requirements

### Requirement: OpenRouter API Client

The system SHALL provide an API client that authenticates with OpenRouter and sends chat completion requests.

#### Scenario: Successful inference call

- **WHEN** an inference request is made with valid API key and input text
- **THEN** the client SHALL return generated text, input token count, output token count, model used, and latency

#### Scenario: API key not configured

- **WHEN** the OPENROUTER_API_KEY environment variable is not set and no config fallback exists
- **THEN** the service SHALL start in degraded mode and all inference calls SHALL return an error

---

### Requirement: Inference Service with Model Selection

The inference service SHALL select the appropriate model based on inference level using a configurable level-to-model mapping.

#### Scenario: Turn-level inference

- **WHEN** an inference call is made at level "turn" or "command"
- **THEN** the service SHALL use the lightweight model (e.g., Haiku)

#### Scenario: Project-level inference

- **WHEN** an inference call is made at level "project" or "objective"
- **THEN** the service SHALL use the more capable model (e.g., Sonnet)

---

### Requirement: Inference Call Logging

Every inference call SHALL be recorded in the InferenceCall database table with full metadata.

#### Scenario: Successful call logged

- **WHEN** an inference call completes successfully
- **THEN** a record SHALL be created with timestamp, level, purpose, model, input tokens, output tokens, input content hash, result text, and latency

#### Scenario: Failed call logged

- **WHEN** an inference call fails after retry exhaustion
- **THEN** a record SHALL be created with the error message and null result text

---

### Requirement: Rate Limiting

The system SHALL enforce rate limits on inference calls with configurable thresholds.

#### Scenario: Rate limit exceeded

- **WHEN** calls per minute or tokens per minute exceeds the configured limit
- **THEN** the request SHALL be rejected with feedback indicating when retry is possible

#### Scenario: Within rate limits

- **WHEN** the request is within configured limits
- **THEN** the request SHALL proceed normally

---

### Requirement: Caching

The system SHALL cache inference results by input content identity with configurable TTL.

#### Scenario: Cache hit

- **WHEN** an inference request matches a cached entry that has not expired
- **THEN** the cached result SHALL be returned without making an API call
- **AND** the response metadata SHALL indicate it was a cache hit

#### Scenario: Cache miss

- **WHEN** no matching cache entry exists or the entry has expired
- **THEN** a fresh API call SHALL be made and the result cached

---

### Requirement: Error Handling with Retries

The system SHALL retry retryable API failures with configurable increasing delays.

#### Scenario: Retryable error with recovery

- **WHEN** a retryable error occurs (timeout, 429, 500-series) and retry succeeds
- **THEN** the successful result SHALL be returned normally

#### Scenario: Retry exhaustion

- **WHEN** all retry attempts are exhausted
- **THEN** an error result SHALL be returned without crashing
- **AND** the failed call SHALL be logged with the error message

#### Scenario: Non-retryable error

- **WHEN** a non-retryable error occurs (401, 400)
- **THEN** the error SHALL be returned immediately without retries

---

### Requirement: API Endpoints

The system SHALL expose inference status and usage endpoints.

#### Scenario: Status endpoint

- **WHEN** GET `/api/inference/status` is requested
- **THEN** the response SHALL include service state, OpenRouter connectivity, models per level, and rate limit configuration

#### Scenario: Usage endpoint

- **WHEN** GET `/api/inference/usage` is requested
- **THEN** the response SHALL include total calls, calls by level, calls by model, total tokens, and cost breakdown

---

### Requirement: Configuration

The system SHALL load inference configuration from config.yaml with environment variable overrides.

#### Scenario: Configuration loaded from config.yaml

- **WHEN** the application starts
- **THEN** the openrouter section SHALL be loaded with base URL, model mapping, rate limits, cache settings, and retry settings

#### Scenario: API key from environment

- **WHEN** OPENROUTER_API_KEY environment variable is set
- **THEN** it SHALL be used for authentication
- **AND** it SHALL take precedence over any config.yaml value

---

### Requirement: InferenceCall Data Model

The InferenceCall model SHALL be created via Alembic migration with appropriate indexes.

#### Scenario: Model created with migration

- **WHEN** `flask db upgrade` is run
- **THEN** the inference_calls table SHALL be created with all required columns and indexes on timestamp, level, project_id, and input_hash
