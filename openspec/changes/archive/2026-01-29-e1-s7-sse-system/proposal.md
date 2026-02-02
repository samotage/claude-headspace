# Proposal: e1-s7-sse-system

## Summary

Implement the SSE (Server-Sent Events) system - the real-time transport layer that pushes state updates from the server to browser clients. Delivers events from Sprint 5/6 to the dashboard with <1 second latency.

## Motivation

Without SSE, users would need to manually refresh or implement client-side polling to see state changes. This sprint delivers the critical link between the event-driven backend (Sprints 4-6) and the reactive frontend (Sprint 8).

## Impact

### Files to Create
- `src/claude_headspace/routes/sse.py` - SSE endpoint blueprint
- `src/claude_headspace/services/broadcaster.py` - Event broadcaster service
- `static/js/sse-client.js` - Frontend SSE integration
- `templates/_sse_setup.html` - HTMX SSE partial
- `tests/routes/test_sse.py` - SSE endpoint tests
- `tests/services/test_broadcaster.py` - Broadcaster tests

### Files to Modify
- `src/claude_headspace/routes/__init__.py` - Register SSE blueprint
- `config.yaml` - Add SSE configuration section
- `src/claude_headspace/config.py` - Add SSE config accessors

### Database Changes
None - SSE is transport only, using in-memory broadcaster.

## Definition of Done

- [ ] SSE endpoint at `/api/events` accepting connections
- [ ] Event broadcaster service with client registry
- [ ] Heartbeat mechanism (30-second keepalive)
- [ ] Event filtering by type, project, agent
- [ ] Connection limit enforcement (default 100)
- [ ] Stale connection cleanup
- [ ] Graceful shutdown handling
- [ ] Frontend SSE client with reconnection
- [ ] Health endpoint integration
- [ ] All tests passing

## Risks

- **Connection timeouts through proxies**: Mitigated by heartbeat mechanism
- **Memory leaks from stale connections**: Mitigated by cleanup and monitoring
- **Reconnection storms**: Mitigated by jittered retry in frontend

## Alternatives Considered

1. **WebSockets**: More complex, bidirectional not needed. Rejected.
2. **Polling**: Higher latency, more resource usage. Rejected.
3. **Redis pub/sub**: Adds complexity for Epic 1. Deferred to scaling phase.
