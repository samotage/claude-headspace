# agent-lifecycle Specification

## Purpose
TBD - created by archiving change e6-s4-agent-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Agent Creation via API

The system SHALL accept requests to create new Claude Code agents for registered projects. The system SHALL invoke the `claude-headspace` CLI to start a new session in the project's working directory within a tmux session. The new agent SHALL be registered with Claude Headspace and appear on the dashboard in idle state.

#### Scenario: Successful agent creation

- **WHEN** a `POST /api/agents` request is received with a valid `project_id`
- **THEN** the system starts a new Claude Code session in the project's directory
- **AND** the new agent is registered and appears on the dashboard
- **AND** the response includes the new agent's identifier

#### Scenario: Project not found

- **WHEN** a `POST /api/agents` request is received with an invalid or unregistered `project_id`
- **THEN** the system returns an error response indicating the project was not found

#### Scenario: Project path invalid

- **WHEN** a `POST /api/agents` request is received but the project's path does not exist on disk
- **THEN** the system returns an error response indicating the path is invalid

---

### Requirement: Agent Graceful Shutdown via API

The system SHALL accept requests to gracefully shut down active agents by sending the `/exit` command to the agent's tmux pane. The system SHALL rely on Claude Code's existing hook lifecycle to update agent state.

#### Scenario: Successful graceful shutdown

- **WHEN** a `DELETE /api/agents/<id>` request is received for an active agent with a tmux pane
- **THEN** the system sends `/exit` to the agent's tmux pane via tmux send-keys
- **AND** Claude Code fires session-end and stop hooks to update dashboard state

#### Scenario: Agent has no tmux pane

- **WHEN** a `DELETE /api/agents/<id>` request is received for an agent without a tmux pane
- **THEN** the system returns an error indicating the agent cannot be gracefully shut down

#### Scenario: Agent already ended

- **WHEN** a `DELETE /api/agents/<id>` request is received for an agent with `ended_at` set
- **THEN** the system returns an error indicating the agent is already ended

#### Scenario: Agent not found

- **WHEN** a `DELETE /api/agents/<id>` request is received for a non-existent agent
- **THEN** the system returns a 404 error

---

### Requirement: Context Window Usage Query

The system SHALL capture an agent's tmux pane content on demand and parse the context usage statusline (format: `[ctx: XX% used, XXXk remaining]`). The system SHALL return structured data including percentage used and tokens remaining.

#### Scenario: Context data available

- **WHEN** a `GET /api/agents/<id>/context` request is received for an active agent with a tmux pane
- **AND** the pane content contains a context usage statusline
- **THEN** the system returns `{percent_used: <int>, remaining_tokens: "<string>", available: true}`

#### Scenario: Context data unavailable (no statusline)

- **WHEN** a `GET /api/agents/<id>/context` request is received for an active agent
- **AND** the pane content does not contain a context usage statusline
- **THEN** the system returns `{available: false, reason: "statusline_not_found"}`

#### Scenario: Agent has no tmux pane

- **WHEN** a `GET /api/agents/<id>/context` request is received for an agent without a tmux pane
- **THEN** the system returns `{available: false, reason: "no_tmux_pane"}`

---

### Requirement: Dashboard Agent Controls

The dashboard SHALL provide controls for agent creation (project selector + button), graceful shutdown (per-card kill control), and context checking (per-card context indicator).

#### Scenario: Create agent from dashboard

- **WHEN** a user selects a project and clicks "New Agent"
- **THEN** a new agent is created for that project and appears on the dashboard

#### Scenario: Kill agent from dashboard

- **WHEN** a user clicks the kill control on an agent card
- **THEN** the agent receives a graceful `/exit` command and hooks update the dashboard

#### Scenario: Check context from dashboard

- **WHEN** a user clicks the context check control on an agent card
- **THEN** the context usage is displayed inline on the card (e.g., `45% used · 110k remaining`)

---

### Requirement: Voice/Text Bridge Agent Commands

The voice/text bridge SHALL support commands to create agents, shut down agents, and check context usage.

#### Scenario: Create agent via voice bridge

- **WHEN** a user sends a create command (e.g., "start an agent for [project]")
- **THEN** a new agent is created for the named project and a voice-formatted confirmation is returned

#### Scenario: Kill agent via voice bridge

- **WHEN** a user sends a kill command (e.g., "kill [agent]" or "shut down [agent]")
- **THEN** the specified agent receives a graceful shutdown and a voice-formatted confirmation is returned

#### Scenario: Check context via voice bridge

- **WHEN** a user sends a context command (e.g., "check context for [agent]")
- **THEN** the agent's context usage is returned in a voice-formatted response

---

### Requirement: Agent Turn Reconciliation

The system SHALL reconcile agent Turn records against JSONL transcript entries to ensure correct ordering and completeness.

#### Scenario: TranscriptReconciler integration

- **WHEN** new JSONL entries are detected for an agent's transcript
- **THEN** the TranscriptReconciler service SHALL be invoked to match entries against existing Turns
- **AND** correct timestamps from approximate (hook-time) to precise (JSONL) values
- **AND** create missing Turns that were not captured by hooks

#### Scenario: Reconciliation does not affect agent state

- **WHEN** the TranscriptReconciler creates or updates Turns
- **THEN** the agent's task state SHALL NOT be modified
- **AND** only Turn-level data (timestamp, timestamp_source, jsonl_entry_hash) SHALL be affected

