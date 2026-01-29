# Tasks: e1-s7-sse-system

## Phase 1: Setup

- [ ] Add SSE configuration to config.yaml
- [ ] Add SSE config accessors to config.py
- [ ] Create routes directory structure if needed

## Phase 2: Implementation

### Event Broadcaster Service (FR2, FR3, FR4)
- [ ] Create broadcaster module
- [ ] Implement SSEClient dataclass with metadata
- [ ] Implement client registry with thread-safe operations
- [ ] Implement register_client() with unique ID generation
- [ ] Implement unregister_client() with cleanup
- [ ] Implement broadcast_event() to all connected clients
- [ ] Implement get_next_event() with timeout for client queues
- [ ] Handle individual client write failures gracefully

### Heartbeat Mechanism (FR5)
- [ ] Implement heartbeat timer (30 second default)
- [ ] Send SSE comment format keepalive (`: heartbeat\n\n`)
- [ ] Reset heartbeat timer on any event sent
- [ ] Detect failed heartbeat writes as disconnection

### SSE Endpoint (FR1, FR6)
- [ ] Create SSE blueprint
- [ ] Implement `/api/events` GET endpoint
- [ ] Return proper `text/event-stream` content type
- [ ] Implement generator function for streaming
- [ ] Include monotonic event IDs
- [ ] Accept Last-Event-ID header for reconnection logging

### Event Filtering (FR7)
- [ ] Accept `types` query parameter for event type filtering
- [ ] Accept `project_id` query parameter
- [ ] Accept `agent_id` query parameter
- [ ] Apply filters server-side before sending

### Connection Limits (FR8)
- [ ] Implement max connections check (default 100)
- [ ] Return HTTP 503 when limit reached
- [ ] Include Retry-After header

### Stale Connection Cleanup (FR10)
- [ ] Detect connections with failed writes
- [ ] Remove stale connections within 60 seconds
- [ ] Log connection cleanup events

### Error Events (FR9)
- [ ] Implement error event format
- [ ] Send error events for recoverable issues

### Graceful Shutdown (FR11)
- [ ] Handle SIGTERM/SIGINT
- [ ] Close all SSE connections cleanly
- [ ] Send close notification to clients

### Frontend Integration (FR12)
- [ ] Create sse-client.js module
- [ ] Implement automatic reconnection with exponential backoff
- [ ] Implement event parsing and dispatch
- [ ] Create HTMX SSE setup partial

### Health Integration (FR14)
- [ ] Report active SSE connection count
- [ ] Report broadcaster status
- [ ] Integrate with /health endpoint

### Configuration (FR13)
- [ ] heartbeat_interval_seconds (default 30)
- [ ] max_connections (default 100)
- [ ] connection_timeout_seconds (default 60)
- [ ] retry_after_seconds (default 5)

## Phase 3: Testing

- [ ] Test SSE endpoint connection
- [ ] Test event broadcast to multiple clients
- [ ] Test heartbeat mechanism
- [ ] Test event filtering
- [ ] Test connection limit enforcement
- [ ] Test stale connection cleanup
- [ ] Test graceful shutdown
- [ ] Test frontend reconnection
- [ ] Test thread safety of broadcaster
- [ ] Test event format compliance

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No linting errors
- [ ] Event delivery latency < 100ms verified
- [ ] Memory usage acceptable with 100 connections
