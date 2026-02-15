## MODIFIED Requirements

### Requirement: Agent Model

The system SHALL persist Agents with id, session_uuid (UUID), project_id FK, iterm_pane_id (nullable), tmux_pane_id (nullable), tmux_session (nullable String(128)), started_at, and last_seen_at.

#### Scenario: Create Agent

- **WHEN** a new Agent is created with session_uuid and project_id
- **THEN** the agent is persisted with FK relationship to Project

#### Scenario: Agent State Derivation

- **WHEN** Agent.state is accessed
- **THEN** it returns the current task's state, or IDLE if no active task

#### Scenario: Agent with tmux session name

- **WHEN** an Agent is created or updated with a tmux_session value
- **THEN** the tmux session name (e.g. `hs-claude-headspace-14100608`) is persisted as a nullable String(128)
- **AND** the value can be used for `tmux attach -t <tmux_session>`

#### Scenario: Agent without tmux session

- **WHEN** an Agent exists without a tmux_session value
- **THEN** tmux_session SHALL be NULL
- **AND** the dashboard attach action SHALL NOT be available for this agent
