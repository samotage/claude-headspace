# Delta Spec: e1-s13-hook-receiver

## ADDED Requirements

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

The system SHALL correlate incoming Claude Code session identifiers to tracked agents.

#### Scenario: Known session ID

Given a Claude session ID has been seen before
When a hook event arrives with that session ID
Then the event is routed to the correct agent

#### Scenario: New session in known directory

Given a new Claude session in a directory with an existing agent
When a hook event arrives
Then the session is correlated to the existing agent

#### Scenario: New session in unknown directory

Given a new Claude session in an unknown directory
When a hook event arrives
Then a new agent is created

### Requirement: High Confidence State Updates

The system SHALL record hook-originated state updates with high confidence indicator.

#### Scenario: Hook-originated update

Given a state update originates from a hook event
When the state is recorded
Then the confidence level is recorded as "high"
And events are emitted for downstream consumers

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

The system SHALL provide a notification script for Claude Code hooks.

#### Scenario: Successful notification

Given the application is running
When the hook script is executed
Then an HTTP request is sent to the application
And the script exits with status 0

#### Scenario: Application unavailable

Given the application is not running
When the hook script is executed
Then the script times out after 2 seconds
And the script exits with status 0 (does not block Claude Code)

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

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
