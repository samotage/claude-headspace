# Tasks: api-call-logging

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Database Model & Migration

- [x] 2.1 Create `ApiCallLog` model in `src/claude_headspace/models/api_call_log.py`
  - Fields: id, timestamp, http_method, endpoint_path, query_string, request_content_type, request_headers (JSONB, safe subset), request_body (Text), response_status_code, response_content_type, response_body (Text), latency_ms, source_ip, auth_status (enum: authenticated/failed/unauthenticated/bypassed)
  - Foreign keys: project_id (nullable, SET NULL), agent_id (nullable, SET NULL)
  - Indexes: timestamp (desc), endpoint_path, http_method, response_status_code, auth_status, composite (endpoint_path + timestamp)
- [x] 2.2 Create Alembic migration for `api_call_logs` table
- [x] 2.3 Register model import in app factory

### Capture Middleware/Service

- [x] 2.4 Create `ApiCallLogger` service in `src/claude_headspace/services/api_call_logger.py`
  - Flask `after_request` handler or decorator approach
  - Target route prefixes: `/api/remote_agents/`, `/api/voice_bridge/`, `/embed/`
  - Capture: request method, path, query string, content type, body, selected headers (strip Authorization values)
  - Capture: response status, content type, body, latency (via `before_request` timestamp)
  - Resolve project_id and agent_id from request context when available
  - Fault-tolerant: wrap DB write in try/except, log failures, never break the API response
  - Payload truncation: if body > 1MB, truncate with indicator
  - Broadcast SSE `api_call_logged` event after successful persistence
- [x] 2.5 Register `ApiCallLogger` in `app.py` app factory (attach before/after request hooks)

### API Endpoints

- [x] 2.6 Add `api_log_page` route (`/logging/api`) to `logging.py` blueprint
  - Render `logging_api.html` template
- [x] 2.7 Add `GET /api/logging/api-calls` endpoint to `logging.py`
  - Query params: endpoint_path, http_method, status_category (2xx/4xx/5xx), auth_status, search, page, per_page
  - Text search across request_body and response_body using ILIKE
  - Return paginated results with total count and page metadata
  - Resolve project and agent names for display
- [x] 2.8 Add `GET /api/logging/api-calls/filters` endpoint to `logging.py`
  - Return distinct endpoint paths, HTTP methods, status categories, auth statuses from existing records
- [x] 2.9 Add `DELETE /api/logging/api-calls` endpoint to `logging.py`
  - Require `X-Confirm-Destructive: true` header
  - Delete all ApiCallLog records, return count

### UI Template & JavaScript

- [x] 2.10 Create `templates/logging_api.html` following `logging_inference.html` pattern
  - Filter bar: endpoint path dropdown, HTTP method dropdown, status category dropdown, auth status dropdown, text search input, clear filters button, clear all logs button with inline confirmation
  - Table columns: Timestamp, Method (badge), Endpoint, Status (colour-coded badge: 2xx green, 4xx amber, 5xx red), Latency (ms), Source IP, Auth Status
  - Expanded row: two sections — "Request" (headers + body with JSON syntax highlighting) and "Response" (status + body with JSON syntax highlighting)
  - States: loading, empty, no results, error
  - Pagination: Previous/Next with page indicator
- [x] 2.11 Create `static/js/logging-api.js` following `logging-inference.js` pattern
  - API client for `/api/logging/api-calls` and `/api/logging/api-calls/filters`
  - Filter change handlers with debounced text search
  - Pagination controls
  - SSE listener for `api_call_logged` events — prepend new rows on page 1 when matching filters
  - Row expansion toggle showing full request/response payloads
  - Clear all logs with confirmation flow
- [x] 2.12 Update `templates/partials/_logging_tabs.html` to add API tab
  - Add third tab after Inference with distinct icon (e.g., bidirectional arrow or plug)
  - Active state logic using `request.endpoint == 'logging.api_log_page'`

## 3. Testing (Phase 3)

- [x] 3.1 Create `tests/services/test_api_call_logger.py`
  - Test middleware captures requests to target prefixes
  - Test middleware ignores non-target routes (hooks, dashboard, internal APIs)
  - Test request/response payloads are persisted correctly
  - Test Authorization header values are stripped (auth_status preserved)
  - Test fault tolerance: logging failure does not break API response
  - Test payload truncation for bodies > 1MB
  - Test project_id and agent_id resolution from request context
  - Test SSE event broadcast after capture
- [x] 3.2 Create `tests/routes/test_logging_api.py`
  - Test `GET /logging/api` renders template
  - Test `GET /api/logging/api-calls` returns paginated results
  - Test filtering by endpoint_path, http_method, status_category, auth_status
  - Test text search across request/response bodies
  - Test combined filters
  - Test pagination parameters
  - Test `GET /api/logging/api-calls/filters` returns distinct values
  - Test `DELETE /api/logging/api-calls` requires destructive header
  - Test `DELETE /api/logging/api-calls` clears all records
  - Test empty state (no records)

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Migration runs cleanly on test database
- [ ] 4.4 Manual verification: make API calls to remote agents/voice bridge endpoints, confirm they appear in API log tab
- [ ] 4.5 Verify SSE real-time updates work
- [ ] 4.6 Verify expanded row shows formatted JSON payloads
