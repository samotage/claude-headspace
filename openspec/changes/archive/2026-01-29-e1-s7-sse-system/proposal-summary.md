# Proposal Summary: e1-s7-sse-system

## Architecture Decisions
- Server-Sent Events (SSE) over WebSockets - simpler, browser-native, HTMX compatible
- In-memory broadcaster for Epic 1 (Redis pub/sub deferred for scaling)
- Thread-safe client registry with per-client event queues
- Generator-based streaming endpoint for memory efficiency
- Comment-style heartbeat (`: heartbeat`) per SSE spec

## Implementation Approach
- Create Broadcaster singleton service with thread-safe client registry
- Create SSE endpoint blueprint with generator function
- Implement heartbeat timer that resets on event send
- Create frontend JavaScript module with reconnection logic
- Integrate with health endpoint for monitoring

## Files to Modify
**Routes:**
- `src/claude_headspace/routes/__init__.py` - Register SSE blueprint

**Config:**
- `config.yaml` - Add sse section
- `src/claude_headspace/config.py` - Add SSE config accessors

**New Files:**
- `src/claude_headspace/routes/sse.py` - SSE endpoint blueprint
- `src/claude_headspace/services/broadcaster.py` - Event broadcaster service
- `static/js/sse-client.js` - Frontend SSE integration
- `templates/_sse_setup.html` - HTMX SSE partial
- `tests/routes/test_sse.py` - SSE endpoint tests
- `tests/services/test_broadcaster.py` - Broadcaster tests

## Acceptance Criteria
- SSE endpoint at `/api/events` accepts connections and streams events
- Browser receives events within 1 second of emission
- Multiple clients (5+) receive same broadcast simultaneously
- Heartbeat messages sent every 30 seconds
- Event filtering by type, project_id, agent_id
- Connection limit (100) enforced with HTTP 503
- Stale connections cleaned up within 60 seconds
- Graceful shutdown closes all connections

## Constraints and Gotchas
- SSE is unidirectional (server to client only)
- Content-Type MUST be `text/event-stream`
- Events MUST end with double newline (`\n\n`)
- Heartbeats use comment format (`: heartbeat\n\n`)
- Flask generator functions require special handling for cleanup
- Thread safety critical for concurrent client management
- Browser reconnection is automatic but needs jitter to avoid storms

## Git Change History

### Related Files
**Routes:**
- No existing routes (this is new subsystem)

**Services:**
- src/claude_headspace/services/event_writer.py (Sprint 5 - produces events)
- src/claude_headspace/services/state_machine.py (Sprint 6 - produces state transitions)

### OpenSpec History
- e1-s6-state-machine: State machine service (just completed)
- e1-s5-event-system: Event writer service (completed)
- e1-s4-file-watcher: File watching service (completed)

### Implementation Patterns
**Detected from Sprint 5/6:**
1. Create service class with clear public API
2. Use dataclasses for data structures (SSEClient)
3. Thread-safe operations with locks
4. Comprehensive logging at appropriate levels
5. Unit tests for all code paths

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required**
- **Event sources:** Sprint 5 EventWriter, Sprint 6 StateMachine
- **Frontend:** HTMX (already included in project)

## Testing Strategy
- Test SSE endpoint connection and content type
- Test event broadcast to multiple clients
- Test heartbeat mechanism and timing
- Test event filtering (types, project, agent)
- Test connection limit enforcement
- Test stale connection cleanup
- Test graceful shutdown
- Test frontend reconnection with mocked EventSource
- Test thread safety with concurrent operations
- Test SSE event format compliance

## OpenSpec References
- proposal.md: openspec/changes/e1-s7-sse-system/proposal.md
- tasks.md: openspec/changes/e1-s7-sse-system/tasks.md
- spec.md: openspec/changes/e1-s7-sse-system/specs/sse/spec.md
