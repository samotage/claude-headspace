# hooks Specification

## Purpose
TBD - created by archiving change e1-s13-hook-receiver. Update Purpose after archive.
## Requirements
### Requirement: Hook Event Reception Endpoints

The system SHALL provide API endpoints to receive hook events from Claude Code.

#### Scenario: Session start event

Given Claude Code starts a new session
When POST /hook/session-start is called with session data
Then the agent is created or activated with idle state
And status 200 is returned

#### Scenario: User prompt submit event

Given an active agent exists
When POST /hook/user-prompt-submit is called
Then the agent transitions to processing state
And status 200 is returned

#### Scenario: Stop (turn complete) event

Given an agent is in processing state
When POST /hook/stop is called
Then the agent transitions to idle state
And status 200 is returned

#### Scenario: Session end event

Given an active agent exists
When POST /hook/session-end is called
Then the agent is marked inactive
And status 200 is returned

#### Scenario: Notification event

Given an active agent exists
When POST /hook/notification is called
Then the agent timestamp is updated
And status 200 is returned

### Requirement: Hook Status Endpoint

The system SHALL provide an endpoint to query hook receiver status.

#### Scenario: Status query

When GET /hook/status is called
Then the response includes whether hooks are enabled
And the response includes last event timestamp
And the response includes current mode (hooks active vs polling fallback)

### Requirement: Session Correlation

The system SHALL correlate incoming Claude Code session identifiers to tracked agents. The correlator SHALL use 6 sequential strategies and accept a `tmux_session` parameter for persistence.

#### Scenario: Known session ID

- **WHEN** a Claude session ID has been seen before
- **AND** a hook event arrives with that session ID
- **THEN** the event is routed to the correct agent

#### Scenario: New session in known directory

- **WHEN** a new Claude session in a directory with an existing agent
- **AND** a hook event arrives
- **THEN** the session is correlated to the existing agent

#### Scenario: New session in unknown directory

- **WHEN** a new Claude session in an unknown directory
- **AND** a hook event arrives
- **THEN** a new agent is created

#### Scenario: Hook routes pass tmux_session

- **WHEN** any hook endpoint receives a request with `tmux_session` in the JSON body
- **THEN** the value SHALL be passed through to the session correlator and lifecycle bridge
- **AND** the agent's `tmux_session` field SHALL be updated if not already set

### Requirement: High Confidence State Updates

The system SHALL record hook-originated state updates with high confidence indicator.

#### Scenario: Hook-originated update

Given a state update originates from a hook event
When the state is recorded
Then the confidence level is recorded as "high"
And events are emitted for downstream consumers

### Requirement: Hook Turn Creation with SSE Broadcasting (Phase 1)

Hook event processing SHALL create Turn records with server timestamps and broadcast `turn_created` SSE events as Phase 1 of the three-phase event pipeline.

#### Scenario: Turn created from hook with SSE broadcast

- **WHEN** a hook event (stop, user-prompt-submit, post-tool-use) creates a Turn record
- **THEN** the Turn SHALL have `timestamp=now()` and `timestamp_source="server"`
- **AND** a `turn_created` SSE event SHALL be broadcast with `agent_id`, `project_id`, `text`, `actor`, `intent`, `command_id`, `turn_id`, and `timestamp` (ISO format)

#### Scenario: JSONL timestamps used for progress capture

- **WHEN** the hook receiver captures progress text from the transcript JSONL file
- **THEN** the Turn timestamp SHALL use the JSONL entry's timestamp when available
- **AND** the `timestamp_source` SHALL be set accordingly

#### Scenario: Broadcast includes timestamp

- **WHEN** any hook event triggers a state change broadcast
- **THEN** the broadcast payload SHALL include `turn.timestamp.isoformat()` for client-side ordering

### Requirement: Hybrid Mode

The system SHALL use hooks as the primary event source with polling fallback.

#### Scenario: Hooks active

Given hook events are being received regularly
When polling interval is configured
Then polling interval is 60 seconds (reconciliation only)

#### Scenario: Hooks silent

Given no hook events received for 300 seconds
When the fallback timeout expires
Then polling interval reverts to 2 seconds

#### Scenario: Hooks resume

Given hooks were silent and polling was increased
When hook events resume
Then polling interval returns to 60 seconds

### Requirement: Hook Notification Script

The system SHALL provide a notification script for Claude Code hooks. The script SHALL forward the tmux session name from the `CLAUDE_HEADSPACE_TMUX_SESSION` environment variable in the JSON payload.

#### Scenario: Successful notification

- **WHEN** the application is running
- **AND** the hook script is executed
- **THEN** an HTTP request is sent to the application
- **AND** the script exits with status 0

#### Scenario: Application unavailable

- **WHEN** the application is not running
- **AND** the hook script is executed
- **THEN** the script times out after 2 seconds
- **AND** the script exits with status 0 (does not block Claude Code)

#### Scenario: Tmux session name forwarded

- **WHEN** the hook script is executed
- **AND** the `CLAUDE_HEADSPACE_TMUX_SESSION` environment variable is set
- **THEN** the JSON payload SHALL include `tmux_session` with the env var value

#### Scenario: Tmux session name absent

- **WHEN** the hook script is executed
- **AND** the `CLAUDE_HEADSPACE_TMUX_SESSION` environment variable is not set
- **THEN** the JSON payload SHALL NOT include a `tmux_session` field

### Requirement: Hook Installation Script

The system SHALL provide an installation script for hook configuration.

#### Scenario: Clean installation

Given hooks are not installed
When the installation script runs
Then notify-headspace.sh is created in ~/.claude/hooks/
And ~/.claude/settings.json is updated with hook configuration
And all paths are absolute (not ~ or $HOME)
And the script is executable

### Requirement: Hook Status UI

The system SHALL display hook receiver status on the Logging tab.

#### Scenario: Status display

When the Logging tab is viewed
Then hook receiver enabled/disabled state is shown
And last hook event timestamp is shown
And current mode is shown

### Requirement: Agent Last Active Time

The system SHALL display last active time on agent cards.

#### Scenario: Last active display

Given an agent has recent activity
When the dashboard is viewed
Then the agent card shows "last active X ago"
And the time updates in real-time via SSE

