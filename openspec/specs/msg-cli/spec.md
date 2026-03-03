# msg-cli Specification

## Purpose
TBD - created by archiving change e9-s4-channel-service-cli. Update Purpose after archive.
## Requirements
### Requirement: Msg CLI Group (FR17)
A Click `AppGroup` named `msg` SHALL be registered in the app factory via `register_cli_commands()`. Subcommands: `send` and `history`.

#### Scenario: CLI registration
- **WHEN** the Flask app is created
- **THEN** `flask msg` is a valid CLI group with `send` and `history` subcommands

---

### Requirement: Msg Send Command
`flask msg send <slug> <content> [--type message|delegation|escalation] [--attachment <path>]` SHALL send a message to a channel. Default type is `message`.

#### Scenario: Send message
- **WHEN** `flask msg send workshop-review-7 "The constraint needs to be nullable"` is executed
- **THEN** a Message record is created in the channel

#### Scenario: Output
- **WHEN** a message is sent successfully
- **THEN** a confirmation with message ID and channel slug is printed

---

### Requirement: Msg History Command
`flask msg history <slug> [--format envelope|yaml] [--limit N] [--since ISO]` SHALL display message history. Default format is `envelope`, default limit is 50.

#### Scenario: Envelope format (default)
- **WHEN** `flask msg history workshop-review-7` is executed
- **THEN** messages are displayed in conversational envelope format

#### Scenario: YAML format
- **WHEN** `flask msg history workshop-review-7 --format yaml` is executed
- **THEN** messages are output as machine-consumable YAML

#### Scenario: Limit and since
- **WHEN** `--limit 20 --since 2026-03-03T10:00:00` is provided
- **THEN** at most 20 messages after the given timestamp are returned

---

### Requirement: Conversational Envelope Format
The envelope format SHALL render messages as:
```
[#channel-slug] PersonaName (agent:ID) -- DD Mon YYYY, HH:MM:
Message content here.

[#channel-slug] SYSTEM -- DD Mon YYYY, HH:MM:
System message content.
```
Person-type personas (no agent ID) omit the agent reference.

#### Scenario: Regular message
- **WHEN** a message from persona "Robbo" (agent 42) is formatted
- **THEN** the header is `[#slug] Robbo (agent:42) -- DD Mon YYYY, HH:MM:`

#### Scenario: System message
- **WHEN** a system message is formatted
- **THEN** the header is `[#slug] SYSTEM -- DD Mon YYYY, HH:MM:`

#### Scenario: Person without agent
- **WHEN** a message from persona "Sam" with no agent is formatted
- **THEN** the header is `[#slug] Sam -- DD Mon YYYY, HH:MM:`

---

### Requirement: YAML Output Format
The YAML format SHALL output a list of message dicts with keys: id, channel_slug, persona_slug, persona_name, agent_id, content, message_type, sent_at (ISO 8601).

#### Scenario: YAML structure
- **WHEN** `--format yaml` is used
- **THEN** each message is a YAML dict with the specified keys

