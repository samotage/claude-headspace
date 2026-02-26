# Delta Spec: api-call-logging

## ADDED Requirements

### Requirement: ApiCallLog Database Model

The system SHALL persist external API call records in an `api_call_logs` table.

#### Scenario: Model schema

- **WHEN** an API call log record is created
- **THEN** it contains: id, timestamp, http_method, endpoint_path, query_string, request_content_type, request_headers (JSONB), request_body (Text), response_status_code, response_content_type, response_body (Text), latency_ms (Integer), source_ip (String), auth_status (String enum)
- **AND** optional foreign keys: project_id, agent_id (both nullable, SET NULL on delete)
- **AND** indexes exist on: timestamp, endpoint_path, http_method, response_status_code, auth_status

#### Scenario: Auth status values

- **WHEN** auth_status is recorded
- **THEN** it is one of: `authenticated`, `failed`, `unauthenticated`, `bypassed`

### Requirement: API Call Capture Middleware

The system SHALL capture every HTTP request to designated external API route prefixes.

#### Scenario: Target routes captured

- **WHEN** a request is made to `/api/remote_agents/*`, `/api/voice_bridge/*`, or `/embed/*`
- **THEN** the request and response are captured and persisted as an ApiCallLog record

#### Scenario: Non-target routes ignored

- **WHEN** a request is made to `/hook/*`, `/api/events/*`, `/api/inference/*`, `/`, `/dashboard`, `/logging`, or any other non-target route
- **THEN** no ApiCallLog record is created

#### Scenario: Captured data completeness

- **WHEN** a request is captured
- **THEN** the record includes: HTTP method, endpoint path, query string, request content type, request body, response status code, response content type, response body, response latency in milliseconds, source IP address, and authentication status

#### Scenario: Sensitive header stripping

- **WHEN** request headers are captured
- **THEN** Authorization header values are replaced with the auth status determination
- **AND** the raw token value is never stored

#### Scenario: Fault tolerance

- **WHEN** the logging mechanism encounters a database error or serialisation error
- **THEN** the API request still completes normally with the correct response
- **AND** the logging failure is recorded in the application log

#### Scenario: Performance overhead

- **WHEN** API call logging is active
- **THEN** it adds no more than 50ms of overhead to request processing under normal conditions

#### Scenario: Large payload handling

- **WHEN** a request or response body exceeds 1MB
- **THEN** the body is truncated with a clear indicator that truncation occurred
- **AND** bodies up to 1MB are captured without truncation

#### Scenario: Entity resolution

- **WHEN** project_id or agent_id can be resolved from the request context
- **THEN** they are stored on the ApiCallLog record
- **AND** when they cannot be resolved, the fields are NULL

### Requirement: API Log Tab Page

The system SHALL provide an "API" tab in the logging subsystem navigation.

#### Scenario: Tab navigation

- **WHEN** the logging subsystem is displayed
- **THEN** three tabs are shown: Events, Inference, API
- **AND** the API tab is positioned after the Inference tab
- **AND** the API tab uses a distinct icon

#### Scenario: Tab route

- **WHEN** a user navigates to `/logging/api`
- **THEN** the API log tab is displayed with filter bar, table, and pagination controls

### Requirement: API Log Table Display

The system SHALL display captured API calls in a paginated table.

#### Scenario: Table columns

- **WHEN** the API log table renders
- **THEN** columns are displayed: Timestamp, Method (badge), Endpoint, Status (colour-coded badge), Latency (ms), Source IP, Auth Status

#### Scenario: Status code colour coding

- **WHEN** a status code badge renders
- **THEN** 2xx status codes display with green styling
- **AND** 4xx status codes display with amber styling
- **AND** 5xx status codes display with red styling

#### Scenario: Ordering

- **WHEN** the table renders
- **THEN** records are ordered by timestamp descending (most recent first)

### Requirement: API Log Filter Controls

The system SHALL provide filter controls for narrowing API call display.

#### Scenario: Endpoint path filter

- **WHEN** the endpoint path filter is shown
- **THEN** it lists all distinct endpoint paths from existing records plus an "All Endpoints" option

#### Scenario: HTTP method filter

- **WHEN** the HTTP method filter is shown
- **THEN** it lists: GET, POST, PUT, DELETE, OPTIONS plus an "All Methods" option

#### Scenario: Status category filter

- **WHEN** the status category filter is shown
- **THEN** it lists: 2xx, 4xx, 5xx plus an "All" option

#### Scenario: Auth status filter

- **WHEN** the auth status filter is shown
- **THEN** it lists: authenticated, failed, unauthenticated, bypassed plus an "All" option

#### Scenario: Text search

- **WHEN** a user enters text in the search field
- **THEN** results are filtered to records where request_body or response_body contains the search text (case-insensitive)

#### Scenario: Combined filters

- **WHEN** multiple filters are selected
- **THEN** only records matching ALL active filters are displayed

#### Scenario: Clear filters

- **WHEN** the user clicks Clear Filters
- **THEN** all filters reset to default state
- **AND** the full unfiltered list is displayed

### Requirement: API Log Row Expansion

The system SHALL provide expandable rows for API call details.

#### Scenario: Expand row

- **WHEN** a user clicks a table row
- **THEN** it expands to show full request payload and full response payload
- **AND** request headers (safe subset) are displayed
- **AND** JSON content is syntax-highlighted

#### Scenario: Collapse row

- **WHEN** a user clicks an expanded row
- **THEN** it collapses back to summary view

#### Scenario: Request section

- **WHEN** the expanded row renders the request section
- **THEN** it shows request headers and request body
- **AND** JSON bodies are formatted with indentation

#### Scenario: Response section

- **WHEN** the expanded row renders the response section
- **THEN** it shows response status code and response body
- **AND** JSON bodies are formatted with indentation

### Requirement: GET /api/logging/api-calls Endpoint

The system SHALL provide a paginated endpoint to retrieve API call log records.

#### Scenario: Get calls with no filters

- **WHEN** `GET /api/logging/api-calls` is called
- **THEN** a paginated list of API call records is returned
- **AND** response includes: total, page, pages, has_next, has_previous

#### Scenario: Get calls with endpoint filter

- **WHEN** `GET /api/logging/api-calls?endpoint_path=/api/remote_agents/create` is called
- **THEN** only records for that endpoint are returned

#### Scenario: Get calls with status category filter

- **WHEN** `GET /api/logging/api-calls?status_category=4xx` is called
- **THEN** only records with 400-499 status codes are returned

#### Scenario: Get calls with text search

- **WHEN** `GET /api/logging/api-calls?search=error` is called
- **THEN** only records where request_body or response_body contains "error" are returned

#### Scenario: Pagination parameters

- **WHEN** `GET /api/logging/api-calls?page=2&per_page=25` is called
- **THEN** page 2 with 25 records per page is returned

### Requirement: GET /api/logging/api-calls/filters Endpoint

The system SHALL provide an endpoint to retrieve available filter options.

#### Scenario: Get filter options

- **WHEN** `GET /api/logging/api-calls/filters` is called
- **THEN** distinct endpoint paths, HTTP methods, status categories, and auth statuses from existing records are returned

### Requirement: DELETE /api/logging/api-calls Endpoint

The system SHALL provide a clear-all endpoint for API call log records.

#### Scenario: Clear all with confirmation header

- **WHEN** `DELETE /api/logging/api-calls` is called with `X-Confirm-Destructive: true` header
- **THEN** all ApiCallLog records are deleted
- **AND** the count of deleted records is returned

#### Scenario: Clear all without confirmation header

- **WHEN** `DELETE /api/logging/api-calls` is called without `X-Confirm-Destructive: true` header
- **THEN** the request is rejected with 403 status

### Requirement: Real-Time SSE Updates

The system SHALL broadcast new API call log records via SSE.

#### Scenario: New call broadcast

- **WHEN** a new API call is captured and persisted
- **THEN** an `api_call_logged` SSE event is broadcast with the call data

#### Scenario: Client-side real-time update

- **WHEN** the API log tab is open on page 1 and an `api_call_logged` SSE event is received
- **THEN** the new row is prepended to the table with a subtle animation
- **AND** it respects active filters (only shown if it matches)

### Requirement: Clear All Logs UI

The system SHALL provide a clear-all function with destructive confirmation.

#### Scenario: Clear all button

- **WHEN** the user clicks "Clear All Logs"
- **THEN** an inline confirmation prompt appears asking "Delete all?"

#### Scenario: Confirm delete

- **WHEN** the user confirms the delete action
- **THEN** all API call log records are deleted
- **AND** the table refreshes to show empty state

#### Scenario: Cancel delete

- **WHEN** the user cancels the delete action
- **THEN** the confirmation prompt is hidden
- **AND** no records are deleted

### Requirement: Empty and Error States

The system SHALL handle empty and error states gracefully.

#### Scenario: No records exist

- **WHEN** no API call log records exist
- **THEN** a message "No API calls recorded yet" is displayed

#### Scenario: No matching records

- **WHEN** filters are applied but no records match
- **THEN** a message "No API calls match the current filters" is displayed

#### Scenario: API error

- **WHEN** the API request to load records fails
- **THEN** an error message "Failed to load API calls" is displayed

## MODIFIED Requirements

### Requirement: Logging Tab Navigation (from e1-s10-logging-tab)

The logging tab navigation partial SHALL include three tabs instead of two.

#### Scenario: Updated tab bar

- **WHEN** the logging subsystem navigation renders
- **THEN** three tabs are shown: Events, Inference, API
- **AND** the API tab links to `/logging/api`
- **AND** the API tab active state is determined by `request.endpoint == 'logging.api_log_page'`

## REMOVED Requirements

None.
