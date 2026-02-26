# logging Specification

## Purpose
TBD - created by archiving change e1-s1-flask-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: Structured Logging
The application SHALL log to both console and file with structured format.

#### Scenario: Log entry format
- **WHEN** a log entry is created
- **THEN** it SHALL include timestamp in ISO 8601 format
- **AND** log level (DEBUG, INFO, WARNING, ERROR)
- **AND** logger name (module)
- **AND** message

#### Scenario: Log destinations
- **WHEN** the application logs a message
- **THEN** it SHALL appear in console (stdout)
- **AND** in `logs/app.log` file

#### Scenario: Log level configuration
- **WHEN** `FLASK_LOG_LEVEL=DEBUG` is set
- **THEN** DEBUG level messages SHALL be logged

### Requirement: Logging Tab Template

The system SHALL provide a logging tab page for viewing system events.

#### Scenario: Logging tab displays event table and filters

Given a user navigates to the logging tab
When the page loads
Then the filter bar is displayed at the top
And the event table is displayed below
And pagination controls are displayed at the bottom
And the page uses dark terminal aesthetic

### Requirement: Event Table Display

The system SHALL display events in a table format.

#### Scenario: Event table columns

Given the logging tab is displayed
When the event table renders
Then columns are displayed: Timestamp, Project, Agent, Event Type, Details

#### Scenario: Timestamp format

Given events exist in the table
When timestamps are displayed
Then they show in human-readable local time format (e.g., "2026-01-29 14:32:05")

#### Scenario: Agent identifier display

Given events exist in the table
When agent column renders
Then it displays truncated session UUID (e.g., "#2e3f...")

#### Scenario: Event ordering

Given events exist in the table
When the table renders
Then events are ordered by timestamp descending (most recent first)

### Requirement: Filter Controls

The system SHALL provide filter controls for narrowing event display.

#### Scenario: Project filter dropdown

Given the logging tab is displayed
When the project filter is shown
Then it lists all projects with events plus "All Projects" option

#### Scenario: Agent filter dropdown

Given the logging tab is displayed
When the agent filter is shown
Then it lists all agents with events plus "All Agents" option

#### Scenario: Event type filter dropdown

Given the logging tab is displayed
When the event type filter is shown
Then it lists all event types plus "All Types" option

#### Scenario: Combined filters

Given user selects project filter AND event type filter
When filters are applied
Then only events matching BOTH criteria are displayed

#### Scenario: Clear filters

Given filters are applied
When user clicks Clear Filters
Then all filters reset to default (all) state
And full event list is displayed

### Requirement: Pagination

The system SHALL paginate events for efficient display.

#### Scenario: Default pagination

Given more than 50 events exist
When logging tab loads
Then 50 events are displayed per page

#### Scenario: Pagination controls

Given paginated events
When pagination controls render
Then previous/next buttons are shown
And page indicator shows "Page X of Y"

#### Scenario: Pagination state on filter change

Given user is on page 3
When a filter is applied
Then pagination resets to page 1

### Requirement: Real-Time Updates

The system SHALL display new events in real-time via SSE.

#### Scenario: New event received

Given logging tab is open
When a new event is logged that matches current filters
Then the event appears at the top of the list automatically

#### Scenario: Visual indicator for new events

Given a new event is received via SSE
When it appears in the list
Then it has a brief highlight animation

#### Scenario: Scroll position preservation

Given user is scrolled down viewing older events
When a new event arrives
Then scroll position is not disrupted

### Requirement: Expandable Event Details

The system SHALL provide expandable rows for event details.

#### Scenario: Expand event row

Given an event row is displayed
When user clicks the row
Then it expands to show full JSON payload

#### Scenario: Collapse event row

Given an event row is expanded
When user clicks the row again
Then it collapses back to summary view

#### Scenario: Single expansion

Given an event row is expanded
When user clicks a different row
Then the previous row collapses
And the clicked row expands

### Requirement: GET /api/events Endpoint

The system SHALL provide endpoint to retrieve paginated events.

#### Scenario: Get events with no filters

Given events exist
When GET /api/events is called
Then paginated list of events is returned
And response includes total, page, pages, has_next, has_previous

#### Scenario: Get events with project filter

Given events exist for multiple projects
When GET /api/events?project_id=1 is called
Then only events for project 1 are returned

#### Scenario: Get events with combined filters

Given events exist
When GET /api/events?project_id=1&event_type=STATE_TRANSITION is called
Then only events matching both criteria are returned

#### Scenario: Pagination parameters

Given many events exist
When GET /api/events?page=2&per_page=25 is called
Then page 2 with 25 events per page is returned

### Requirement: GET /api/events/filters Endpoint

The system SHALL provide endpoint to retrieve filter options.

#### Scenario: Get filter options

Given events exist
When GET /api/events/filters is called
Then available projects, agents, and event types are returned
And only items with events are included

### Requirement: Empty States

The system SHALL handle empty states gracefully.

#### Scenario: No events at all

Given no events exist
When logging tab loads
Then "No events recorded yet" message is displayed

#### Scenario: No matching events

Given events exist but none match filters
When filters are applied
Then "No events match the current filters" message is displayed

### Requirement: Error Handling

The system SHALL handle errors gracefully.

#### Scenario: API error

Given API request fails
When response is received
Then user-friendly error message is displayed

#### Scenario: SSE connection loss

Given SSE connection is lost
When reconnection is attempted
Then exponential backoff is used

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

### Requirement: Logging Tab Navigation

The logging tab navigation partial SHALL include three tabs.

#### Scenario: Tab bar layout

- **WHEN** the logging subsystem navigation renders
- **THEN** three tabs are shown: Events, Inference, API
- **AND** the API tab links to `/logging/api`
- **AND** the API tab active state is determined by `request.endpoint == 'logging.api_log_page'`

