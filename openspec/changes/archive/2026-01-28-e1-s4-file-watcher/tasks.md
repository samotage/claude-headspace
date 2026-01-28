# Tasks: e1-s4-file-watcher

## Phase 1: Setup

- [x] Add watchdog to requirements.txt
- [x] Create services package structure
- [x] Add file_watcher config section to config.yaml
- [x] Add config accessors for new settings

## Phase 2: Implementation

### Session Registry (FR1, FR2)
- [x] Create SessionRegistry class with thread-safe storage
- [x] Implement register_session() method
- [x] Implement unregister_session() method
- [x] Implement get_registered_sessions() method
- [x] Implement is_session_registered() method
- [x] Add RegisteredSession dataclass with all required fields

### Project Decoder (FR6)
- [x] Create project_decoder module
- [x] Implement decode_project_path() function
- [x] Handle standard paths (-Users-foo-bar → /Users/foo/bar)
- [x] Handle edge cases (spaces, special characters)
- [x] Implement encode_project_path() for reverse operation

### JSONL Parser (FR5)
- [x] Create JSONLParser class
- [x] Implement incremental reading with position tracking
- [x] Extract turn data (actor, text, timestamp)
- [x] Handle malformed lines gracefully
- [x] Parse actual Claude Code jsonl format

### JSONL File Locator (FR3)
- [x] Implement locate_jsonl_file() function
- [x] Search ~/.claude/projects/ for matching folder
- [x] Find most recent jsonl file in folder
- [x] Handle missing folder/file (wait for creation)

### Git Metadata (FR7)
- [x] Create GitMetadata class with caching
- [x] Implement get_repo_url() method
- [x] Implement get_current_branch() method
- [x] Cache results per project path
- [x] Handle non-git directories gracefully

### File Watcher Core (FR4, FR8, FR11, FR12)
- [x] Create FileWatcher service class
- [x] Implement Watchdog observer setup
- [x] Watch registered sessions' jsonl files
- [x] Implement debouncing for rapid changes
- [x] Emit turn_detected events
- [x] Implement start() and stop() lifecycle methods
- [x] Implement set_polling_interval() for hybrid mode

### Session Inactivity (FR9)
- [x] Track last activity timestamp per session
- [x] Implement inactivity check with configurable timeout
- [x] Emit session_ended event on timeout
- [x] Auto-unregister inactive sessions

### Flask Integration
- [x] Register FileWatcher with Flask app extensions
- [x] Start watcher on app startup
- [x] Stop watcher on app shutdown

## Phase 3: Testing

- [x] Test SessionRegistry CRUD operations
- [x] Test thread-safety of registry
- [x] Test project path decoding (standard cases)
- [x] Test project path decoding (edge cases)
- [x] Test JSONL parsing (valid lines)
- [x] Test JSONL parsing (malformed lines)
- [x] Test incremental file reading
- [x] Test Git metadata extraction
- [x] Test Git metadata caching
- [x] Test file watcher event emission
- [x] Test debouncing behavior
- [x] Test session inactivity detection
- [x] Test polling interval control
- [x] Test Flask lifecycle integration

## Phase 4: Final Verification

- [x] All tests passing
- [x] No linting errors
- [x] Config schema documented
- [x] Integration points documented
