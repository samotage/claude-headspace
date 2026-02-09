## ADDED Requirements

### Requirement: Voice Command API

The voice bridge SHALL provide an API endpoint for submitting commands to agents via voice.

#### Scenario: Command with explicit target agent

- **WHEN** a POST to `/api/voice/command` includes `agent_id` and `text`
- **THEN** the command SHALL be routed to the specified agent via tmux send-keys
- **AND** the response SHALL confirm delivery in voice-friendly format

#### Scenario: Command with auto-target (single awaiting agent)

- **WHEN** a POST to `/api/voice/command` includes `text` but no `agent_id`
- **AND** exactly one agent is in AWAITING_INPUT state
- **THEN** the command SHALL be auto-routed to that agent

#### Scenario: Command with no awaiting agents

- **WHEN** a POST to `/api/voice/command` is submitted
- **AND** no agents are in AWAITING_INPUT state
- **THEN** the response SHALL indicate no agents need input
- **AND** SHALL include a summary of what active agents are doing

#### Scenario: Command targeting non-awaiting agent

- **WHEN** a POST to `/api/voice/command` targets an agent not in AWAITING_INPUT state
- **THEN** the response SHALL include the agent's current state and a voice-friendly suggestion

---

### Requirement: Voice Session Listing

The voice bridge SHALL provide an endpoint listing all active agents in voice-friendly format.

#### Scenario: Multiple active agents

- **WHEN** a GET to `/api/voice/sessions` is made
- **THEN** the response SHALL include each active agent with: project name, state, awaiting input flag, current task summary, time since last activity
- **AND** the format SHALL be status line + key results + next action

#### Scenario: Verbosity parameter

- **WHEN** a GET to `/api/voice/sessions?verbosity=detailed` is made
- **THEN** the response SHALL include additional detail per agent (full task instruction, recent turns)

---

### Requirement: Voice Output Retrieval

The voice bridge SHALL provide an endpoint for recent agent output.

#### Scenario: Agent with completed tasks

- **WHEN** a GET to `/api/voice/agents/<agent_id>/output` is made
- **THEN** the response SHALL include the last N tasks with full_command and full_output
- **AND** the format SHALL be voice-friendly with configurable verbosity

---

### Requirement: Voice Question Detail

The voice bridge SHALL provide an endpoint for full question context.

#### Scenario: Structured question (AskUserQuestion)

- **WHEN** a GET to `/api/voice/agents/<agent_id>/question` is made
- **AND** the agent is in AWAITING_INPUT with a structured question
- **THEN** the response SHALL include question_text, numbered options with labels and descriptions, and question_source_type

#### Scenario: Free-text question

- **WHEN** a GET to `/api/voice/agents/<agent_id>/question` is made
- **AND** the agent is in AWAITING_INPUT with a free-text question
- **THEN** the response SHALL include the full question text
- **AND** SHALL indicate question_source_type=free_text (no options to select)

#### Scenario: Agent not awaiting input

- **WHEN** a GET to `/api/voice/agents/<agent_id>/question` is made
- **AND** the agent is NOT in AWAITING_INPUT state
- **THEN** the response SHALL indicate the agent is not waiting for input with its current state

---

### Requirement: Token-Based Authentication

All voice bridge API endpoints SHALL require token-based authentication.

#### Scenario: Valid token provided

- **WHEN** a request includes `Authorization: Bearer <valid_token>` header
- **THEN** the request SHALL be processed normally

#### Scenario: Missing or invalid token

- **WHEN** a request lacks a token or provides an invalid token
- **THEN** the response SHALL be 401 with a voice-friendly error message

#### Scenario: Localhost bypass enabled

- **WHEN** `voice_bridge.auth.localhost_bypass` is true
- **AND** the request originates from 127.0.0.1 or ::1
- **THEN** authentication SHALL be bypassed

---

### Requirement: Voice-Friendly Error Responses

All voice bridge error responses SHALL be formatted for voice consumption.

#### Scenario: Error response format

- **WHEN** any voice bridge endpoint returns an error
- **THEN** the response SHALL include: error type (short phrase), suggestion for resolution
- **AND** SHALL NOT include stack traces, HTTP status codes, or technical details in the response body

---

### Requirement: Access Logging

All voice bridge API requests SHALL be logged.

#### Scenario: Request logged

- **WHEN** any voice bridge API request is processed
- **THEN** a log entry SHALL be created with: timestamp, source IP, endpoint, target agent (if applicable), auth status, response latency

---

### Requirement: Network Binding Configuration

The server SHALL support configurable network binding for voice bridge access.

#### Scenario: LAN-accessible mode

- **WHEN** `voice_bridge.network.bind_address` is set to `0.0.0.0`
- **THEN** the Flask server SHALL bind to all network interfaces

#### Scenario: Localhost-only mode (default)

- **WHEN** `voice_bridge.network.bind_address` is not set or is `127.0.0.1`
- **THEN** the Flask server SHALL bind to localhost only

---

### Requirement: Voice Output Formatting

Voice API responses SHALL use a structured voice-friendly format.

#### Scenario: Standard response format

- **WHEN** any voice bridge endpoint returns a successful response
- **THEN** the response SHALL include: status_line (1 sentence), results (1-3 items), next_action (0-2 items or "none")

#### Scenario: Verbosity levels

- **WHEN** `verbosity=concise` (default)
- **THEN** responses SHALL be minimal, designed for listening
- **WHEN** `verbosity=normal`
- **THEN** responses SHALL include moderate detail
- **WHEN** `verbosity=detailed`
- **THEN** responses SHALL include full information

---

### Requirement: Turn Question Detail Storage

Turn records with intent=QUESTION SHALL store structured question detail.

#### Scenario: AskUserQuestion turn created

- **WHEN** a pre_tool_use hook fires for AskUserQuestion
- **THEN** the Turn record SHALL have `question_text`, `question_options` (JSONB), and `question_source_type` populated

#### Scenario: Free-text question turn created

- **WHEN** the intent_detector classifies agent output as QUESTION without AskUserQuestion
- **THEN** the Turn record SHALL have `question_text` populated and `question_options` SHALL be null

---

### Requirement: Answer-to-Question Linking

Turn records with intent=ANSWER SHALL reference the QUESTION turn they resolve.

#### Scenario: Answer turn created via respond

- **WHEN** an ANSWER turn is created (via dashboard respond or voice command)
- **THEN** `answered_by_turn_id` SHALL reference the most recent QUESTION turn in the same task
