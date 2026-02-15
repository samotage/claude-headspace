# voice-bridge Specification

## Purpose
TBD - created by archiving change e6-s1-voice-bridge-server. Update Purpose after archive.
## Requirements
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

### Requirement: Agent Chat Transcript

The voice bridge transcript endpoint SHALL return an agent-lifetime conversation history with cursor-based pagination and real-time intermediate message capture.

#### Scenario: Agent with multiple completed tasks

- **WHEN** a GET to `/api/voice/agents/<agent_id>/transcript` is made
- **THEN** the response SHALL include turns from ALL tasks for that agent
- **AND** turns SHALL be ordered chronologically by `(timestamp, id)` composite ordering
- **AND** each turn SHALL include `task_id`, `task_instruction`, `task_state`, `turn_id`, and `timestamp`

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
- **AND** the turn SHALL be linked to the agent's current task

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

---

### Requirement: Voice Command Turn Broadcasting

When voice commands or file uploads create Turn records, the system SHALL broadcast SSE `turn_created` events.

#### Scenario: Voice command creates turn with SSE broadcast

- **WHEN** a POST to `/api/voice/command` successfully creates a Turn record
- **THEN** a `turn_created` SSE event SHALL be broadcast with `agent_id`, `project_id`, `text`, `actor`, `intent`, `task_id`, `turn_id`, and `timestamp`

#### Scenario: File upload creates turn with SSE broadcast

- **WHEN** a POST to `/api/voice/agents/<agent_id>/upload` successfully creates a Turn record
- **THEN** a `turn_created` SSE event SHALL be broadcast with the same fields as voice command turns

---

### Requirement: Three-Phase Event Pipeline

The voice bridge transcript system SHALL use a three-phase event pipeline for turn ordering.

#### Scenario: Phase 1 — Hook event creates Turn

- **WHEN** a Claude Code hook event fires (e.g., stop, user-prompt-submit)
- **THEN** a Turn is created with `timestamp=now()` and `timestamp_source="server"`
- **AND** a `turn_created` SSE event is broadcast immediately

#### Scenario: Phase 2 — JSONL reconciliation corrects timestamps

- **WHEN** the file watcher reads new JSONL entries
- **THEN** the TranscriptReconciler matches entries to existing Turns via content hash
- **AND** corrects Turn timestamps to JSONL values and sets `timestamp_source="jsonl"`
- **AND** creates missing Turns not captured by hooks

#### Scenario: Phase 3 — SSE corrections for reordering

- **WHEN** the reconciler updates Turn timestamps or creates new Turns
- **THEN** `turn_updated` SSE events are broadcast for timestamp corrections
- **AND** `turn_created` SSE events are broadcast for newly discovered Turns
- **AND** the client reorders chat bubbles based on the corrected timestamps

