# agent-revival Specification

## Purpose
TBD - created by archiving change e8-s18-agent-revival. Update Purpose after archive.
## Requirements
### Requirement: CLI Transcript Command

The system SHALL provide a CLI command `claude-headspace transcript <agent-id>` that extracts an agent's conversation history from the database and outputs it as structured markdown to stdout.

The command MUST accept an agent ID (integer primary key from the Agent table) as a positional argument.

The output format MUST be:
- Each command as a `##` markdown section with the command's `instruction` text as the heading (or "Untitled Command" if instruction is null)
- Turns within each command listed chronologically (ordered by `timestamp` ASC)
- Each turn prefixed with actor label (`**User:**` or `**Agent:**`) followed by the turn's `text` content
- Timestamps included for each turn in ISO 8601 format
- Commands ordered chronologically (earliest `started_at` first)
- Turns with empty or null `text` content MUST be omitted

#### Scenario: Agent has conversation history

- **WHEN** the CLI command is invoked with a valid agent ID that has commands and turns
- **THEN** the full conversation history is output as structured markdown to stdout
- **AND** the exit code is 0

#### Scenario: Agent has no conversation history

- **WHEN** the CLI command is invoked with a valid agent ID that has no commands or no turns
- **THEN** a message "No conversation history found for agent <id>" is output to stdout
- **AND** the exit code is 0

#### Scenario: Agent not found

- **WHEN** the CLI command is invoked with an agent ID that does not exist in the database
- **THEN** an error message "Agent <id> not found" is output to stderr
- **AND** the exit code is 1

#### Scenario: CLI runs within Flask app context

- **WHEN** the transcript command executes
- **THEN** it MUST have access to the Flask application context and database session
- **AND** it MUST use the existing Flask CLI infrastructure (Click commands registered on the app)

---

### Requirement: Revive API Endpoint

The system SHALL provide an API endpoint `POST /api/agents/<int:agent_id>/revive` that initiates the revival flow for a dead agent.

#### Scenario: Successful revival

- **WHEN** a POST request is made with a valid dead agent ID (agent exists and `ended_at` is not null)
- **THEN** a new successor agent is created with the same `project_id` and `persona_id` as the predecessor
- **AND** the successor's `previous_agent_id` is set to the predecessor's ID
- **AND** the response status is 201 with the successor agent details
- **AND** the successor agent is started via `create_agent()` in a new tmux session

#### Scenario: Agent not found

- **WHEN** a POST request is made with an agent ID that does not exist
- **THEN** the response status is 404 with an error message

#### Scenario: Agent is still alive

- **WHEN** a POST request is made with an agent ID where `ended_at` is null
- **THEN** the response status is 400 with an error message "Agent is still alive, cannot revive"

---

### Requirement: Successor Agent Creation

The revival flow MUST create a successor agent with:
- The same `project_id` as the predecessor
- The same `persona_id` as the predecessor (resolved to `persona.slug` for `create_agent()`)
- `previous_agent_id` set to the predecessor's ID

The revival flow MUST use the existing `create_agent()` function in `agent_lifecycle.py`.

#### Scenario: Persona agent revival

- **WHEN** a dead agent with a persona is revived
- **THEN** the successor agent is created with the same persona slug
- **AND** skill injection occurs at session_start (existing behavior via `inject_persona_skills()`)
- **AND** revival instruction injection occurs AFTER skill injection

#### Scenario: Anonymous agent revival

- **WHEN** a dead agent without a persona is revived
- **THEN** the successor agent is created without a persona
- **AND** revival instruction injection occurs immediately at session_start (no skill injection step)

---

### Requirement: Revival Instruction Injection

After the successor agent's session_start hook fires, the system SHALL inject a revival instruction via the tmux bridge that tells the agent to run the CLI transcript command with the predecessor's agent ID.

The injection MUST occur:
- AFTER skill injection for persona-based agents
- AFTER handoff injection (if applicable) — though revival and handoff are mutually exclusive flows
- As the first injection for anonymous agents

#### Scenario: Revival instruction delivery

- **WHEN** a successor agent created via the revive flow completes session_start
- **AND** the agent has a tmux pane
- **THEN** a revival instruction is sent via `tmux_bridge.send_text()` telling the agent to run `claude-headspace transcript <predecessor-id>` and use the output to understand what the predecessor was working on

#### Scenario: Distinguish revival from handoff

- **WHEN** a successor agent has `previous_agent_id` set
- **AND** the predecessor agent does NOT have a Handoff record
- **THEN** the system treats this as a revival (not a handoff)
- **AND** injects the revival instruction instead of the handoff injection prompt

---

### Requirement: Revive UI Trigger

The dashboard SHALL display a "Revive" action button on dead agent cards (agents where `ended_at` is not null).

#### Scenario: Dead agent card shows revive button

- **WHEN** an agent card is rendered for a dead agent
- **THEN** a "Revive" button is visible
- **AND** clicking it calls `POST /api/agents/<id>/revive`
- **AND** feedback is shown (e.g., "Reviving..." spinner or status message)

#### Scenario: Live agent card does not show revive button

- **WHEN** an agent card is rendered for a live agent (`ended_at` is null)
- **THEN** the "Revive" button is NOT visible

#### Scenario: Successor card shows predecessor link

- **WHEN** a successor agent's card is rendered
- **AND** the agent has `previous_agent_id` set
- **THEN** the card displays an informational link showing it was revived from the predecessor

