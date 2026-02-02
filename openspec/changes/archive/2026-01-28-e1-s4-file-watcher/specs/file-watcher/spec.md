# Delta Spec: e1-s4-file-watcher

## ADDED Requirements

### Requirement: Session Registration API

The system SHALL provide an internal Python API to register sessions for monitoring.

#### Scenario: Register a new session

Given no session is registered for UUID "abc-123"
When register_session is called with session_uuid="abc-123", project_path="/Users/foo/project", working_directory="/Users/foo/project"
Then the session is added to the registry
And is_session_registered("abc-123") returns True

#### Scenario: Unregister an existing session

Given a session is registered with UUID "abc-123"
When unregister_session is called with session_uuid="abc-123"
Then the session is removed from the registry
And is_session_registered("abc-123") returns False

### Requirement: Session Registry Storage

The system SHALL maintain an in-memory registry of registered sessions with session UUID, project path, working directory, iTerm pane ID, registration timestamp, last activity timestamp, and jsonl file path.

#### Scenario: Registry stores all required fields

Given a session is registered with UUID, project_path, working_directory, and iterm_pane_id
When get_session is called for that UUID
Then the returned RegisteredSession contains all provided fields
And registered_at is set to the registration time
And last_activity_at is set to the registration time
And jsonl_file_path is initially None

### Requirement: JSONL File Locator

The system SHALL locate the jsonl file for a registered session by searching ~/.claude/projects/ for a folder matching the working directory.

#### Scenario: Locate jsonl file for standard path

Given a working directory of "/Users/samotage/dev/project"
And a folder "-Users-samotage-dev-project" exists in ~/.claude/projects/
And the folder contains "session.jsonl"
When locate_jsonl_file is called
Then it returns the path to "session.jsonl"

#### Scenario: Handle missing folder gracefully

Given a working directory with no matching folder in ~/.claude/projects/
When locate_jsonl_file is called
Then it returns None without raising an exception

### Requirement: Watchdog Integration

The system SHALL use Watchdog to monitor filesystem changes for registered sessions' jsonl files.

#### Scenario: Watch file modifications

Given a session is registered with a known jsonl file path
When the jsonl file is modified (content appended)
Then the file watcher detects the change
And processes the new content

#### Scenario: Debounce rapid changes

Given a session is registered
When the jsonl file is modified 10 times in 0.1 seconds
Then the file watcher processes the changes once (debounced)

### Requirement: JSONL Parser

The system SHALL parse Claude Code jsonl files, reading line-by-line and extracting turn data.

#### Scenario: Parse valid jsonl line

Given a jsonl file with a line containing actor, text, and timestamp
When read_new_lines is called
Then it returns a ParsedTurn with the correct actor, text, and timestamp

#### Scenario: Handle malformed line

Given a jsonl file with an invalid JSON line
When read_new_lines is called
Then it logs a warning
And skips the malformed line
And continues processing subsequent lines

#### Scenario: Incremental reading

Given a jsonl file has been read once
When new lines are appended to the file
And read_new_lines is called again
Then only the new lines are returned

### Requirement: Project Path Decoder

The system SHALL decode project paths from folder names by replacing dashes with slashes.

#### Scenario: Decode standard path

Given a folder name "-Users-samotage-dev-project"
When decode_project_path is called
Then it returns "/Users/samotage/dev/project"

#### Scenario: Encode path for reverse operation

Given a path "/Users/samotage/dev/project"
When encode_project_path is called
Then it returns "-Users-samotage-dev-project"

### Requirement: Git Metadata Extraction

The system SHALL extract git metadata for projects (repository URL and current branch) with caching.

#### Scenario: Extract git info from repository

Given a directory that is a git repository
When get_git_info is called
Then it returns the repository URL and current branch

#### Scenario: Cache git info

Given get_git_info was called for a path
When get_git_info is called again for the same path
Then it returns cached results without running git commands again

#### Scenario: Handle non-git directory

Given a directory that is not a git repository
When get_git_info is called
Then it returns GitInfo with repo_url=None and current_branch=None

### Requirement: Turn Detection and Event Emission

The system SHALL emit turn_detected events when new turns are detected in monitored jsonl files.

#### Scenario: Emit turn_detected event

Given a registered session
When a new turn is detected in the session's jsonl file
Then a turn_detected event is emitted
And the event contains session_uuid, project_path, actor, text, timestamp, and source="polling"

### Requirement: Session Inactivity Detection

The system SHALL detect inactive sessions and emit session_ended events when the inactivity timeout is exceeded.

#### Scenario: Detect inactive session

Given a session has been inactive for longer than the configured timeout
When the inactivity check runs
Then a session_ended event is emitted with reason="timeout"
And the session is automatically unregistered

### Requirement: Configuration Schema

The system SHALL extend config.yaml with file watcher settings including polling_interval, inactivity_timeout, and debounce_interval.

#### Scenario: Read file watcher configuration

Given config.yaml contains file_watcher settings
When the application starts
Then the FileWatcher uses the configured polling_interval
And uses the configured inactivity_timeout
And uses the configured debounce_interval

### Requirement: Polling Interval Control

The system SHALL support dynamic polling interval adjustment for hybrid mode operation.

#### Scenario: Adjust polling interval at runtime

Given the file watcher is running with a 2-second interval
When set_polling_interval(60) is called
Then the watcher adjusts to poll every 60 seconds

### Requirement: Flask Lifecycle Integration

The system SHALL integrate with Flask application lifecycle, starting when the app starts and stops when the app stops.

#### Scenario: Start with Flask app

Given a Flask application with FileWatcher configured
When the application starts
Then the FileWatcher starts its background thread

#### Scenario: Stop with Flask app

Given a Flask application with FileWatcher running
When the application shuts down
Then the FileWatcher stops gracefully
And releases all resources

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
