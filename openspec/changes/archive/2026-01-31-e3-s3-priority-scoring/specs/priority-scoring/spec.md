## ADDED Requirements

### Requirement: Batch Priority Scoring Service

The system SHALL provide a priority scoring service that evaluates all active agents in a single batch inference call and assigns each a score (0-100) with a human-readable reason.

#### Scenario: Successful batch scoring with objective

- **WHEN** batch scoring is triggered and an objective is set
- **THEN** the system SHALL gather all active agents (ended_at IS NULL, last_seen within timeout)
- **AND** the system SHALL build a scoring prompt including the objective text, constraints, and each agent's metadata (project name, state, command summary, task duration, waypoint next-up items)
- **AND** the system SHALL make a single inference call at the "objective" level via the E3-S1 inference service
- **AND** the LLM response SHALL be parsed as structured JSON: `[{"agent_id": N, "score": N, "reason": "..."}]`
- **AND** each agent's `priority_score`, `priority_reason`, and `priority_updated_at` SHALL be persisted to the database

#### Scenario: Scoring with waypoint fallback (no objective)

- **WHEN** batch scoring is triggered and no objective is set but projects have waypoints
- **THEN** the scoring prompt SHALL use project waypoint Next Up and Upcoming sections as the primary alignment context
- **AND** each agent SHALL receive a score and reason based on waypoint alignment

#### Scenario: Default scoring (no context)

- **WHEN** batch scoring is triggered with no objective and no waypoints available
- **THEN** each agent SHALL receive a default score of 50
- **AND** each agent SHALL receive the reason "No scoring context available"
- **AND** no inference call SHALL be made

#### Scenario: Zero active agents

- **WHEN** batch scoring is triggered with no active agents
- **THEN** scoring SHALL be a no-op and return an empty result

#### Scenario: Single active agent

- **WHEN** batch scoring is triggered with exactly one active agent
- **THEN** the system SHALL still run the inference call and provide a score and reason for that agent

---

### Requirement: Scoring Factors

The scoring evaluation SHALL consider multiple factors with objective/waypoint alignment as the dominant factor.

#### Scenario: Multi-factor scoring

- **WHEN** the scoring prompt is constructed
- **THEN** the prompt SHALL instruct the LLM to consider: objective/waypoint alignment (40%), agent state (25%), task duration (15%), project context (10%), and recent activity (10%)
- **AND** agent state weights SHALL follow: awaiting_input (highest urgency) > processing > idle (lowest urgency)

---

### Requirement: Rate-Limited Scoring Triggers

Scoring triggers SHALL be rate-limited to prevent redundant inference calls during rapid state changes.

#### Scenario: State change triggers debounced scoring

- **WHEN** a command state change occurs on any agent
- **THEN** the system SHALL schedule a re-score of all active agents with a 5-second debounce delay
- **AND** multiple rapid state changes within the 5-second window SHALL consolidate into a single scoring call

#### Scenario: Objective change triggers immediate scoring

- **WHEN** the objective is changed
- **THEN** the system SHALL bypass the debounce and trigger an immediate re-score of all active agents
- **AND** any pending debounced scoring SHALL be cancelled

#### Scenario: Thread-safe debounce

- **WHEN** scoring triggers arrive from multiple concurrent sources
- **THEN** the debounce mechanism SHALL be thread-safe and handle concurrent access without race conditions

---

### Requirement: Priority Score Storage

The Agent model SHALL be extended with fields for priority scoring data.

#### Scenario: Agent model extended

- **WHEN** the migration is applied
- **THEN** the agents table SHALL have a nullable `priority_score` integer field (0-100)
- **AND** a nullable `priority_reason` text field
- **AND** a nullable `priority_updated_at` datetime (timezone-aware) field

#### Scenario: Score persistence

- **WHEN** scoring completes successfully
- **THEN** each scored agent's `priority_score`, `priority_reason`, and `priority_updated_at` SHALL be persisted to the database
- **AND** scores SHALL be preserved across page reloads

---

### Requirement: Priority API Endpoints

The system SHALL expose API endpoints for triggering scoring and querying rankings.

#### Scenario: Trigger batch scoring

- **WHEN** POST `/api/priority/score` is requested
- **THEN** the system SHALL trigger batch priority scoring of all active agents
- **AND** the response SHALL include the scores, reasons, and context type used

#### Scenario: Query current rankings

- **WHEN** GET `/api/priority/rankings` is requested
- **THEN** the response SHALL return all agents ordered by priority score descending
- **AND** each agent entry SHALL include agent_id, project_name, state, score, reason, and scored_at

#### Scenario: Inference service unavailable

- **WHEN** the inference service is unavailable during a scoring request
- **THEN** the API SHALL return a 503 error response
- **AND** existing persisted scores SHALL be preserved unchanged

#### Scenario: No active agents

- **WHEN** POST `/api/priority/score` is requested with no active agents
- **THEN** the response SHALL return 200 with an empty agents list

---

### Requirement: Malformed Response Handling

The system SHALL handle malformed LLM responses gracefully.

#### Scenario: Invalid JSON response

- **WHEN** the LLM returns non-JSON or malformed JSON
- **THEN** the error SHALL be logged
- **AND** existing persisted scores SHALL be preserved unchanged
- **AND** no scores SHALL be cleared or zeroed

#### Scenario: Invalid score values

- **WHEN** the LLM returns scores outside the 0-100 range
- **THEN** scores SHALL be clamped to the valid range (0-100)

---

### Requirement: Non-blocking Scoring

Event-triggered scoring SHALL not block the Flask request/response cycle or SSE delivery.

#### Scenario: Async event-triggered scoring

- **WHEN** scoring is triggered by a state change event
- **THEN** the scoring SHALL execute asynchronously in a background thread with Flask app context
- **AND** the event processing SHALL continue without waiting for scoring to complete

#### Scenario: SSE broadcast on score update

- **WHEN** scoring completes successfully
- **THEN** a `priority_update` SSE event SHALL be broadcast with the updated scores
- **AND** the dashboard SHALL reflect the new scores via the existing SSE real-time update mechanism

---

## MODIFIED Requirements

### Requirement: Dashboard Priority Display

The dashboard agent cards and recommended next panel SHALL display real LLM-generated priority scores.

#### Scenario: Agent card priority badge

- **WHEN** an agent has a priority_score in the database
- **THEN** the agent card SHALL display the real score as the priority badge value
- **AND** the priority reason SHALL be accessible on the agent card

#### Scenario: Agent without score

- **WHEN** an agent has no priority_score (NULL)
- **THEN** the agent card SHALL display a default priority of 50

#### Scenario: Recommended next uses priority

- **WHEN** no agents are in AWAITING_INPUT state
- **THEN** the recommended next panel SHALL display the agent with the highest priority_score
- **AND** the rationale SHALL include the priority score and reason

#### Scenario: Priority-based sorting

- **WHEN** agents are displayed in the priority view
- **THEN** agents SHALL be sorted by priority_score descending (highest first)
- **AND** agents with equal scores SHALL be sorted by state group then last_seen_at
