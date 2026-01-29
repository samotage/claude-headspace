# Tasks: e1-s7-sse-system

## Phase 1: Setup

- [x] Add SSE configuration to config.yaml
- [x] Add SSE config accessors to config.py
- [x] Create routes directory structure if needed

## Phase 2: Implementation

### Event Broadcaster Service (FR2, FR3, FR4)
- [x] Create broadcaster module
- [x] Implement SSEClient dataclass with metadata
- [x] Implement client registry with thread-safe operations
- [x] Implement register_client() with unique ID generation
- [x] Implement unregister_client() with cleanup
- [x] Implement broadcast_event() to all connected clients
- [x] Implement get_next_event() with timeout for client queues
- [x] Handle individual client write failures gracefully

### Heartbeat Mechanism (FR5)
- [x] Implement heartbeat timer (30 second default)
- [x] Send SSE comment format keepalive (`: heartbeat\n\n`)
- [x] Reset heartbeat timer on any event sent
- [x] Detect failed heartbeat writes as disconnection

### SSE Endpoint (FR1, FR6)
- [x] Create SSE blueprint
- [x] Implement `/api/events` GET endpoint
- [x] Return proper `text/event-stream` content type
- [x] Implement generator function for streaming
- [x] Include monotonic event IDs
- [x] Accept Last-Event-ID header for reconnection logging

### Event Filtering (FR7)
- [x] Accept `types` query parameter for event type filtering
- [x] Accept `project_id` query parameter
- [x] Accept `agent_id` query parameter
- [x] Apply filters server-side before sending

### Connection Limits (FR8)
- [x] Implement max connections check (default 100)
- [x] Return HTTP 503 when limit reached
- [x] Include Retry-After header

### Stale Connection Cleanup (FR10)
- [x] Detect connections with failed writes
- [x] Remove stale connections within 60 seconds
- [x] Log connection cleanup events

### Error Events (FR9)
- [x] Implement error event format
- [x] Send error events for recoverable issues

### Graceful Shutdown (FR11)
- [x] Handle SIGTERM/SIGINT
- [x] Close all SSE connections cleanly
- [x] Send close notification to clients

### Frontend Integration (FR12)
- [x] Create sse-client.js module
- [x] Implement automatic reconnection with exponential backoff
- [x] Implement event parsing and dispatch
- [x] Create HTMX SSE setup partial

### Health Integration (FR14)
- [x] Report active SSE connection count
- [x] Report broadcaster status
- [x] Integrate with /health endpoint

### Configuration (FR13)
- [x] heartbeat_interval_seconds (default 30)
- [x] max_connections (default 100)
- [x] connection_timeout_seconds (default 60)
- [x] retry_after_seconds (default 5)

## Phase 3: Testing

- [x] Test SSE endpoint connection
- [x] Test event broadcast to multiple clients
- [x] Test heartbeat mechanism
- [x] Test event filtering
- [x] Test connection limit enforcement
- [x] Test stale connection cleanup
- [x] Test graceful shutdown
- [x] Test frontend reconnection
- [x] Test thread safety of broadcaster
- [x] Test event format compliance

## Phase 4: Final Verification

- [x] All tests passing
- [x] No linting errors
- [x] Event delivery latency < 100ms verified
- [x] Memory usage acceptable with 100 connections
