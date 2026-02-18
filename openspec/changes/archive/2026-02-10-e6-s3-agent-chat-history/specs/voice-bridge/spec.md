## ADDED Requirements

### Requirement: Agent Chat Transcript

The voice bridge transcript endpoint SHALL return an agent-lifetime conversation history with cursor-based pagination and real-time intermediate message capture.

#### Scenario: Agent with multiple completed tasks

- **WHEN** a GET to `/api/voice/agents/<agent_id>/transcript` is made
- **THEN** the response SHALL include turns from ALL tasks for that agent
- **AND** turns SHALL be ordered chronologically by timestamp
- **AND** each turn SHALL include `command_id`, `command_instruction`, and `task_state`

#### Scenario: Initial page load (no cursor)

- **WHEN** a GET to `/api/voice/agents/<agent_id>/transcript` is made without a `before` parameter
- **THEN** the response SHALL return the most recent N turns (default 50)
- **AND** SHALL include `has_more` boolean indicating if older turns exist

#### Scenario: Loading older messages (with cursor)

- **WHEN** a GET to `/api/voice/agents/<agent_id>/transcript?before=<turn_id>&limit=50` is made
- **THEN** the response SHALL return up to 50 turns older than the specified turn ID
- **AND** turns SHALL be ordered chronologically (oldest first within the page)
- **AND** SHALL include `has_more` boolean

#### Scenario: All history loaded

- **WHEN** there are no more turns older than the cursor
- **THEN** `has_more` SHALL be false

#### Scenario: Ended agent transcript

- **WHEN** a GET to `/api/voice/agents/<agent_id>/transcript` is made for an ended agent
- **THEN** the response SHALL return all historical turns across all tasks
- **AND** SHALL include `agent_ended: true` in the response

---

### Requirement: Real-Time Intermediate Message Capture

The system SHALL capture agent text output between tool calls as individual PROGRESS turns during the post-tool-use hook processing.

#### Scenario: Agent produces text between tool calls

- **WHEN** a post-tool-use hook fires
- **AND** the agent's transcript contains new text since the last read position
- **THEN** a PROGRESS turn SHALL be created with the new text content
- **AND** the turn SHALL be linked to the agent's current command

#### Scenario: Incremental transcript reading

- **WHEN** intermediate text is captured from the transcript
- **THEN** the system SHALL read only from the last known file position
- **AND** SHALL update the position after reading
- **AND** SHALL NOT re-read content already captured

#### Scenario: Deduplication with stop hook

- **WHEN** the agent's turn completes (stop hook fires)
- **AND** PROGRESS turns were captured during the same agent response
- **THEN** the final COMPLETION turn SHALL NOT duplicate text already captured as PROGRESS turns

#### Scenario: Empty text blocks

- **WHEN** a transcript read yields empty or whitespace-only text
- **THEN** no PROGRESS turn SHALL be created

#### Scenario: Performance constraint

- **WHEN** intermediate text capture occurs during post-tool-use hook processing
- **THEN** the capture SHALL add no more than 50ms to the hook response time
