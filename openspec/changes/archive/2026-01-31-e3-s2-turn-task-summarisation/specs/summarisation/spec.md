## ADDED Requirements

### Requirement: Turn Summarisation

The system SHALL automatically generate a 1-2 sentence summary for each turn when it is recorded by the TaskLifecycleManager.

#### Scenario: Successful turn summarisation

- **WHEN** a new turn is recorded with text, actor, and intent
- **THEN** the system SHALL generate a concise 1-2 sentence summary via the inference service at "turn" level
- **AND** the summary SHALL be stored in the Turn model's summary field with a generation timestamp
- **AND** an SSE event SHALL be broadcast to update the agent card on the dashboard

#### Scenario: Turn with cached content

- **WHEN** a turn's content matches a previously summarised turn (same input hash)
- **THEN** the cached summary SHALL be returned without making a new inference call

#### Scenario: Inference service unavailable for turn

- **WHEN** the inference service is unavailable during turn summarisation
- **THEN** the summary field SHALL remain null
- **AND** the dashboard SHALL display the original raw turn text without error

---

### Requirement: Task Summarisation

The system SHALL automatically generate a 2-3 sentence summary when a task transitions to the complete state.

#### Scenario: Successful task summarisation

- **WHEN** a task transitions to complete state
- **THEN** the system SHALL generate a 2-3 sentence outcome summary via the inference service at "task" level
- **AND** the summary SHALL include context from task timestamps, turn count, and final turn content
- **AND** the summary SHALL be stored in the Task model's summary field with a generation timestamp
- **AND** an SSE event SHALL be broadcast to update the agent card

#### Scenario: Inference service unavailable for task

- **WHEN** the inference service is unavailable during task summarisation
- **THEN** the summary field SHALL remain null
- **AND** the dashboard SHALL display the task state without a summary

---

### Requirement: Summarisation API Endpoints

The system SHALL expose manual summarisation endpoints for turns and tasks.

#### Scenario: Manual turn summarisation

- **WHEN** POST `/api/summarise/turn/<id>` is requested for a turn that exists
- **THEN** the response SHALL include the generated summary
- **AND** if the turn already has a summary, the existing summary SHALL be returned without re-generating

#### Scenario: Manual task summarisation

- **WHEN** POST `/api/summarise/task/<id>` is requested for a task that exists
- **THEN** the response SHALL include the generated summary
- **AND** if the task already has a summary, the existing summary SHALL be returned without re-generating

#### Scenario: Entity not found

- **WHEN** the specified turn or task does not exist
- **THEN** the endpoint SHALL return a 404 error response

#### Scenario: Inference service unavailable

- **WHEN** the inference service is unavailable
- **THEN** the endpoint SHALL return a 503 error response

---

### Requirement: Asynchronous Processing

Summarisation SHALL execute without blocking the turn processing pipeline or SSE event delivery.

#### Scenario: Non-blocking summarisation

- **WHEN** summarisation is triggered by turn creation or task completion
- **THEN** the summarisation SHALL execute asynchronously
- **AND** SSE updates SHALL continue uninterrupted during inference

#### Scenario: Placeholder display

- **WHEN** summarisation is in-flight
- **THEN** the dashboard SHALL display a "Summarising..." placeholder on the relevant agent card
- **AND** the placeholder SHALL be replaced by the summary when inference completes

---

### Requirement: Summary Data Model

The Turn and Task models SHALL be extended with summary fields.

#### Scenario: Turn model extended

- **WHEN** the migration is applied
- **THEN** the turns table SHALL have a nullable `summary` text field and a nullable `summary_generated_at` timestamp field

#### Scenario: Task model extended

- **WHEN** the migration is applied
- **THEN** the tasks table SHALL have a nullable `summary` text field and a nullable `summary_generated_at` timestamp field

---

### Requirement: Inference Integration

All summarisation inference calls SHALL use the E3-S1 inference service with correct metadata.

#### Scenario: Turn inference call logging

- **WHEN** a turn summarisation inference call is made
- **THEN** the InferenceCall record SHALL include level="turn", purpose="summarise_turn", and the correct turn_id, task_id, agent_id, and project_id associations

#### Scenario: Task inference call logging

- **WHEN** a task summarisation inference call is made
- **THEN** the InferenceCall record SHALL include level="task", purpose="summarise_task", and the correct task_id, agent_id, and project_id associations

---

### Requirement: Error Handling

Summarisation errors SHALL be logged without retrying or disrupting the system.

#### Scenario: Failed summarisation call

- **WHEN** a summarisation inference call fails
- **THEN** the summary field SHALL remain null
- **AND** the error SHALL be logged via the E3-S1 InferenceCall system
- **AND** no automatic retry SHALL be attempted
