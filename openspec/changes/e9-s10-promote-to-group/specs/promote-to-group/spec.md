## ADDED Requirements

### Requirement: Channel spawned_from_agent_id Reference

The Channel model SHALL have an optional `spawned_from_agent_id` column as a foreign key to the Agent table with ON DELETE SET NULL behaviour. This column MUST be nullable and provides traceability from a group channel back to the originating 1:1 agent conversation.

#### Scenario: Channel created via promote-to-group

- **WHEN** a channel is created via the promote-to-group orchestration flow
- **THEN** the `spawned_from_agent_id` column MUST be set to the originating agent's ID

#### Scenario: Originating agent is deleted

- **WHEN** the originating agent record is deleted from the database
- **THEN** the `spawned_from_agent_id` column MUST be set to NULL (not cascade-deleted)

#### Scenario: Channel created via other methods

- **WHEN** a channel is created via the channel admin page or other creation flows
- **THEN** the `spawned_from_agent_id` column MUST remain NULL

---

### Requirement: Promote-to-Group Orchestration Endpoint

The system SHALL provide a `POST /api/agents/<agent_id>/promote-to-group` endpoint that accepts a JSON body with `persona_slug` and orchestrates the full spawn-and-merge flow.

#### Scenario: Successful promotion

- **WHEN** the operator submits a valid `persona_slug` for an active agent with an assigned persona
- **THEN** the system MUST:
  1. Create a new channel (type=workshop, status=active, spawned_from_agent_id set, auto-generated name)
  2. Add the operator's persona as member and chair
  3. Add the original agent's persona as member
  4. Spin up a fresh agent for the selected persona in the same project
  5. Add the new agent's persona as member
  6. Deliver a private context briefing (last 20 turns) to the new agent via tmux
  7. Post a system origin message in the channel
  8. Return the channel details with HTTP 201

#### Scenario: Agent not found

- **WHEN** the specified agent_id does not exist
- **THEN** the system MUST return HTTP 404

#### Scenario: Agent has no persona

- **WHEN** the specified agent has no persona assigned
- **THEN** the system MUST return HTTP 400 with error message "Agent has no persona assigned"

#### Scenario: Persona slug not found

- **WHEN** the specified persona_slug does not match any active persona
- **THEN** the system MUST return HTTP 404 with error message "Persona not found"

#### Scenario: Agent spin-up failure

- **WHEN** the agent spin-up fails during orchestration after the channel has been created
- **THEN** the system MUST clean up the partially-created channel and return HTTP 500 with error details
- **AND** the original 1:1 agent chat MUST NOT be affected

---

### Requirement: Conversation History Retrieval

The system SHALL provide a method to retrieve the last N turns from an agent's full conversation history, spanning all commands for that agent.

#### Scenario: Agent has more than N turns

- **WHEN** the agent has more than 20 turns across all commands
- **THEN** the system MUST return the 20 most recent turns ordered chronologically

#### Scenario: Agent has fewer than N turns

- **WHEN** the agent has fewer than 20 turns
- **THEN** the system MUST return all available turns

#### Scenario: Agent has no turns

- **WHEN** the agent has no conversation history
- **THEN** the system MUST return an empty list and the context briefing step MUST be skipped

---

### Requirement: Context Seeding via Private Briefing

The last 20 turns from the original agent's conversation history SHALL be formatted as a context briefing and delivered privately to the new agent via tmux injection. The briefing MUST NOT be posted as a visible message in the group channel.

#### Scenario: New agent receives briefing

- **WHEN** the new agent is spun up and has a tmux connection
- **THEN** the context briefing MUST be delivered via the existing `_deliver_context_briefing` pattern

#### Scenario: New agent has no tmux connection yet

- **WHEN** the new agent does not yet have a tmux pane
- **THEN** the briefing delivery MAY be deferred or skipped without failing the overall orchestration

---

### Requirement: Kebab Menu "Create Group Channel" Action

The agent card kebab menu SHALL include a "Create Group Channel" action item positioned after Handoff and before the divider.

#### Scenario: Active agent with persona

- **WHEN** the agent is active with an assigned persona and tmux connection
- **THEN** the "Create Group Channel" menu item MUST be visible and enabled

#### Scenario: Agent without persona

- **WHEN** the agent has no persona assigned
- **THEN** the "Create Group Channel" menu item MUST be visible but disabled with a tooltip explaining why

#### Scenario: Inactive agent

- **WHEN** the agent is dismissed, ended, or has no tmux connection
- **THEN** the "Create Group Channel" menu item MUST NOT be visible

---

### Requirement: Persona Picker Dialog

Clicking "Create Group Channel" SHALL open a modal dialog with a searchable list of active personas.

#### Scenario: Dialog content

- **WHEN** the persona picker dialog is opened
- **THEN** it MUST display:
  - Title "Add Agent to Group Channel"
  - Subtitle referencing the original agent's persona name
  - Searchable list of active personas with name and role
  - Confirm button (disabled until selection) and Cancel button

#### Scenario: Persona filtering

- **WHEN** the persona list is populated
- **THEN** it MUST exclude: the original agent's persona, the operator's persona, and personas already in a channel with the original agent

#### Scenario: Confirm action

- **WHEN** the operator selects a persona and clicks Confirm
- **THEN** the dialog MUST close and the promote-to-group API call MUST be triggered with a loading indicator

---

### Requirement: System Origin Message

A system message SHALL be posted in the newly created group channel indicating its origin.

#### Scenario: Channel created successfully

- **WHEN** the promote-to-group orchestration completes
- **THEN** a system message "Channel created from conversation with [original agent persona name]. Context: last 20 messages shared." MUST be posted in the channel

---

### Requirement: Operator Auto-Join

The operator's persona SHALL be automatically added as a member and chair of the new group channel.

#### Scenario: Channel creation

- **WHEN** a group channel is created via promote-to-group
- **THEN** the operator's persona MUST be added as a member with chair role without requiring manual action
