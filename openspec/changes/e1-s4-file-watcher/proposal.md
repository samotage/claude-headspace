# Proposal: e1-s4-file-watcher

## Summary

Implement the file watcher subsystem for monitoring registered Claude Code sessions. This provides the polling/fallback mechanism that monitors jsonl files, parsing them incrementally and emitting events for downstream processing.

## Motivation

Claude Headspace uses a dual event source architecture where hooks (Sprint 13) are primary and file watcher polling is secondary. The file watcher provides:
- Fallback when hooks are unavailable
- Reconciliation to catch any missed events
- Turn detection from jsonl files

## Impact

### Files to Create
- `src/claude_headspace/services/__init__.py` - Services package init
- `src/claude_headspace/services/file_watcher.py` - Main FileWatcher service class
- `src/claude_headspace/services/jsonl_parser.py` - JSONL incremental parsing
- `src/claude_headspace/services/session_registry.py` - Session registration storage
- `src/claude_headspace/services/project_decoder.py` - Path decoding from folder names
- `src/claude_headspace/services/git_metadata.py` - Git metadata extraction with caching
- `tests/services/__init__.py` - Test package init
- `tests/services/test_file_watcher.py` - FileWatcher tests
- `tests/services/test_jsonl_parser.py` - Parser tests
- `tests/services/test_session_registry.py` - Registry tests
- `tests/services/test_project_decoder.py` - Decoder tests
- `tests/services/test_git_metadata.py` - Git metadata tests

### Files to Modify
- `config.yaml` - Add file_watcher and claude.projects_path settings
- `src/claude_headspace/config.py` - Add config accessors for new settings
- `pyproject.toml` or `requirements.txt` - Add watchdog dependency

### Database Changes
None - this sprint uses in-memory storage only.

## Definition of Done

- [ ] Session registration API implemented (register, unregister, get, is_registered)
- [ ] In-memory session registry with all required fields
- [ ] JSONL file locator finds files based on working directory
- [ ] Watchdog integration monitors registered sessions' files
- [ ] JSONL parser extracts turn data incrementally
- [ ] Project path decoder handles standard and edge cases
- [ ] Git metadata extraction with caching
- [ ] Turn detection emits events with correct structure
- [ ] Session inactivity detection with configurable timeout
- [ ] Configuration schema extended with file_watcher settings
- [ ] Dynamic polling interval control API
- [ ] Flask lifecycle integration (start/stop with app)
- [ ] All unit tests passing
- [ ] Thread-safe operations for registry access

## Risks

- **JSONL format uncertainty**: Claude Code jsonl format needs to be examined from actual files. Mitigation: Make parser flexible and log unknown fields.
- **Path decoding edge cases**: Spaces and special characters in paths. Mitigation: Comprehensive test cases for edge cases.
- **Watchdog platform differences**: macOS FSEvents vs Linux inotify. Mitigation: Use Watchdog's cross-platform API.

## Alternatives Considered

1. **Pure polling without Watchdog**: Simpler but less efficient. Rejected for performance reasons.
2. **inotify/FSEvents directly**: More efficient but platform-specific. Rejected for portability.
3. **File hash-based change detection**: More reliable but slower. Rejected for latency reasons.
