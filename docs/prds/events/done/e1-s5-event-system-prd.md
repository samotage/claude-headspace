---
validation:
  status: valid
  validated_at: '2026-01-29T10:02:45+11:00'
---

## Product Requirements Document (PRD) — Event System

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 5 — Event system writes to Postgres
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

The Event System is the persistence layer that bridges event detection (Sprint 4 File Watcher) to state processing (Sprint 6 State Machine). It ensures all Claude Code lifecycle events are durably stored in Postgres, providing the foundation for the event-driven architecture.

Without reliable event persistence, the dashboard has no data, the state machine has no triggers, and there's no audit trail. This sprint delivers the critical middle link in the event pipeline: receiving events from the file watcher, writing them atomically to the database, and running as a supervised background process that auto-restarts on failure.

The event system defines a consistent taxonomy of event types and payload schemas used across all event sources (file watcher polling and future hook events). It operates independently of the Flask web server, ensuring continuous event capture regardless of web request activity.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace uses an event-driven architecture where all state changes flow through an event log:

```
File Watcher (Sprint 4) → Event System (Sprint 5) → State Machine (Sprint 6)
         ↓                        ↓                         ↓
   Detects turns           Persists events            Transitions state
```

Sprint 4 detects events from Claude Code jsonl files but does not persist them. Sprint 5 receives these events and writes them to Postgres. Sprint 6 then processes persisted events to update Command/Turn state.

The event system must run continuously as a background process, independent of Flask HTTP request cycles. This ensures events are captured even when no web requests are active and survives web server restarts.

### 1.2 Target User

Developers using Claude Headspace who need reliable, real-time tracking of Claude Code sessions with a complete audit trail of all events.

### 1.3 Success Moment

A developer issues commands in Claude Code, and every turn is reliably captured in the Postgres event log—even if the Flask web server restarts or temporarily goes down. The event log provides a complete, queryable history of all session activity.

---

## 2. Scope

### 2.1 In Scope

**Event Writer Service:**
- Receive events from file watcher
- Write events atomically to Postgres Event table
- Handle database write failures gracefully (retry, log, continue)
- Validate event structure before writing

**Background Watcher Process:**
- Run continuously independent of Flask web server
- Execute file watcher and event writer together
- Start on application launch
- Stop gracefully on shutdown signal

**Event Types Taxonomy:**
- Define consistent event type strings used across the system
- Validate event types on write
- Support extensibility for future event sources

**Event Payload Schema:**
- Define JSON structure standards for each event type
- Validate payloads conform to schema
- Include required context (timestamps, session IDs, project paths)

**Process Supervision:**
- Automatically restart background process on crash
- Detect process failure within 5 seconds
- Log restart events for monitoring
- Limit restart attempts to prevent crash loops

**Configuration:**
- Add event system settings to config.yaml schema
- Configurable retry behavior for failed writes
- Configurable process supervision settings

**Graceful Shutdown:**
- Handle SIGTERM/SIGINT signals
- Flush pending events before exit
- Complete shutdown within 2 seconds

### 2.2 Out of Scope

- **File watcher implementation** — Sprint 4 delivers this
- **State machine logic** — Sprint 6 handles state transitions
- **Hook receiver endpoints** — Sprint 13 adds Claude Code hooks
- **SSE broadcasting** — Sprint 7 pushes events to browser
- **Turn intent detection** — Sprint 6 determines command/question/completion
- **Database migrations for Event model** — Sprint 3 creates the Event table
- **Systemd/launchd service files** — Manual process supervision for Epic 1
- **Event archival/cleanup** — Epic 4 handles data management

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Events emitted by file watcher are persisted to Postgres Event table within 1 second
2. Background watcher process runs continuously without Flask web server
3. Process auto-restarts within 5 seconds of unexpected termination
4. All defined event types are written with correct `event_type` field
5. Event payloads are valid JSON conforming to defined schemas
6. Events can be queried from database with correct timestamps and foreign key relationships
7. No event loss under normal operation (all emitted events are persisted)
8. Graceful shutdown completes within 2 seconds, flushing pending events
9. Database write failures are logged and retried (up to 3 attempts)
10. Process crash loops are detected and limited (max 5 restarts in 60 seconds)

### 3.2 Non-Functional Success Criteria

1. Event write latency P95 < 100ms
2. Background process uses < 50MB memory under normal operation
3. CPU usage < 5% when idle (no events flowing)
4. Process supervision adds < 1 second to application startup time
5. Event writer handles burst of 100 events/second without loss

---

## 4. Functional Requirements (FRs)

### FR1: Event Writer Service

The system shall provide an event writer service that:
- Accepts events from internal event sources (file watcher)
- Writes events to the Postgres Event table
- Includes timestamp, event_type, payload, and optional foreign keys (project_id, agent_id, command_id, turn_id)
- Returns success/failure status for each write

### FR2: Atomic Event Writes

The system shall write events atomically:
- Each event is a single database transaction
- Failed writes do not leave partial data
- Successful writes are immediately visible to queries

### FR3: Write Failure Handling

The system shall handle database write failures:
- Retry failed writes up to 3 times with exponential backoff
- Log all failures with event details and error message
- Continue processing subsequent events after max retries exceeded
- Track failure metrics for monitoring

### FR4: Event Validation

The system shall validate events before writing:
- Event type must be in the defined taxonomy
- Payload must be valid JSON
- Required fields must be present (timestamp, event_type)
- Invalid events are logged and rejected (not written)

### FR5: Background Watcher Process

The system shall run a background process that:
- Executes independently of the Flask web server process
- Runs the file watcher (Sprint 4) and event writer together
- Continues running when Flask restarts
- Can be started/stopped independently

### FR6: Process Supervision

The system shall supervise the background watcher process:
- Detect when the process terminates unexpectedly
- Restart the process automatically within 5 seconds
- Log each restart with reason and timestamp
- Implement crash loop protection (max 5 restarts in 60 seconds)

### FR7: Event Types Taxonomy

The system shall define and enforce these event types:

| Event Type | Description | Source |
|------------|-------------|--------|
| `session_registered` | Session registered for monitoring | Launcher (Sprint 11) |
| `session_ended` | Session inactive or unregistered | File Watcher |
| `turn_detected` | New turn parsed from jsonl | File Watcher |
| `state_transition` | Command state changed | State Machine (Sprint 6) |
| `hook_received` | Event from Claude Code hook | Hook Receiver (Sprint 13) |

### FR8: Event Payload Schemas

The system shall enforce payload schemas per event type:

**session_registered:**
```json
{
  "session_uuid": "string (required)",
  "project_path": "string (required)",
  "working_directory": "string (required)",
  "iterm_pane_id": "string (optional)"
}
```

**session_ended:**
```json
{
  "session_uuid": "string (required)",
  "reason": "string (required: timeout|unregistered|closed)",
  "duration_seconds": "integer (optional)"
}
```

**turn_detected:**
```json
{
  "session_uuid": "string (required)",
  "actor": "string (required: user|agent)",
  "text": "string (required)",
  "source": "string (required: polling|hook)",
  "turn_timestamp": "string (ISO8601, required)"
}
```

**state_transition:**
```json
{
  "agent_id": "integer (required)",
  "command_id": "integer (required)",
  "from_state": "string (required)",
  "to_state": "string (required)",
  "trigger": "string (required: turn|timeout|manual)"
}
```

**hook_received:**
```json
{
  "hook_type": "string (required)",
  "claude_session_id": "string (required)",
  "working_directory": "string (required)"
}
```

### FR9: Configuration Schema

The system shall extend config.yaml with event system settings:

```yaml
event_system:
  write_retry_attempts: 3
  write_retry_delay_ms: 100
  max_restarts_per_minute: 5
  shutdown_timeout_seconds: 2
```

### FR10: Graceful Shutdown

The system shall handle shutdown gracefully:
- Respond to SIGTERM and SIGINT signals
- Stop accepting new events
- Flush any pending/buffered events to database
- Complete shutdown within configured timeout
- Log shutdown completion

### FR11: Startup Integration

The system shall integrate with application startup:
- Background process starts when main application starts
- Process readiness is logged
- Failed startup is logged with error details
- Main application can start even if background process fails (degraded mode)

### FR12: Health Reporting

The system shall report health status:
- Expose method to check if background process is running
- Report last successful event write timestamp
- Report count of failed writes since startup
- Integrate with /health endpoint (degraded if process not running)

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Process Isolation

The background watcher process shall be isolated from Flask:
- Separate OS process (not a thread)
- Own database connection pool
- Crash does not affect Flask web server
- Flask crash does not affect event capture

### NFR2: Event Ordering

The system shall preserve event ordering:
- Events written in the order received
- Timestamps reflect actual event time (not write time)
- Database ordering matches emission ordering

### NFR3: Idempotency Consideration

The system shall handle duplicate events safely:
- Duplicate writes are logged as warnings
- No database constraint violations on duplicates
- Deduplication is caller's responsibility (future enhancement)

### NFR4: Logging

The system shall provide comprehensive logging:
- INFO: Process start/stop, successful writes (summary)
- DEBUG: Individual event writes, retry attempts
- WARNING: Write failures, validation errors, duplicates
- ERROR: Unrecoverable failures, crash loop detection

### NFR5: Resource Cleanup

The system shall clean up resources properly:
- Close database connections on shutdown
- Release file handles
- Clear in-memory buffers

---

## 6. Technical Context

*Note: This section captures architectural decisions for implementation reference. These are recommendations, not requirements.*

### Recommended Architecture

- **Background process:** Separate Python script (`bin/watcher.py`) that imports and runs file watcher + event writer
- **Process supervision:** Wrapper shell script with while loop for Epic 1 simplicity
- **Event flow:** File watcher → callback → event writer → Postgres
- **Database access:** Direct SQLAlchemy session (not through Flask-SQLAlchemy app context)

### File Structure

```
bin/
├── watcher.py              # Background watcher process entry point
└── run-watcher.sh          # Supervisor wrapper script

src/claude_headspace/
├── services/
│   ├── event_writer.py     # EventWriter service class
│   ├── event_bus.py        # Internal event routing (optional)
│   └── process_monitor.py  # Health checking for background process
```

### Wrapper Script Pattern

```bash
#!/bin/bash
# bin/run-watcher.sh - Simple process supervision

RESTART_COUNT=0
MAX_RESTARTS=5
RESTART_WINDOW=60

while true; do
    python bin/watcher.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "Watcher exited cleanly"
        break
    fi

    RESTART_COUNT=$((RESTART_COUNT + 1))
    echo "Watcher crashed (exit $EXIT_CODE), restart $RESTART_COUNT"

    if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
        echo "Max restarts reached, stopping"
        break
    fi

    sleep 2
done
```

### Integration with Sprint 4

The file watcher (Sprint 4) emits events via callback. Sprint 5 provides the callback implementation:

```python
# Sprint 4 emits:
file_watcher.on_event(callback_function)

# Sprint 5 provides:
def handle_event(event_type, event_data):
    event_writer.write(event_type, event_data)
```

---

## 7. Dependencies

### Prerequisites

- Sprint 3 (Domain Models) complete — Event model exists in database
- Sprint 4 (File Watcher) complete — Events are being emitted

### Blocking

This sprint blocks:
- Sprint 6 (State Machine) — Processes events from database
- Sprint 7 (SSE System) — Broadcasts events to browser
- Sprint 10 (Logging Tab) — Displays events from database

---

## 8. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
