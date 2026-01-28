# Tasks: e1-s4-file-watcher

## Phase 1: Setup

- [ ] Add watchdog to requirements.txt
- [ ] Create services package structure
- [ ] Add file_watcher config section to config.yaml
- [ ] Add config accessors for new settings

## Phase 2: Implementation

### Session Registry (FR1, FR2)
- [ ] Create SessionRegistry class with thread-safe storage
- [ ] Implement register_session() method
- [ ] Implement unregister_session() method
- [ ] Implement get_registered_sessions() method
- [ ] Implement is_session_registered() method
- [ ] Add RegisteredSession dataclass with all required fields

### Project Decoder (FR6)
- [ ] Create project_decoder module
- [ ] Implement decode_project_path() function
- [ ] Handle standard paths (-Users-foo-bar → /Users/foo/bar)
- [ ] Handle edge cases (spaces, special characters)
- [ ] Implement encode_project_path() for reverse operation

### JSONL Parser (FR5)
- [ ] Create JSONLParser class
- [ ] Implement incremental reading with position tracking
- [ ] Extract turn data (actor, text, timestamp)
- [ ] Handle malformed lines gracefully
- [ ] Parse actual Claude Code jsonl format

### JSONL File Locator (FR3)
- [ ] Implement locate_jsonl_file() function
- [ ] Search ~/.claude/projects/ for matching folder
- [ ] Find most recent jsonl file in folder
- [ ] Handle missing folder/file (wait for creation)

### Git Metadata (FR7)
- [ ] Create GitMetadata class with caching
- [ ] Implement get_repo_url() method
- [ ] Implement get_current_branch() method
- [ ] Cache results per project path
- [ ] Handle non-git directories gracefully

### File Watcher Core (FR4, FR8, FR11, FR12)
- [ ] Create FileWatcher service class
- [ ] Implement Watchdog observer setup
- [ ] Watch registered sessions' jsonl files
- [ ] Implement debouncing for rapid changes
- [ ] Emit turn_detected events
- [ ] Implement start() and stop() lifecycle methods
- [ ] Implement set_polling_interval() for hybrid mode

### Session Inactivity (FR9)
- [ ] Track last activity timestamp per session
- [ ] Implement inactivity check with configurable timeout
- [ ] Emit session_ended event on timeout
- [ ] Auto-unregister inactive sessions

### Flask Integration
- [ ] Register FileWatcher with Flask app extensions
- [ ] Start watcher on app startup
- [ ] Stop watcher on app shutdown

## Phase 3: Testing

- [ ] Test SessionRegistry CRUD operations
- [ ] Test thread-safety of registry
- [ ] Test project path decoding (standard cases)
- [ ] Test project path decoding (edge cases)
- [ ] Test JSONL parsing (valid lines)
- [ ] Test JSONL parsing (malformed lines)
- [ ] Test incremental file reading
- [ ] Test Git metadata extraction
- [ ] Test Git metadata caching
- [ ] Test file watcher event emission
- [ ] Test debouncing behavior
- [ ] Test session inactivity detection
- [ ] Test polling interval control
- [ ] Test Flask lifecycle integration

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No linting errors
- [ ] Config schema documented
- [ ] Integration points documented
