## MODIFIED Requirements

### Requirement: tmux Bridge Service

The system SHALL provide a tmux bridge service (`tmux_bridge.py`) that wraps tmux CLI commands as subprocess calls for sending input to Claude Code sessions.

#### Scenario: Send literal text to tmux pane

- **WHEN** `send_text(pane_id, text)` is called with a valid pane ID
- **THEN** the system sends the text via `tmux send-keys -t <pane_id> -l "<text>"` followed by a separate `tmux send-keys -t <pane_id> Enter` call with an adaptive delay between them
- **AND** the delay SHALL be computed as `base_delay + max(0, len(text) - 200) // 10` milliseconds, where `base_delay` defaults to 120ms
- **AND** returns `SendResult(success=True)` with latency measurement

#### Scenario: Post-typing ghost text dismissal

- **WHEN** `send_text()` has sent literal text and waited the adaptive delay
- **AND** `detect_ghost_text` is True (default)
- **THEN** the system SHALL capture the pane with ANSI escape sequences and check for autocomplete ghost text indicators (`\x1b[2m` dim or `\x1b[90m` dark gray) in the last 2-3 lines
- **AND** if ghost text is detected, the system SHALL send `Escape` to dismiss it and wait `clear_delay_ms` before proceeding to send Enter

#### Scenario: Enter verification with text-presence check for long text

- **WHEN** `send_text()` sends Enter with `verify_enter=True` (default)
- **AND** the sent text is 40 or more characters
- **THEN** the system SHALL extract a verification snippet from the tail of the sent text (last non-empty line, minimum 15 characters)
- **AND** after sending Enter, the system SHALL capture the pane and check if the snippet is still visible
- **AND** if the snippet is NOT found in the captured content, Enter SHALL be considered accepted (input was cleared)
- **AND** if the snippet IS still found, Enter SHALL be considered failed (text still in input) and the system SHALL retry

#### Scenario: Enter verification with content-change check for short text

- **WHEN** `send_text()` sends Enter with `verify_enter=True`
- **AND** the sent text is fewer than 40 characters (no reliable snippet available)
- **THEN** the system SHALL fall back to comparing pane content before and after Enter
- **AND** if content changed, Enter SHALL be considered accepted
- **AND** if content is unchanged, Enter SHALL be considered failed and the system SHALL retry

#### Scenario: Enter retry with ghost text recovery

- **WHEN** Enter verification determines that Enter was not accepted
- **THEN** the system SHALL check for autocomplete ghost text in the pane
- **AND** if ghost text is found, dismiss it with `Escape` + `clear_delay_ms` wait
- **AND** retry sending Enter
- **AND** repeat up to `max_enter_retries` times (default 3)

#### Scenario: All Enter retries exhausted

- **WHEN** Enter verification fails after all retry attempts
- **THEN** the system SHALL log a diagnostic dump of the pane content
- **AND** return `SendResult(success=False, error_type=SEND_FAILED)`

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

### Requirement: Respond via tmux Bridge

The respond endpoint SHALL use tmux bridge for input delivery.

#### Scenario: Successful response delivery

- **WHEN** `POST /api/respond/<agent_id>` is called with valid text
- **AND** the agent is in AWAITING_INPUT state with a `tmux_pane_id`
- **THEN** the system sends text via `tmux_bridge.send_text(pane_id, text, verify_enter=True)`
- **AND** creates a Turn record (actor=USER, intent=ANSWER)
- **AND** transitions state AWAITING_INPUT -> PROCESSING
- **AND** broadcasts a state_changed SSE event with `turn_id` in the payload
- **AND** returns `{status: "ok", agent_id, new_state, latency_ms}`

#### Scenario: Other mode response delivery

- **WHEN** `POST /api/respond/<agent_id>` is called with `mode: "other"`
- **THEN** the system navigates to the "Other" option via `send_keys` with `verify_enter=True`
- **AND** sends the custom text via `send_text(pane_id, text, verify_enter=True)`

#### Scenario: Agent has no pane ID

- **WHEN** `POST /api/respond/<agent_id>` is called
- **AND** the agent has no `tmux_pane_id`
- **THEN** the system returns HTTP 400 with `error_type: "no_pane_id"`

#### Scenario: API contract preserved

- **WHEN** the dashboard sends a respond request
- **THEN** the endpoint path, request body format, and response format are identical to the previous implementation

### Requirement: Configuration

The config.yaml SHALL have a `tmux_bridge:` section.

#### Scenario: Config values

- **WHEN** the tmux bridge reads configuration
- **THEN** it uses `health_check_interval` (30s), `subprocess_timeout` (5s), `text_enter_delay_ms` (120ms base, augmented by adaptive formula), `sequential_send_delay_ms` (150ms)

## ADDED Requirements

### Requirement: Verification Snippet Extraction

The system SHALL provide a `_extract_verification_snippet()` helper that extracts a distinctive tail from sent text for Enter verification.

#### Scenario: Long text produces snippet

- **WHEN** `_extract_verification_snippet(text)` is called with text of 40+ characters
- **THEN** the system SHALL return the last non-empty line of the text, truncated to 60 characters from the end
- **AND** the snippet SHALL be at least 15 characters long

#### Scenario: Short text returns None

- **WHEN** `_extract_verification_snippet(text)` is called with text shorter than 40 characters
- **THEN** the system SHALL return None (no reliable snippet available)

#### Scenario: Empty or whitespace-only text

- **WHEN** `_extract_verification_snippet(text)` is called with empty string or whitespace-only text
- **THEN** the system SHALL return None

#### Scenario: Text with only short lines

- **WHEN** `_extract_verification_snippet(text)` is called with text whose last non-empty line is fewer than 15 characters
- **THEN** the system SHALL return None (snippet too short for reliable matching)
