# Delta Spec: e1-s5-event-system

## ADDED Requirements

### Requirement: Event Writer Service

The system SHALL provide an event writer service that accepts events and writes them to the Postgres Event table.

#### Scenario: Write event successfully

Given a valid event with event_type and payload
When write_event is called
Then the event is persisted to the Event table
And the write returns success status

#### Scenario: Atomic transaction per event

Given an event write operation
When the write fails mid-transaction
Then no partial data is left in the database
And the failure is logged

### Requirement: Write Failure Handling

The system SHALL handle database write failures with retry logic.

#### Scenario: Retry on transient failure

Given a database write fails due to transient error
When the retry logic executes
Then the write is retried up to 3 times
And each retry uses exponential backoff

#### Scenario: Continue after max retries

Given a write fails after maximum retry attempts
When max retries are exhausted
Then the failure is logged with event details
And processing continues with subsequent events

### Requirement: Event Validation

The system SHALL validate events before writing to the database.

#### Scenario: Validate event type

Given an event with event_type not in the defined taxonomy
When validation runs
Then the event is rejected
And a warning is logged

#### Scenario: Validate payload schema

Given an event with invalid payload structure
When validation runs
Then the event is rejected
And the validation error is logged

### Requirement: Background Watcher Process

The system SHALL run a background process that executes the file watcher and event writer.

#### Scenario: Process runs independently

Given the background watcher process is started
When the Flask web server restarts
Then the watcher process continues running
And events continue to be captured

#### Scenario: Process startup

Given the application is starting
When the watcher process initializes
Then the file watcher is started
And the event writer is ready to receive events

### Requirement: Process Supervision

The system SHALL supervise the background watcher process and restart on failure.

#### Scenario: Auto-restart on crash

Given the watcher process crashes unexpectedly
When the supervisor detects termination
Then the process is restarted within 5 seconds
And the restart is logged

#### Scenario: Crash loop protection

Given the watcher process has restarted 5 times in 60 seconds
When another crash occurs
Then the supervisor stops restarting
And an error is logged

### Requirement: Event Types Taxonomy

The system SHALL define and enforce a consistent set of event types.

#### Scenario: Known event type accepted

Given an event with type "turn_detected"
When the event is validated
Then validation passes

#### Scenario: Unknown event type rejected

Given an event with type "unknown_event"
When the event is validated
Then validation fails
And the event is not written

### Requirement: Event Payload Schemas

The system SHALL enforce payload schemas per event type.

#### Scenario: Valid turn_detected payload

Given a turn_detected event with session_uuid, actor, text, source, turn_timestamp
When the payload is validated
Then validation passes

#### Scenario: Missing required field

Given a turn_detected event missing the required actor field
When the payload is validated
Then validation fails
And the missing field is identified in the error

### Requirement: Configuration Schema

The system SHALL extend config.yaml with event system settings.

#### Scenario: Read event system configuration

Given config.yaml contains event_system settings
When the event writer initializes
Then it uses the configured write_retry_attempts
And uses the configured write_retry_delay_ms

### Requirement: Graceful Shutdown

The system SHALL handle shutdown signals and flush pending events.

#### Scenario: Handle SIGTERM

Given the watcher process receives SIGTERM
When shutdown begins
Then pending events are flushed
And the process exits cleanly within 2 seconds

#### Scenario: Handle SIGINT

Given the watcher process receives SIGINT (Ctrl+C)
When shutdown begins
Then pending events are flushed
And the process exits cleanly

### Requirement: Health Reporting

The system SHALL report health status of the background process.

#### Scenario: Check process running

Given the background watcher is running normally
When is_watcher_running is called
Then it returns True

#### Scenario: Report write metrics

Given the event writer has processed events
When health status is queried
Then it includes last_write_timestamp
And includes failed_write_count

### Requirement: Startup Integration

The system SHALL integrate with application startup.

#### Scenario: Start with main application

Given the main application is starting
When startup completes
Then the background watcher process is running
And readiness is logged

#### Scenario: Degraded mode on failure

Given the background process fails to start
When the main application starts
Then the web server still runs
And a warning is logged about degraded mode

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
