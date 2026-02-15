# sse Specification

## Purpose
TBD - created by archiving change e1-s7-sse-system. Update Purpose after archive.
## Requirements
### Requirement: SSE Endpoint

The system SHALL provide an SSE endpoint for real-time event streaming.

#### Scenario: Client connects to SSE endpoint

Given a browser client
When it sends GET request to `/api/events`
Then it receives `Content-Type: text/event-stream`
And a persistent connection is established

#### Scenario: Event is streamed to client

Given a connected SSE client
When a state_transition event occurs
Then the client receives the event in SSE format
And the event includes type, data, and id fields

### Requirement: Event Broadcaster Service

The system SHALL provide a broadcaster service for managing SSE clients.

#### Scenario: Client registration

Given a new SSE connection
When the client connects
Then a unique ID is assigned
And the client is added to the broadcaster registry
And connection metadata is tracked

#### Scenario: Event broadcast

Given multiple connected clients
When an event is broadcast
Then all connected clients receive the event
And individual client failures do not affect others

### Requirement: Heartbeat Mechanism

The system SHALL send periodic heartbeat messages to keep connections alive.

#### Scenario: Heartbeat sent

Given a connected client with no recent events
When 30 seconds pass without an event
Then a heartbeat comment is sent (`: heartbeat`)
And the connection remains open

#### Scenario: Failed heartbeat detection

Given a disconnected client
When a heartbeat write fails
Then the client is marked for cleanup
And removed from the registry

### Requirement: Event Filtering

The system SHALL support filtering events by type and entity.

#### Scenario: Filter by event type

Given a client connected with `?types=state_transition`
When a turn_detected event is broadcast
Then the client does NOT receive it
And when a state_transition event is broadcast
Then the client receives it

#### Scenario: Filter by project

Given a client connected with `?project_id=123`
When an event for project 456 is broadcast
Then the client does NOT receive it

### Requirement: Connection Limits

The system SHALL enforce maximum concurrent connections.

#### Scenario: Connection limit reached

Given 100 connected clients (at limit)
When a new client attempts to connect
Then HTTP 503 is returned
And Retry-After header is included

### Requirement: Stale Connection Cleanup

The system SHALL clean up stale connections.

#### Scenario: Stale connection removed

Given a client with repeated write failures
When 60 seconds pass
Then the client is removed from registry
And cleanup is logged

### Requirement: Graceful Shutdown

The system SHALL handle shutdown gracefully.

#### Scenario: Server shutdown

Given connected SSE clients
When SIGTERM is received
Then close notification is sent to all clients
And all connections are closed
And shutdown completes within 5 seconds

### Requirement: Frontend SSE Integration

The system SHALL provide frontend JavaScript for SSE handling.

#### Scenario: Automatic reconnection

Given a connected frontend client
When the connection is lost
Then the client automatically reconnects
And exponential backoff is applied

### Requirement: Turn Event Types

The system SHALL support SSE event types for turn lifecycle.

#### Scenario: turn_created event

- **WHEN** a new Turn record is created (via hook, voice command, file upload, or reconciliation)
- **THEN** the broadcaster SHALL emit a `turn_created` SSE event
- **AND** the payload SHALL include: `agent_id`, `project_id`, `text`, `actor`, `intent`, `task_id`, `turn_id`, `timestamp`

#### Scenario: turn_updated event

- **WHEN** a Turn record is updated during transcript reconciliation (Phase 2)
- **THEN** the broadcaster SHALL emit a `turn_updated` SSE event
- **AND** the payload SHALL include: `agent_id`, `project_id`, `turn_id`, `timestamp`, `update_type`
- **AND** `update_type` SHALL be "timestamp_correction" for reconciliation-driven updates

#### Scenario: Client handles turn_updated

- **WHEN** a client receives a `turn_updated` event with `update_type=timestamp_correction`
- **THEN** the client SHALL update the affected bubble's `data-timestamp` attribute
- **AND** reorder the bubble to its correct chronological position

### Requirement: Health Integration

The system SHALL report SSE status in health endpoint.

#### Scenario: Health check includes SSE

Given the broadcaster is running
When `/health` is requested
Then response includes sse.active_connections count
And response includes sse.status

