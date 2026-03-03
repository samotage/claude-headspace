# channel-cli Specification

## Purpose
TBD - created by archiving change e9-s4-channel-service-cli. Update Purpose after archive.
## Requirements
### Requirement: Channel CLI Group (FR16)
A Click `AppGroup` named `channel` SHALL be registered in the app factory via `register_cli_commands()`. All subcommands resolve caller identity before delegating to ChannelService.

#### Scenario: CLI registration
- **WHEN** the Flask app is created
- **THEN** `flask channel` is a valid CLI group with subcommands

---

### Requirement: Channel Create Command
`flask channel create <name> --type <type> [--description] [--intent] [--org] [--project] [--members]` SHALL create a channel. `--type` is required (choices from ChannelType enum). `--members` accepts comma-separated persona slugs.

#### Scenario: Create with members
- **WHEN** `flask channel create "review" --type workshop --members "con,paula"` is executed
- **THEN** a channel is created with the creator as chair and con, paula added as members

#### Scenario: Output format
- **WHEN** a channel is created successfully
- **THEN** the channel slug and status are printed to stdout

---

### Requirement: Channel List Command
`flask channel list [--all] [--status <status>] [--type <type>]` SHALL list channels visible to the caller. `--all` shows all non-archived channels.

#### Scenario: Default list
- **WHEN** `flask channel list` is executed
- **THEN** only channels where the caller has an active membership are shown

#### Scenario: All visible
- **WHEN** `flask channel list --all` is executed
- **THEN** all non-archived channels are shown

---

### Requirement: Channel Show Command
`flask channel show <slug>` SHALL display channel details including name, type, status, description, members, message count, and timestamps.

#### Scenario: Show channel
- **WHEN** `flask channel show workshop-review-7` is executed
- **THEN** channel details are displayed in a formatted output

---

### Requirement: Channel Members Command
`flask channel members <slug>` SHALL display all members of the channel with their status, role, and agent information.

#### Scenario: List members
- **WHEN** `flask channel members workshop-review-7` is executed
- **THEN** all members are listed with persona name, status, is_chair, and agent_id

---

### Requirement: Channel Add Command
`flask channel add <slug> --persona <persona-slug>` SHALL add a persona to the channel.

#### Scenario: Add member
- **WHEN** `flask channel add workshop-review-7 --persona con` is executed
- **THEN** con is added to the channel

#### Scenario: Agent spin-up
- **WHEN** the added persona has no running agent
- **THEN** output indicates agent is spinning up

---

### Requirement: Channel Leave Command
`flask channel leave <slug>` SHALL remove the caller from the channel.

#### Scenario: Leave
- **WHEN** `flask channel leave workshop-review-7` is executed
- **THEN** the caller's membership status is set to `left`

---

### Requirement: Channel Complete Command
`flask channel complete <slug>` SHALL complete the channel (chair only).

#### Scenario: Complete
- **WHEN** the chair executes `flask channel complete workshop-review-7`
- **THEN** the channel status transitions to `complete`

---

### Requirement: Channel Transfer-Chair Command
`flask channel transfer-chair <slug> --to <persona-slug>` SHALL transfer chair role (current chair only).

#### Scenario: Transfer
- **WHEN** the chair executes `flask channel transfer-chair workshop-review-7 --to con`
- **THEN** con becomes the new chair

---

### Requirement: Channel Mute Command
`flask channel mute <slug>` SHALL mute the channel for the caller.

#### Scenario: Mute
- **WHEN** `flask channel mute workshop-review-7` is executed
- **THEN** the caller's membership status is set to `muted`

---

### Requirement: Channel Unmute Command
`flask channel unmute <slug>` SHALL unmute the channel for the caller.

#### Scenario: Unmute
- **WHEN** `flask channel unmute workshop-review-7` is executed
- **THEN** the caller's membership status is set back to `active`

---

### Requirement: CLI Error Handling
All channel CLI commands SHALL catch `ChannelError` subclasses, output the error message to stderr, and exit with code 1. `CallerResolutionError` is also caught and displayed.

#### Scenario: Channel error
- **WHEN** a ChannelError occurs during a CLI command
- **THEN** the error message is printed to stderr
- **AND** the exit code is 1

#### Scenario: Caller resolution error
- **WHEN** caller identity cannot be resolved
- **THEN** the CallerResolutionError message is printed to stderr
- **AND** the exit code is 1

