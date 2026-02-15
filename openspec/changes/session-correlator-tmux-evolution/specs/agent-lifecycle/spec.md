## MODIFIED Requirements

### Requirement: Session Correlation Strategy Numbering

The session correlator SHALL use sequential strategy numbering 1–6 for its correlation cascade.

#### Scenario: Strategy execution order

- **WHEN** a hook event arrives requiring session correlation
- **THEN** the correlator SHALL execute strategies in this order:
  - Strategy 1: In-memory cache lookup
  - Strategy 2: Database claude_session_id lookup
  - Strategy 3: Headspace session UUID (CLI-assigned) matching
  - Strategy 4: Tmux pane ID matching (survives context compression)
  - Strategy 5: Working directory matching (unclaimed agents only)
  - Strategy 6: Create new agent (requires valid working directory)

#### Scenario: Log messages use sequential numbering

- **WHEN** the correlator logs a strategy match or attempt
- **THEN** log messages SHALL reference strategies by their sequential number (1–6)
- **AND** SHALL NOT use fractional numbers (2.5, 2.75)

## ADDED Requirements

### Requirement: Tmux Session Name Capture

The system SHALL capture the tmux session name from hook payloads and persist it on the Agent record.

#### Scenario: Tmux session name from hook payload

- **WHEN** a hook event arrives with a `tmux_session` field in the JSON payload
- **AND** the correlated agent's `tmux_session` is NULL or different
- **THEN** the agent's `tmux_session` SHALL be updated to the payload value
- **AND** the change SHALL be committed to the database

#### Scenario: Tmux session name backfill on any hook

- **WHEN** any hook event (not just session-start) is processed for an agent
- **AND** the payload contains `tmux_session`
- **THEN** the agent's `tmux_session` SHALL be set if not already populated
- **AND** this SHALL use the existing backfill mechanism alongside tmux_pane_id backfill

#### Scenario: No tmux session in payload

- **WHEN** a hook event arrives without a `tmux_session` field
- **THEN** the agent's `tmux_session` SHALL NOT be modified
