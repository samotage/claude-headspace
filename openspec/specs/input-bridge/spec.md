# input-bridge Specification

## Purpose
TBD - created by archiving change e5-s1-input-bridge. Update Purpose after archive.
## Requirements
### Requirement: Response Submission API

The system SHALL provide an API endpoint for submitting text responses to Claude Code sessions from the dashboard.

#### Scenario: Submit response successfully

- **WHEN** `POST /api/respond/<agent_id>` is called with `{"text": "1"}`
- **AND** the agent is in AWAITING_INPUT state
- **AND** the agent has a reachable commander socket
- **THEN** the text is sent to the commander socket
- **AND** a Turn record is created with actor=USER, intent=ANSWER, text="1"
- **AND** the task state transitions from AWAITING_INPUT to PROCESSING
- **AND** a state_changed SSE event is broadcast with `turn_id` included in the payload
- **AND** the response returns HTTP 200 with `{"status": "ok"}`

#### Scenario: Agent not found

- **WHEN** `POST /api/respond/<agent_id>` is called with a non-existent agent ID
- **THEN** the response returns HTTP 404 with error message

#### Scenario: Agent not in AWAITING_INPUT state

- **WHEN** `POST /api/respond/<agent_id>` is called
- **AND** the agent is not in AWAITING_INPUT state
- **THEN** the response returns HTTP 409 with error message indicating wrong state

#### Scenario: No claude_session_id

- **WHEN** `POST /api/respond/<agent_id>` is called
- **AND** the agent has no `claude_session_id`
- **THEN** the response returns HTTP 400 with error message

#### Scenario: Commander socket unavailable

- **WHEN** `POST /api/respond/<agent_id>` is called
- **AND** the commander socket is not reachable
- **THEN** the response returns HTTP 503 with error message

#### Scenario: Commander send failure

- **WHEN** the commander socket is reachable but the send operation fails
- **THEN** the response returns HTTP 502 with error message
- **AND** no Turn record is created
- **AND** no state transition occurs

---

### Requirement: Dashboard Input Widget

The system SHALL display an input widget on agent cards in AWAITING_INPUT state when a commander socket is available.

#### Scenario: Display quick-action buttons

- **WHEN** an agent is in AWAITING_INPUT state
- **AND** a commander socket is available
- **AND** the question text contains numbered options (e.g., "1. Yes / 2. No / 3. Cancel")
- **THEN** the agent card displays quick-action buttons for each option
- **AND** clicking a button sends the option number as the response

#### Scenario: Display free-text input

- **WHEN** an agent is in AWAITING_INPUT state
- **AND** a commander socket is available
- **THEN** the agent card displays a free-text input field with a send button
- **AND** the user can type and submit an arbitrary response

#### Scenario: Success feedback

- **WHEN** a response is sent successfully
- **THEN** the UI shows visual confirmation (highlight animation)
- **AND** the input widget is removed as the state transitions

#### Scenario: Error feedback

- **WHEN** a response send fails
- **THEN** the UI shows an error toast message
- **AND** the input widget remains available for retry

#### Scenario: No commander socket available

- **WHEN** an agent is in AWAITING_INPUT state
- **AND** no commander socket is available
- **THEN** no input widget is shown
- **AND** the card displays only the existing focus button and question text

#### Scenario: Agent without claude_session_id

- **WHEN** an agent is in AWAITING_INPUT state
- **AND** the agent has no `claude_session_id`
- **THEN** no input widget is shown

---

### Requirement: Commander Availability Broadcasting

The system SHALL check and broadcast commander socket availability for active agents.

#### Scenario: Availability check on session start

- **WHEN** an agent session starts
- **THEN** the system checks commander socket availability for that agent

#### Scenario: Periodic availability check

- **WHEN** the configured health check interval elapses
- **THEN** the system checks commander availability for all active agents with `claude_session_id`

#### Scenario: Availability change broadcast

- **WHEN** commander availability changes for an agent (available → unavailable or vice versa)
- **THEN** a `commander_availability` SSE event is broadcast
- **AND** the dashboard updates the input widget visibility without page refresh

---

### Requirement: Graceful Degradation

The system SHALL degrade gracefully when commander functionality is unavailable.

#### Scenario: No commander installed

- **WHEN** no claude-commander sockets exist for any agent
- **THEN** all agent cards behave exactly as they do today
- **AND** no errors are logged for missing sockets

#### Scenario: Race condition — prompt already passed

- **WHEN** a response is sent but Claude Code has already moved past the prompt
- **THEN** the text is delivered via the socket (input-only, no prompt awareness)
- **AND** the state transition reflects reality on the next hook event

