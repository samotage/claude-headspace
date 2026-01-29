# Proposal Summary: e1-s5-event-system

## Architecture Decisions
- Separate OS process for background watcher (not Flask thread) - ensures event capture survives Flask restarts
- Simple shell wrapper script for process supervision in Epic 1 (systemd deferred to Epic 4)
- Direct SQLAlchemy session (not Flask-SQLAlchemy) for database access from background process
- Callback-based event flow: File Watcher → callback → EventWriter → Postgres

## Implementation Approach
- Create EventWriter service class with retry logic and exponential backoff
- Define EventType enum matching the Event model constants
- Define Pydantic-style payload schemas for each event type
- Create bin/watcher.py as main entry point that wires file watcher to event writer
- Create bin/run-watcher.sh as supervisor wrapper with crash loop protection
- Create process_monitor module for health checking

## Files to Modify
**Configuration:**
- `config.yaml` - Add event_system settings section
- `src/claude_headspace/config.py` - Add config accessors

**Services:**
- `src/claude_headspace/services/__init__.py` - Export new services
- `src/claude_headspace/services/file_watcher.py` - Wire up event writer callback

**New Files:**
- `bin/watcher.py` - Background process entry point
- `bin/run-watcher.sh` - Process supervision wrapper
- `src/claude_headspace/services/event_writer.py` - EventWriter service
- `src/claude_headspace/services/event_schemas.py` - Event types and payload schemas
- `src/claude_headspace/services/process_monitor.py` - Health checking

## Acceptance Criteria
- Events emitted by file watcher are persisted to Postgres Event table
- Background watcher process runs continuously without Flask web server
- Process auto-restarts within 5 seconds of unexpected termination
- All defined event types are written with correct `event_type` field
- Event payloads are valid JSON conforming to defined schemas
- Graceful shutdown completes within 2 seconds, flushing pending events
- Database write failures are logged and retried (up to 3 attempts)
- Process crash loops are detected and limited (max 5 restarts in 60 seconds)

## Constraints and Gotchas
- Background process needs its own database connection pool (can't use Flask-SQLAlchemy app context)
- SIGTERM/SIGINT handling must flush pending events before exit
- 2-second shutdown timeout may be tight under heavy load
- Event model already exists from Sprint 3 - do NOT create migrations
- EventType enum must match model constants exactly
- Shell wrapper must track restart count and reset it after success period

## Git Change History

### Related Files
**Models:**
- src/claude_headspace/models/event.py (existing from Sprint 3)

**Services:**
- src/claude_headspace/services/file_watcher.py (Sprint 4, has callback system)
- src/claude_headspace/services/session_registry.py (Sprint 4)

**Config:**
- config.yaml (has file_watcher section)
- src/claude_headspace/config.py (has file_watcher accessors)

### OpenSpec History
- e1-s4-file-watcher: File watcher with callbacks and session registry (just completed)
- e1-s3-domain-models: Created Event model with event_type enum

### Implementation Patterns
**Detected structure from Sprint 4:**
1. Create service class with clear public API
2. Use dataclasses for data structures
3. Thread-safe operations where needed
4. Callback-based event flow
5. Configuration via config.yaml with accessor functions

## Q&A History
- No clarifications needed - PRD is comprehensive and consistent

## Dependencies
- **Existing dependencies:** SQLAlchemy, watchdog (from Sprint 4)
- **No new pip packages required**
- **Event model:** Already exists from Sprint 3 domain models
- **File watcher:** Already has callback system from Sprint 4

## Testing Strategy
- Test EventWriter write_event() success and failure cases
- Test atomic transaction behavior (rollback on failure)
- Test retry logic with mocked transient failures
- Test event type validation (accept valid, reject invalid)
- Test payload schema validation for each event type
- Test background process startup and shutdown
- Test signal handling (SIGTERM, SIGINT)
- Test process monitor health reporting

## OpenSpec References
- proposal.md: openspec/changes/e1-s5-event-system/proposal.md
- tasks.md: openspec/changes/e1-s5-event-system/tasks.md
- spec.md: openspec/changes/e1-s5-event-system/specs/event-system/spec.md
