# Tasks: e1-s5-event-system

## Phase 1: Setup

- [ ] Add event_system config section to config.yaml
- [ ] Add config accessors for event_system settings
- [ ] Create bin/ directory structure

## Phase 2: Implementation

### Event Schemas (FR7, FR8)
- [ ] Create event_schemas module
- [ ] Define EventType constants matching model
- [ ] Define payload schema for session_registered
- [ ] Define payload schema for session_ended
- [ ] Define payload schema for turn_detected
- [ ] Define payload schema for state_transition
- [ ] Define payload schema for hook_received
- [ ] Implement validate_event_type() function
- [ ] Implement validate_payload() function

### Event Writer Service (FR1, FR2, FR3, FR4)
- [ ] Create EventWriter class
- [ ] Implement write_event() method
- [ ] Implement atomic transaction handling
- [ ] Implement retry logic with exponential backoff
- [ ] Implement validation before write
- [ ] Handle database connection independently of Flask
- [ ] Implement failure metrics tracking
- [ ] Log write outcomes appropriately

### Background Watcher Process (FR5, FR6, FR11)
- [ ] Create bin/watcher.py entry point
- [ ] Initialize file watcher and event writer
- [ ] Wire file watcher callbacks to event writer
- [ ] Handle startup logging
- [ ] Implement clean exit on signal

### Process Supervision (FR6)
- [ ] Create bin/run-watcher.sh wrapper script
- [ ] Implement restart loop
- [ ] Implement crash loop detection
- [ ] Implement max restart limiting
- [ ] Log restart events

### Graceful Shutdown (FR10)
- [ ] Handle SIGTERM signal
- [ ] Handle SIGINT signal
- [ ] Flush pending events before exit
- [ ] Implement shutdown timeout
- [ ] Log shutdown completion

### Health Reporting (FR12)
- [ ] Create process_monitor module
- [ ] Implement is_watcher_running() method
- [ ] Track last successful write timestamp
- [ ] Track failed write count
- [ ] Expose health status for /health endpoint

### File Watcher Integration
- [ ] Update file_watcher.py to accept event callbacks
- [ ] Connect turn_detected events to event writer
- [ ] Connect session_ended events to event writer

## Phase 3: Testing

- [ ] Test EventWriter write_event() success
- [ ] Test EventWriter atomic transactions
- [ ] Test EventWriter retry logic
- [ ] Test EventWriter validation rejection
- [ ] Test event type validation
- [ ] Test payload schema validation for each type
- [ ] Test background process startup
- [ ] Test graceful shutdown
- [ ] Test signal handling
- [ ] Test process monitor health reporting
- [ ] Test file watcher integration

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No linting errors
- [ ] Config schema documented
- [ ] Process supervision tested manually
- [ ] Graceful shutdown verified
