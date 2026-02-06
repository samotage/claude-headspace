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

The `POST /api/sessions` endpoint SHALL accept an optional `tmux_pane_id` field and store it on the Agent model at creation time.

#### Scenario: Registration with tmux_pane_id

- **WHEN** the registration payload includes `tmux_pane_id`
- **THEN** the value is stored on `agent.tmux_pane_id`
- **AND** the agent is registered with the `CommanderAvailability` service immediately

#### Scenario: Registration without tmux_pane_id

- **WHEN** the registration payload does not include `tmux_pane_id`
- **THEN** `agent.tmux_pane_id` is NULL
- **AND** no availability registration occurs (hook backfill remains as fallback)

### Requirement: Immediate Availability Monitoring

When the sessions endpoint receives a `tmux_pane_id`, it SHALL register the agent with the `CommanderAvailability` service immediately, so availability monitoring begins from session creation rather than waiting for the first hook event.

#### Scenario: Availability registered at session creation

- **WHEN** an agent is created via `POST /api/sessions` with a `tmux_pane_id`
- **THEN** `commander_availability.register_agent(agent.id, tmux_pane_id)` is called
- **AND** the dashboard respond widget is available from the first moment

## REMOVED Requirements

### Requirement: claudec Detection

The `detect_claudec()` function and all references to claudec/claude-commander SHALL be removed from the CLI launcher.

#### Scenario: No claudec references remain

- **WHEN** the CLI launcher code is inspected
- **THEN** no references to `claudec`, `claude-commander`, `detect_claudec`, or `shutil.which("claudec")` exist

### Requirement: claudec Wrapping in launch_claude

The `launch_claude()` function SHALL always construct the command as `["claude"] + claude_args`. The `claudec_path` parameter SHALL be removed.

#### Scenario: Direct claude launch

- **WHEN** `launch_claude()` is called
- **THEN** the command is always `["claude"] + claude_args`
- **AND** no wrapper binary is ever used

## UPDATED Requirements

### Requirement: --bridge Flag Purpose

The `--bridge` flag's help text SHALL describe its purpose as enabling the tmux-based input bridge for dashboard responses. No references to claudec or commander SHALL remain in any help text.

#### Scenario: Help text accuracy

- **WHEN** `claude-headspace start --help` is run
- **THEN** the `--bridge` flag description references tmux-based input bridge
- **AND** no mention of claudec or commander appears
