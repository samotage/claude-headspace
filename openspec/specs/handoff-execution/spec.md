# handoff-execution Specification

## Purpose
TBD - created by archiving change e8-s14-handoff-execution. Update Purpose after archive.
## Requirements
### Requirement: Handoff trigger endpoint

The system SHALL provide `POST /api/agents/<id>/handoff` accepting `{ "reason": "..." }`. The endpoint SHALL validate: agent exists, is active (not ended), has a persona, and has a tmux pane. On validation failure, return 4xx error with description. On success, initiate async handoff flow and return 200 immediately.

#### Scenario: Valid handoff trigger
- **GIVEN** an active agent with persona and tmux pane
- **WHEN** POST /api/agents/{id}/handoff with reason "context_limit"
- **THEN** return 200 with status "initiated"
- **AND** handoff flow begins asynchronously

#### Scenario: Agent without persona
- **GIVEN** an active agent without a persona
- **WHEN** POST /api/agents/{id}/handoff
- **THEN** return 400 with error "Agent has no persona"

#### Scenario: Agent without tmux pane
- **GIVEN** an active agent with persona but no tmux pane
- **WHEN** POST /api/agents/{id}/handoff
- **THEN** return 400 with error describing missing tmux

#### Scenario: Agent already ended
- **GIVEN** an agent with ended_at set
- **WHEN** POST /api/agents/{id}/handoff
- **THEN** return 400 with error "Agent is not active"

#### Scenario: Agent already has handoff record
- **GIVEN** an agent that already has a Handoff DB record
- **WHEN** POST /api/agents/{id}/handoff
- **THEN** return 409 with error "Handoff already in progress"

---

### Requirement: Handoff instruction delivery

The system SHALL generate a handoff file path following `data/personas/{slug}/handoffs/{YYYYMMDDTHHmmss}-{agent-8digit}.md`. The system SHALL create the directory if needed. The system SHALL compose and send a handoff instruction via tmux bridge telling the outgoing agent to write a handoff document to that path.

#### Scenario: Handoff instruction sent
- **GIVEN** a valid handoff trigger for persona agent "developer-con-1"
- **WHEN** the handoff executor runs
- **THEN** a tmux message is sent to the agent's pane
- **AND** the message contains the file path under data/personas/developer-con-1/handoffs/
- **AND** the message instructs the agent to write: current work, progress, decisions, blockers, files modified, next steps

---

### Requirement: Handoff confirmation via stop hook

After sending the handoff instruction, the system SHALL set a handoff-in-progress flag. When the stop hook fires for an agent with this flag, the system SHALL verify the handoff file exists and is non-empty. Normal stop hooks (no flag) are unaffected.

#### Scenario: Stop hook with handoff file present
- **GIVEN** an agent with handoff-in-progress flag set
- **AND** the handoff file exists and is non-empty
- **WHEN** the stop hook fires
- **THEN** the handoff flow continues to record creation

#### Scenario: Stop hook with handoff file missing
- **GIVEN** an agent with handoff-in-progress flag set
- **AND** the handoff file does not exist
- **WHEN** the stop hook fires
- **THEN** a hard error is raised and reported to the operator
- **AND** the handoff flow halts
- **AND** the outgoing agent session remains active

#### Scenario: Stop hook with empty handoff file
- **GIVEN** an agent with handoff-in-progress flag set
- **AND** the handoff file exists but is empty (0 bytes)
- **WHEN** the stop hook fires
- **THEN** treated as failure (same as file not found)

#### Scenario: Normal stop hook unaffected
- **GIVEN** an agent without handoff-in-progress flag
- **WHEN** the stop hook fires
- **THEN** normal stop processing occurs unchanged

---

### Requirement: Handoff record creation

After file verification, the system SHALL create a Handoff DB record with: outgoing agent_id, reason, file_path, and a composed injection prompt for the successor. The injection prompt SHALL reference the predecessor and point to the handoff file path.

#### Scenario: Handoff record created
- **GIVEN** successful file verification
- **WHEN** the handoff record is created
- **THEN** Handoff.agent_id = outgoing agent's ID
- **AND** Handoff.reason = the trigger reason
- **AND** Handoff.file_path = the verified file path
- **AND** Handoff.injection_prompt contains predecessor reference and file path

---

### Requirement: Outgoing agent shutdown

After Handoff DB record creation, the system SHALL gracefully shut down the outgoing agent via `shutdown_agent()`.

#### Scenario: Graceful shutdown
- **GIVEN** Handoff record created successfully
- **WHEN** shutdown is initiated
- **THEN** the outgoing agent receives /exit via tmux
- **AND** the agent's ended_at is set

---

### Requirement: Successor agent creation

After outgoing agent ends, the system SHALL create a successor with the same persona via `create_agent(persona_slug=..., previous_agent_id=outgoing_agent.id)`.

#### Scenario: Successor created
- **GIVEN** outgoing agent has been shut down
- **WHEN** successor creation runs
- **THEN** a new agent is created with the same persona slug
- **AND** successor's previous_agent_id = outgoing agent's ID

#### Scenario: Successor creation fails
- **GIVEN** create_agent fails
- **WHEN** an error occurs during successor creation
- **THEN** a hard error is raised and reported to the operator
- **AND** the Handoff DB record is preserved for manual recovery

---

### Requirement: Successor bootstrap with handoff context

After the successor registers and receives skill injection (S9), the system SHALL send the injection prompt from the Handoff DB record to the successor via tmux bridge. Skill injection MUST complete before the handoff injection prompt is sent.

#### Scenario: Sequenced delivery
- **GIVEN** a successor agent has registered (session-start hook fired)
- **AND** skill injection has completed
- **WHEN** the handoff injection is delivered
- **THEN** the successor receives the injection prompt via tmux bridge
- **AND** the prompt references the predecessor and handoff file path

---

### Requirement: Error surfacing

Every failure in the handoff pipeline SHALL be surfaced to the operator via API error responses, SSE broadcasts, or OS notifications. No step SHALL fail silently.

#### Scenario: Error notification
- **GIVEN** any step in the handoff pipeline fails
- **WHEN** the error is detected
- **THEN** the operator is notified with error details
- **AND** the flow halts at the failed step

