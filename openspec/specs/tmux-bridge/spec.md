# tmux-bridge Specification

## Purpose
TBD - created by archiving change e5-s4-tmux-bridge. Update Purpose after archive.
## Requirements
### Requirement: tmux Bridge Service

The system SHALL provide a tmux bridge service (`tmux_bridge.py`) that wraps tmux CLI commands as subprocess calls for sending input to Claude Code sessions.

#### Scenario: Send literal text to tmux pane

- **WHEN** `send_text(pane_id, text)` is called with a valid pane ID
- **THEN** the system sends the text via `tmux send-keys -t <pane_id> -l "<text>"` followed by a separate `tmux send-keys -t <pane_id> Enter` call with a configurable delay (default 100ms) between them
- **AND** returns `SendResult(success=True)` with latency measurement

#### Scenario: Send special keys to tmux pane

- **WHEN** `send_keys(pane_id, "Enter")` or other special keys (Escape, Up, Down, C-c, C-u) are called
- **THEN** the system sends via `tmux send-keys -t <pane_id> <key>` without the `-l` flag

#### Scenario: tmux pane does not exist

- **WHEN** a tmux command targets a non-existent pane
- **THEN** the system returns a result with `error_type=PANE_NOT_FOUND`

#### Scenario: tmux not installed

- **WHEN** the `tmux` binary is not found on `PATH`
- **THEN** the system returns a result with `error_type=TMUX_NOT_INSTALLED`

#### Scenario: Subprocess timeout

- **WHEN** a tmux subprocess exceeds the configured timeout (default 5s)
- **THEN** the system returns a result with `error_type=TIMEOUT`

### Requirement: tmux Pane Health Check

The system SHALL check tmux pane health at two levels.

#### Scenario: Pane exists check

- **WHEN** `check_health(pane_id)` is called
- **THEN** the system checks pane existence via `tmux list-panes -a -F '#{pane_id}'`
- **AND** reports `available=True` if the pane ID is found

#### Scenario: Claude Code running check

- **WHEN** `check_health(pane_id)` is called
- **THEN** the system also checks `pane_current_command` for `claude` or `node`
- **AND** reports `running=True` if a matching process is detected

### Requirement: Agent tmux_pane_id Field

The Agent model SHALL have a `tmux_pane_id` field (nullable string) that stores the tmux pane ID.

#### Scenario: Pane ID coexistence

- **WHEN** an Agent has both `tmux_pane_id` and `iterm_pane_id` set
- **THEN** both fields function independently (tmux targeting vs iTerm focus)

### Requirement: Hook Pane ID Discovery

The hook notification script SHALL extract `$TMUX_PANE` and include it in every hook payload.

#### Scenario: Session start with tmux_pane

- **WHEN** a session-start hook fires with `tmux_pane` in the payload
- **THEN** the hook receiver stores the pane ID on `agent.tmux_pane_id`
- **AND** registers the agent with the availability tracker

#### Scenario: Late discovery via other hooks

- **WHEN** any non-session-start hook fires with `tmux_pane` in the payload
- **AND** the agent's `tmux_pane_id` is not yet set
- **THEN** the hook route handler stores it on `agent.tmux_pane_id`

### Requirement: Respond via tmux Bridge

The respond endpoint SHALL use tmux bridge for input delivery.

#### Scenario: Successful response delivery

- **WHEN** `POST /api/respond/<agent_id>` is called with valid text
- **AND** the agent is in AWAITING_INPUT state with a `tmux_pane_id`
- **THEN** the system sends text via `tmux_bridge.send_text(pane_id, text)`
- **AND** creates a Turn record (actor=USER, intent=ANSWER)
- **AND** transitions state AWAITING_INPUT -> PROCESSING
- **AND** broadcasts a state_changed SSE event with `turn_id` in the payload
- **AND** returns `{status: "ok", agent_id, new_state, latency_ms}`

#### Scenario: Agent has no pane ID

- **WHEN** `POST /api/respond/<agent_id>` is called
- **AND** the agent has no `tmux_pane_id`
- **THEN** the system returns HTTP 400 with `error_type: "no_pane_id"`

#### Scenario: API contract preserved

- **WHEN** the dashboard sends a respond request
- **THEN** the endpoint path, request body format, and response format are identical to the previous commander implementation

### Requirement: Availability Tracking via tmux

The CommanderAvailability class SHALL use tmux pane checks instead of socket probes.

#### Scenario: Availability SSE events

- **WHEN** a tmux pane's availability status changes
- **THEN** the system broadcasts `commander_availability` SSE event with `{agent_id, available, timestamp}`
- **AND** the `commander_available` response field name is preserved for backward compatibility

#### Scenario: Background health check

- **WHEN** the availability thread runs its periodic check
- **THEN** it iterates registered agents and calls `tmux_bridge.check_health()` for each

### Requirement: Configuration

The config.yaml SHALL have a `tmux_bridge:` section replacing `commander:`.

#### Scenario: Config values

- **WHEN** the tmux bridge reads configuration
- **THEN** it uses `health_check_interval` (30s), `subprocess_timeout` (5s), `text_enter_delay_ms` (100ms), `sequential_send_delay_ms` (150ms)

### Requirement: Session End Cleanup

The system SHALL preserve the `tmux_pane_id` field on session end while unregistering the agent from availability tracking.

#### Scenario: Session end preserves pane ID

- **WHEN** the session-end hook fires
- **THEN** the availability tracker unregisters the agent
- **AND** the `tmux_pane_id` field is NOT cleared (preserved for audit)

### Requirement: Extension Registration

The application SHALL register the tmux bridge service as `app.extensions["tmux_bridge"]` and MUST preserve the `app.extensions["commander_availability"]` key for backward compatibility.

#### Scenario: Both extensions registered

- **WHEN** the Flask application initializes
- **THEN** `app.extensions["tmux_bridge"]` contains the tmux bridge service instance
- **AND** `app.extensions["commander_availability"]` contains the availability tracker instance

### Requirement: Error Types

The system SHALL use `TmuxBridgeErrorType` enum with tmux-specific error types replacing `CommanderErrorType`.

#### Scenario: Error type mapping

- **WHEN** a tmux operation fails
- **THEN** the error is classified as one of: PANE_NOT_FOUND, TMUX_NOT_INSTALLED, SUBPROCESS_FAILED, NO_PANE_ID, TIMEOUT, SEND_FAILED, or UNKNOWN

