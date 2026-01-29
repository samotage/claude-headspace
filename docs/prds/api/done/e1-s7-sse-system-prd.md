---
validation:
  status: valid
  validated_at: '2026-01-29T10:21:25+11:00'
---

## Product Requirements Document (PRD) — SSE System

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 7 — Server-sent events for real-time updates
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

The SSE System is the real-time transport layer that pushes state updates from the server to browser clients. It enables the dashboard to reflect agent state changes instantly (<1 second latency) without polling, providing the "at a glance" awareness that makes Claude Headspace valuable.

Without SSE, users would need to manually refresh or implement client-side polling to see state changes. This sprint delivers the critical link between the event-driven backend (Sprints 4-6) and the reactive frontend (Sprint 8): a persistent HTTP connection that streams events as they occur.

The SSE system uses Server-Sent Events (SSE), a browser-native technology with built-in reconnection support. It integrates with HTMX on the frontend for seamless DOM updates. The implementation uses an in-memory broadcaster for Epic 1 simplicity, with the architecture supporting future Redis pub/sub for horizontal scaling.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace uses an event-driven architecture where state changes flow through an event pipeline:

```
File Watcher → Event System → State Machine → SSE System → Browser Dashboard
   (S4)           (S5)           (S6)           (S7)           (S8)
```

Sprint 6 produces state transitions (Task state changes, Turn detections). Sprint 7 delivers these to the browser in real-time. Sprint 8 renders the updates in the dashboard UI.

SSE is chosen over WebSockets because:
- Server-to-client push only (no bidirectional needed for Epic 1)
- Browser-native with automatic reconnection
- Works over HTTP/1.1 (no upgrade negotiation)
- HTMX has built-in SSE support

### 1.2 Target User

Developers using Claude Headspace who are monitoring multiple Claude Code sessions and need instant visibility into state changes across all agents without manual refresh.

### 1.3 Success Moment

A developer has the dashboard open in their browser. They issue a command in Claude Code. Within 1 second, the dashboard updates to show the agent's state transition from "idle" to "processing"—without any page refresh or user action.

---

## 2. Scope

### 2.1 In Scope

**SSE Endpoint:**
- HTTP endpoint that streams events to connected browser clients
- Long-lived HTTP connection with `text/event-stream` content type
- Supports multiple concurrent client connections

**Event Broadcaster Service:**
- Manages registry of connected SSE clients
- Broadcasts events to all connected clients
- Receives events from internal event sources (state machine, event system)

**Client Connection Management:**
- Track connected clients with unique identifiers
- Detect and handle client disconnections
- Clean up stale connections

**Heartbeat/Keepalive:**
- Periodic messages to prevent connection timeouts
- Configurable interval (default 30 seconds)
- Comment-style keepalive (`:` prefix) per SSE spec

**Reconnection Support:**
- Monotonic event IDs for Last-Event-ID header support
- Clients can resume from last received event on reconnect

**Event Filtering:**
- Clients can subscribe to specific event types
- Filter by project, agent, or event category
- Reduces bandwidth for focused monitoring

**Frontend Integration:**
- JavaScript/HTMX setup for receiving SSE events
- Event parsing and dispatch to UI components
- Automatic reconnection with backoff

**Connection Limits:**
- Configurable maximum concurrent connections
- Graceful rejection when limit reached

**Error Handling:**
- Error events sent to clients for issue visibility
- Graceful degradation on broadcaster failures

**Graceful Shutdown:**
- Clean closure of all SSE connections on server shutdown
- Clients receive close notification

### 2.2 Out of Scope

- **Redis pub/sub** — In-memory broadcaster for Epic 1; Redis for horizontal scaling in future
- **Event persistence** — SSE is transport only; Sprint 5 handles persistence
- **State machine logic** — Sprint 6 handles transitions; SSE broadcasts results
- **Dashboard UI rendering** — Sprint 8 builds UI; SSE provides data transport
- **Hook receiver endpoints** — Sprint 13 adds Claude Code hooks
- **Authentication/authorization** — Local-only for Epic 1; security in Epic 2
- **Multi-server coordination** — Single-server deployment for Epic 1
- **Event replay/history** — Clients get live events only; history via REST API
- **WebSocket support** — SSE sufficient for server-to-client push

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. SSE endpoint (`/api/events`) accepts connections and streams events
2. Browser receives state transition events within 1 second of emission
3. Multiple browser clients (5+) receive the same broadcast simultaneously
4. Disconnected clients reconnect automatically within 5 seconds
5. Heartbeat messages sent every 30 seconds keep connections alive through proxies
6. Clients can filter events by type via query parameter
7. Event IDs are included for Last-Event-ID reconnection support
8. Stale connections are detected and cleaned up within 60 seconds
9. Server gracefully closes SSE connections on shutdown
10. Connection limit (default 100) is enforced with graceful rejection

### 3.2 Non-Functional Success Criteria

1. Event delivery latency P95 < 100ms (from broadcast call to client receipt)
2. Broadcaster memory usage < 10MB for 100 concurrent connections
3. No memory leaks after 1 hour of continuous operation with connect/disconnect cycles
4. CPU usage < 2% when idle (heartbeats only, no events)
5. Handles burst of 50 events/second without dropping or significant delay

---

## 4. Functional Requirements (FRs)

### FR1: SSE Endpoint

The system shall provide an SSE endpoint that:
- Responds to GET requests at `/api/events`
- Returns `Content-Type: text/event-stream`
- Maintains a persistent HTTP connection
- Streams events in SSE format (`event:`, `data:`, `id:` fields)

### FR2: Event Broadcaster Service

The system shall provide a broadcaster service that:
- Maintains a registry of connected SSE clients
- Accepts events from internal sources (state machine, event system)
- Delivers events to all registered clients
- Supports event type categorization

### FR3: Client Registration

The system shall manage client connections:
- Assign unique identifier to each connected client
- Add client to broadcaster registry on connection
- Remove client from registry on disconnection
- Track connection metadata (connected_at, last_event_at)

### FR4: Event Broadcasting

The system shall broadcast events:
- Deliver each event to all connected clients
- Format events per SSE specification
- Include event type, JSON data payload, and event ID
- Handle individual client write failures without affecting others

### FR5: Heartbeat Mechanism

The system shall send heartbeat messages:
- Transmit keepalive every 30 seconds (configurable)
- Use SSE comment format (`: heartbeat` or `: ping`)
- Reset heartbeat timer on any event sent
- Detect failed heartbeat writes as disconnection signal

### FR6: Reconnection Support

The system shall support client reconnection:
- Include monotonic `id:` field in each event
- Accept `Last-Event-ID` header from reconnecting clients
- Log reconnection events for monitoring
- Note: Event replay not required for Epic 1 (clients get live events only)

### FR7: Event Filtering

The system shall support event filtering:
- Accept optional query parameters for filtering (e.g., `?types=state_transition,turn_detected`)
- Accept optional project filter (e.g., `?project_id=123`)
- Accept optional agent filter (e.g., `?agent_id=456`)
- Apply filters server-side before sending to client
- Default to all events if no filter specified

### FR8: Connection Limits

The system shall enforce connection limits:
- Configure maximum concurrent SSE connections (default 100)
- Return HTTP 503 Service Unavailable when limit reached
- Include `Retry-After` header suggesting reconnection delay
- Log when connection limit is reached

### FR9: Error Events

The system shall communicate errors to clients:
- Send error events for recoverable issues (e.g., `event: error`)
- Include error type and message in data payload
- Allow clients to handle errors gracefully

### FR10: Stale Connection Cleanup

The system shall clean up stale connections:
- Detect connections with failed writes
- Remove stale connections from registry within 60 seconds
- Log connection cleanup events

### FR11: Graceful Shutdown

The system shall handle shutdown gracefully:
- Close all SSE connections on SIGTERM/SIGINT
- Send close notification to clients before disconnecting
- Complete shutdown within 5 seconds
- Log shutdown completion

### FR12: Frontend SSE Integration

The system shall provide frontend integration:
- JavaScript module for SSE connection management
- Automatic reconnection with exponential backoff
- Event parsing and dispatch to registered handlers
- Compatible with HTMX SSE extension

### FR13: Configuration

The system shall be configurable via config.yaml:

```yaml
sse:
  heartbeat_interval_seconds: 30
  max_connections: 100
  connection_timeout_seconds: 60
  retry_after_seconds: 5
```

### FR14: Health Integration

The system shall integrate with health endpoint:
- Report number of active SSE connections
- Report broadcaster status (healthy/degraded)
- Include in `/health` endpoint response

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Event Format

The system shall use standard SSE format:
```
event: state_transition
id: 12345
data: {"agent_id": 1, "from_state": "idle", "to_state": "processing", "timestamp": "2026-01-29T10:00:00Z"}

```
(Note: Events separated by double newline)

### NFR2: Thread Safety

The system shall be thread-safe:
- Broadcaster handles concurrent event submissions
- Client registry handles concurrent connect/disconnect
- No race conditions on client iteration during broadcast

### NFR3: Backpressure Handling

The system shall handle slow clients:
- Detect clients not consuming events
- Log slow client warnings
- Remove clients that fall too far behind (configurable threshold)

### NFR4: Logging

The system shall provide comprehensive logging:
- INFO: Client connect/disconnect, broadcaster startup
- DEBUG: Individual events broadcast, heartbeats sent
- WARNING: Slow clients, write failures, connection limit approached
- ERROR: Broadcaster failures, unrecoverable errors

### NFR5: Observability

The system shall expose metrics:
- Active connection count
- Events broadcast per second
- Average event delivery latency
- Connection errors per minute

---

## 6. Technical Context

*Note: This section captures architectural decisions for implementation reference. These are recommendations, not requirements.*

### Recommended Architecture

- **SSE endpoint:** Flask route with generator function yielding SSE-formatted strings
- **Broadcaster:** Singleton service with thread-safe client registry
- **Client storage:** Dictionary keyed by unique client ID (UUID)
- **Event delivery:** Iterate registered clients, write to each response stream
- **Heartbeat:** Background thread or timer sending periodic keepalives

### File Structure

```
src/claude_headspace/
├── routes/
│   └── sse.py              # SSE endpoint blueprint
├── services/
│   └── broadcaster.py      # Event broadcaster service

static/js/
└── sse-client.js           # Frontend SSE integration

templates/
└── _sse_setup.html         # HTMX SSE partial (included in base.html)
```

### SSE Endpoint Pattern

```python
@sse_bp.route('/api/events')
def event_stream():
    def generate():
        client_id = broadcaster.register_client(request)
        try:
            while True:
                event = broadcaster.get_next_event(client_id, timeout=30)
                if event:
                    yield format_sse_event(event)
                else:
                    yield ': heartbeat\n\n'
        finally:
            broadcaster.unregister_client(client_id)

    return Response(generate(), mimetype='text/event-stream')
```

### HTMX Integration

```html
<div hx-ext="sse" sse-connect="/api/events" sse-swap="message">
    <!-- Content updated by SSE events -->
</div>
```

### Event Types to Broadcast

| Event Type | Source | Payload |
|------------|--------|---------|
| `state_transition` | State Machine (S6) | agent_id, task_id, from_state, to_state |
| `turn_detected` | Event System (S5) | agent_id, task_id, actor, intent |
| `session_discovered` | Event System (S5) | agent_id, project_id, session_uuid |
| `session_ended` | Event System (S5) | agent_id, reason |
| `objective_changed` | Objective API (S9) | objective_id, text |
| `heartbeat` | Broadcaster | timestamp |
| `error` | Broadcaster | error_type, message |

---

## 7. Dependencies

### Prerequisites

- Sprint 5 (Event System) complete — Events are being persisted
- Sprint 6 (State Machine) complete — State transitions are occurring

### Blocking

This sprint blocks:
- Sprint 8 (Dashboard UI) — Consumes SSE for real-time updates
- Sprint 9 (Objective Tab) — Uses SSE for objective change broadcasts
- Sprint 10 (Logging Tab) — Uses SSE for live event log updates

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSE connections timing out through proxies | Medium | Heartbeat mechanism (FR5) |
| Memory leaks from stale connections | High | Connection cleanup (FR10), monitoring |
| Reconnection storms (all clients reconnect at once) | Medium | Jittered retry in frontend (FR12) |
| Broadcasting to many clients causing latency | Medium | Connection limits (FR8), async broadcast |
| Browser SSE implementation differences | Low | Use well-tested HTMX SSE extension |

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
