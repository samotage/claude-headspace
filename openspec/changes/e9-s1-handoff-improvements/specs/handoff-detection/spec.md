## ADDED Requirements

### Requirement: Handoff Detection on Agent Creation

When a new agent is created and assigned a persona, the `HandoffDetectionService` SHALL scan `data/personas/{slug}/handoffs/` for existing `.md` files and emit a `synthetic_turn` SSE event with the most recent 3 handoffs.

#### Scenario: Handoff files exist

- **WHEN** a new agent is created with a persona
- **AND** the persona's handoff directory contains `.md` files
- **THEN** the system SHALL sort files by filename (reverse chronological) and select the most recent 3
- **AND** a `synthetic_turn` SSE event SHALL be emitted with filenames and absolute file paths

#### Scenario: No handoff directory

- **WHEN** a new agent is created with a persona
- **AND** the persona's handoff directory does not exist
- **THEN** no `synthetic_turn` event SHALL be emitted

#### Scenario: Empty handoff directory

- **WHEN** a new agent is created with a persona
- **AND** the persona's handoff directory is empty
- **THEN** no `synthetic_turn` event SHALL be emitted

#### Scenario: Agent without persona

- **WHEN** a new agent is created without a persona
- **THEN** no handoff detection SHALL occur

#### Scenario: HandoffExecutor-created successor

- **WHEN** a new agent is created by HandoffExecutor (previous_agent_id set)
- **THEN** the synthetic turn listing SHALL still be emitted

### Requirement: Synthetic Turn SSE Event

The system SHALL emit a `synthetic_turn` SSE event type via the existing broadcaster for dashboard-only informational turns.

#### Scenario: Event payload structure

- **WHEN** a `synthetic_turn` event is emitted for handoff listing
- **THEN** the event data SHALL include `agent_id`, `persona_slug`, and a `turns` array containing `type`, `filenames`, and `file_paths`

#### Scenario: Agent isolation

- **WHEN** a `synthetic_turn` event is emitted
- **THEN** the event SHALL NOT be delivered to the agent via tmux, hook response, or any other mechanism

### Requirement: Service Registration

`HandoffDetectionService` SHALL be registered as `app.extensions["handoff_detection_service"]` following the existing service registration pattern in `app.py`.

#### Scenario: Service available at runtime

- **WHEN** the Flask app is initialized
- **THEN** `app.extensions["handoff_detection_service"]` SHALL be a `HandoffDetectionService` instance
