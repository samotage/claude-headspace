# summarisation Specification

## Purpose
TBD - created by archiving change e3-s2-turn-task-summarisation. Update Purpose after archive.
## Requirements
### Requirement: Turn Summarisation

Turn summarisation prompts SHALL use intent-specific templates with task instruction context.

#### Scenario: COMMAND intent turn

- **WHEN** a USER turn with COMMAND intent has non-empty text
- **THEN** the prompt SHALL summarise what the user is asking the agent to do

#### Scenario: QUESTION intent turn

- **WHEN** an AGENT turn with QUESTION intent has non-empty text
- **THEN** the prompt SHALL summarise what the agent is asking the user

#### Scenario: COMPLETION intent turn

- **WHEN** an AGENT turn with COMPLETION intent has non-empty text
- **THEN** the prompt SHALL summarise what the agent accomplished with task instruction as context

#### Scenario: PROGRESS intent turn

- **WHEN** an AGENT turn with PROGRESS intent has non-empty text
- **THEN** the prompt SHALL summarise what progress the agent has made

#### Scenario: ANSWER intent turn

- **WHEN** a USER turn with ANSWER intent has non-empty text
- **THEN** the prompt SHALL summarise what information the user provided

#### Scenario: END_OF_TASK intent turn

- **WHEN** a turn with END_OF_TASK intent has non-empty text
- **THEN** the prompt SHALL summarise the final outcome of the task

#### Scenario: Turn with task instruction context

- **WHEN** a turn is summarised and the parent task has a non-NULL instruction
- **THEN** the task instruction SHALL be included in the summarisation prompt as context

### Requirement: Task Summarisation

The task completion summary prompt SHALL be rebuilt to use instruction context instead of timestamps.

#### Scenario: Completion summary with full context

- **WHEN** a task transitions to COMPLETE and the final turn has non-empty text
- **THEN** the completion summary prompt SHALL receive the task instruction and the agent's final message text
- **AND** the prompt SHALL ask the LLM to describe what was accomplished relative to what was asked
- **AND** the result SHALL be 2-3 sentences
- **AND** timestamps and turn counts SHALL NOT be included as primary prompt content

#### Scenario: Completion summary stored with renamed field

- **WHEN** a completion summary is generated
- **THEN** it SHALL be stored in `task.completion_summary` with `task.completion_summary_generated_at`
- **AND** an SSE event SHALL be broadcast to update the agent card

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

### Requirement: Task Instruction Summarisation

The system SHALL generate a 1-2 sentence instruction summary from the initiating USER COMMAND turn when a task is created.

#### Scenario: Instruction generated on task creation from USER COMMAND

- **WHEN** a task is created from a USER COMMAND turn with non-empty text
- **THEN** instruction summarisation SHALL be triggered asynchronously
- **AND** the prompt SHALL receive the full text of the user's command
- **AND** the result SHALL be persisted to `task.instruction` and `task.instruction_generated_at`
- **AND** an `instruction_summary` SSE event SHALL be broadcast with task_id, instruction, agent_id, and project_id

#### Scenario: Instruction generation does not block hook pipeline

- **WHEN** instruction summarisation is triggered
- **THEN** it SHALL execute asynchronously via the thread pool
- **AND** the hook processing pipeline SHALL continue without waiting

#### Scenario: Task created with empty command text

- **WHEN** a task is created from a USER COMMAND turn with None or empty text
- **THEN** instruction summarisation SHALL NOT be triggered
- **AND** `task.instruction` SHALL remain NULL

---

### Requirement: Empty Text Guard

Turn and task summarisation SHALL be skipped when text content is unavailable.

#### Scenario: Turn with empty text

- **WHEN** a turn has None or empty text
- **THEN** turn summarisation SHALL be skipped and return None
- **AND** no summary SHALL be generated from metadata alone

#### Scenario: Completion summary deferred when final turn text empty

- **WHEN** a task transitions to COMPLETE but the final turn's text is None or empty
- **THEN** completion summarisation SHALL be deferred or skipped
- **AND** no summary SHALL be generated from metadata alone

---

### Requirement: Reference Rename

All codebase references to `task.summary` SHALL be updated to `task.completion_summary`.

#### Scenario: Field references updated across codebase

- **WHEN** the change is applied
- **THEN** all references to `task.summary` SHALL be updated to `task.completion_summary`
- **AND** all references to `task.summary_generated_at` SHALL be updated to `task.completion_summary_generated_at`
- **AND** this SHALL include models, services, routes, templates, static JS, and all test files

---

