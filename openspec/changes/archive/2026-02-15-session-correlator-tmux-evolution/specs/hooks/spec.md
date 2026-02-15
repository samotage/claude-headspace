## MODIFIED Requirements

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

## MODIFIED Requirements

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
