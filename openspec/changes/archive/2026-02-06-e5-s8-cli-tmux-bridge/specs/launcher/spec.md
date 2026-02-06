## ADDED Requirements

### Requirement: tmux Pane Detection in CLI

The CLI launcher SHALL detect tmux pane presence via the `$TMUX_PANE` environment variable when the `--bridge` flag is passed.

#### Scenario: Inside tmux with --bridge

- **WHEN** `claude-headspace start --bridge` is run inside a tmux pane
- **THEN** the CLI outputs `Input Bridge: available (tmux pane %N)` to stdout
- **AND** the tmux pane ID is included in the session registration payload

#### Scenario: Outside tmux with --bridge

- **WHEN** `claude-headspace start --bridge` is run outside a tmux session
- **THEN** the CLI outputs `Input Bridge: unavailable (not in tmux session)` to stderr as a warning
- **AND** the session still launches successfully without a pane ID

#### Scenario: Without --bridge flag

- **WHEN** `claude-headspace start` is run without `--bridge`
- **THEN** no bridge detection or bridge-related output occurs
- **AND** Claude Code launches with monitoring only

### Requirement: Session Registration with tmux_pane_id

The `register_session()` CLI function SHALL accept an optional `tmux_pane_id` parameter and include it in the registration payload when provided.

#### Scenario: Registration includes pane ID

- **WHEN** `register_session()` is called with a `tmux_pane_id`
- **THEN** the HTTP POST payload includes `tmux_pane_id`

#### Scenario: Registration without pane ID

- **WHEN** `register_session()` is called without a `tmux_pane_id`
- **THEN** the HTTP POST payload does not include `tmux_pane_id`

### Requirement: Direct Claude Launch

The `launch_claude()` function SHALL always construct the command as `["claude"] + claude_args`. The `claudec_path` parameter SHALL be removed.

#### Scenario: Always direct launch

- **WHEN** `launch_claude()` is called
- **THEN** the command is always `["claude"] + claude_args`
- **AND** no wrapper binary is ever used

## REMOVED Requirements

### Requirement: claudec Detection

The `detect_claudec()` function and all references to claudec/claude-commander SHALL be removed from the CLI launcher.

#### Scenario: No claudec references remain

- **WHEN** the CLI launcher code is inspected
- **THEN** no references to `claudec`, `claude-commander`, `detect_claudec`, or `shutil.which("claudec")` exist
- **AND** the `shutil` import is removed

## MODIFIED Requirements

### Requirement: --bridge Flag Purpose

The `--bridge` flag's help text SHALL describe its purpose as enabling the tmux-based input bridge for dashboard responses.

#### Scenario: Help text accuracy

- **WHEN** `claude-headspace start --help` is run
- **THEN** the `--bridge` flag description references tmux-based input bridge
- **AND** no mention of claudec or commander appears

### Requirement: POST /api/sessions tmux_pane_id Support

The `POST /api/sessions` endpoint SHALL accept an optional `tmux_pane_id` field in the request body, store it on the Agent model at creation time, and register the agent with the `CommanderAvailability` service immediately.

#### Scenario: Registration with tmux_pane_id via API

- **WHEN** the registration payload includes `tmux_pane_id`
- **THEN** the value is stored on `agent.tmux_pane_id`
- **AND** `commander_availability.register_agent(agent.id, tmux_pane_id)` is called

#### Scenario: Registration without tmux_pane_id via API

- **WHEN** the registration payload does not include `tmux_pane_id`
- **THEN** `agent.tmux_pane_id` is NULL
- **AND** no availability registration occurs (hook backfill remains as fallback)
