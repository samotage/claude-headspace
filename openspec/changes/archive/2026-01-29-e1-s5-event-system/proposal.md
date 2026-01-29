# Proposal: e1-s5-event-system

## Summary

Implement the Event System that persists events from the file watcher to Postgres. This provides the critical persistence layer in the event-driven architecture, bridging event detection (Sprint 4) to state processing (Sprint 6).

## Motivation

Without reliable event persistence, the dashboard has no data, the state machine has no triggers, and there's no audit trail. The event system must run continuously as a background process, independent of Flask HTTP request cycles.

## Impact

### Files to Create
- `bin/watcher.py` - Background watcher process entry point
- `bin/run-watcher.sh` - Supervisor wrapper script
- `src/claude_headspace/services/event_writer.py` - EventWriter service class
- `src/claude_headspace/services/event_schemas.py` - Event type definitions and payload schemas
- `src/claude_headspace/services/process_monitor.py` - Health checking for background process
- `tests/services/test_event_writer.py` - EventWriter tests
- `tests/services/test_event_schemas.py` - Schema validation tests

### Files to Modify
- `config.yaml` - Add event_system configuration section
- `src/claude_headspace/config.py` - Add config accessors for event_system settings
- `src/claude_headspace/services/__init__.py` - Export new services
- `src/claude_headspace/services/file_watcher.py` - Wire up event writer callback

### Database Changes
None - Event model already exists from Sprint 3.

## Definition of Done

- [ ] EventWriter service accepts events and writes to Postgres
- [ ] Atomic writes with transaction per event
- [ ] Write failure handling with retry and exponential backoff
- [ ] Event validation against type taxonomy
- [ ] Payload schema validation per event type
- [ ] Background watcher process (bin/watcher.py)
- [ ] Process supervision wrapper script
- [ ] Crash loop protection (max 5 restarts in 60 seconds)
- [ ] Graceful shutdown (SIGTERM/SIGINT handling)
- [ ] Configuration schema extended
- [ ] Health reporting methods
- [ ] Integration with file watcher callbacks
- [ ] All unit tests passing

## Risks

- **Process isolation complexity**: Running a separate background process adds operational complexity. Mitigation: Simple shell wrapper for Epic 1, proper systemd in Epic 4.
- **Database connection management**: Background process needs its own connection pool. Mitigation: Use standalone SQLAlchemy session, not Flask-SQLAlchemy.
- **Graceful shutdown timing**: 2-second shutdown window may be tight under load. Mitigation: Test with realistic event volumes.

## Alternatives Considered

1. **Thread-based approach**: Run event writer in Flask thread. Rejected: Couples event capture to web server lifecycle.
2. **Celery/Redis queue**: Message queue for event processing. Rejected: Over-engineering for Epic 1.
3. **asyncio approach**: Use async event loop. Rejected: Adds complexity without clear benefit for this use case.
