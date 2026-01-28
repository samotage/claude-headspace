# Proposal Summary: e1-s4-file-watcher

## Architecture Decisions

- **Watchdog library** for filesystem monitoring (cross-platform, efficient)
- **In-memory registry** for session tracking (no database dependency for this sprint)
- **Incremental file reading** with byte position tracking (avoid re-reading entire files)
- **Debouncing** to prevent event storms from rapid Claude Code output
- **Threading model** - background thread for file watching, thread-safe registry access
- **Event emission interface** - events are emitted to be consumed by Sprint 5 Event System

## Implementation Approach

Build modular components that can be tested independently:
1. Start with pure functions (project decoder, git metadata extraction)
2. Build session registry with thread-safe storage
3. Create JSONL parser with incremental reading
4. Integrate Watchdog for file monitoring
5. Compose into FileWatcher service class
6. Register with Flask application lifecycle

## Files to Modify

### New Files to Create
- `src/claude_headspace/services/__init__.py` - Services package init
- `src/claude_headspace/services/session_registry.py` - Session registration storage
- `src/claude_headspace/services/project_decoder.py` - Path encoding/decoding
- `src/claude_headspace/services/jsonl_parser.py` - JSONL incremental parsing
- `src/claude_headspace/services/git_metadata.py` - Git info extraction with caching
- `src/claude_headspace/services/file_watcher.py` - Main FileWatcher service
- `tests/services/__init__.py` - Test package init
- `tests/services/test_session_registry.py`
- `tests/services/test_project_decoder.py`
- `tests/services/test_jsonl_parser.py`
- `tests/services/test_git_metadata.py`
- `tests/services/test_file_watcher.py`

### Files to Modify
- `config.yaml` - Add claude.projects_path and file_watcher configuration section
- `src/claude_headspace/config.py` - Add accessor functions for new settings
- `requirements.txt` - Add watchdog dependency

## Acceptance Criteria

- [ ] Session registration API works (register, unregister, get, is_registered)
- [ ] Sessions stored with all required fields (UUID, paths, timestamps, etc.)
- [ ] JSONL file located based on working directory
- [ ] Watchdog monitors registered sessions' files
- [ ] JSONL parser extracts turns incrementally
- [ ] Project path decoder handles standard and edge cases
- [ ] Git metadata extracted and cached
- [ ] turn_detected events emitted with correct structure
- [ ] session_ended events emitted on timeout
- [ ] Configuration schema extended
- [ ] Polling interval adjustable at runtime
- [ ] Flask lifecycle integration (start/stop)
- [ ] All operations thread-safe

## Constraints and Gotchas

- **Claude Code JSONL format**: Need to examine actual files to determine exact schema. Make parser flexible.
- **Path encoding edge cases**: Spaces and special characters. Test with real Claude Code folder names.
- **Watchdog macOS/Linux differences**: FSEvents vs inotify. Use Watchdog's cross-platform API.
- **Thread safety**: Registry accessed from multiple threads. Use threading.Lock.
- **Flask app context**: Git operations and file reading don't need app context, but event emission might need it for database access in Sprint 5.
- **Graceful shutdown**: Watchdog observer must be stopped cleanly on app shutdown.

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/event.py` (EventType constants)
- Config: `src/claude_headspace/config.py`, `config.yaml`
- Database: `src/claude_headspace/database.py`

### OpenSpec History
- e1-s3-domain-models (2026-01-29) - Created Event model with event_type constants

### Implementation Patterns
- Services are registered in `app.extensions["service_name"]`
- Config accessors use `get_value(config, section, key, default=value)` pattern
- Models use SQLAlchemy with Flask-SQLAlchemy

## Q&A History

No clarifications needed - PRD was clear and complete.

## Dependencies

- **watchdog** - Add to requirements.txt (filesystem monitoring)
- No database changes (in-memory registry only)
- No external APIs

## Testing Strategy

- Unit tests for each module independently
- Test session registry CRUD and thread safety
- Test project decoder with standard and edge case paths
- Test JSONL parser with valid, malformed, and incremental scenarios
- Test git metadata extraction and caching
- Test file watcher event emission
- Test debouncing behavior
- Test Flask lifecycle integration
- Use pytest fixtures for temporary directories and files

## OpenSpec References

- proposal.md: openspec/changes/e1-s4-file-watcher/proposal.md
- tasks.md: openspec/changes/e1-s4-file-watcher/tasks.md
- spec.md: openspec/changes/e1-s4-file-watcher/specs/file-watcher/spec.md
