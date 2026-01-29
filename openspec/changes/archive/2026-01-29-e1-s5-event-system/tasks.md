# Tasks: e1-s5-event-system

## Phase 1: Setup

- [x] Add event_system config section to config.yaml
- [x] Add config accessors for event_system settings
- [x] Create bin/ directory structure

## Phase 2: Implementation

### Event Schemas (FR7, FR8)
- [x] Create event_schemas module
- [x] Define EventType constants matching model
- [x] Define payload schema for session_registered
- [x] Define payload schema for session_ended
- [x] Define payload schema for turn_detected
- [x] Define payload schema for state_transition
- [x] Define payload schema for hook_received
- [x] Implement validate_event_type() function
- [x] Implement validate_payload() function

### Event Writer Service (FR1, FR2, FR3, FR4)
- [x] Create EventWriter class
- [x] Implement write_event() method
- [x] Implement atomic transaction handling
- [x] Implement retry logic with exponential backoff
- [x] Implement validation before write
- [x] Handle database connection independently of Flask
- [x] Implement failure metrics tracking
- [x] Log write outcomes appropriately

### Background Watcher Process (FR5, FR6, FR11)
- [x] Create bin/watcher.py entry point
- [x] Initialize file watcher and event writer
- [x] Wire file watcher callbacks to event writer
- [x] Handle startup logging
- [x] Implement clean exit on signal

### Process Supervision (FR6)
- [x] Create bin/run-watcher.sh wrapper script
- [x] Implement restart loop
- [x] Implement crash loop detection
- [x] Implement max restart limiting
- [x] Log restart events

### Graceful Shutdown (FR10)
- [x] Handle SIGTERM signal
- [x] Handle SIGINT signal
- [x] Flush pending events before exit
- [x] Implement shutdown timeout
- [x] Log shutdown completion

### Health Reporting (FR12)
- [x] Create process_monitor module
- [x] Implement is_watcher_running() method
- [x] Track last successful write timestamp
- [x] Track failed write count
- [x] Expose health status for /health endpoint

### File Watcher Integration
- [x] Update file_watcher.py to accept event callbacks
- [x] Connect turn_detected events to event writer
- [x] Connect session_ended events to event writer

## Phase 3: Testing

- [x] Test EventWriter write_event() success
- [x] Test EventWriter atomic transactions
- [x] Test EventWriter retry logic
- [x] Test EventWriter validation rejection
- [x] Test event type validation
- [x] Test payload schema validation for each type
- [x] Test background process startup
- [x] Test graceful shutdown
- [x] Test signal handling
- [x] Test process monitor health reporting
- [x] Test file watcher integration

## Phase 4: Final Verification

- [x] All tests passing
- [x] No linting errors
- [x] Config schema documented
- [x] Process supervision tested manually
- [x] Graceful shutdown verified
