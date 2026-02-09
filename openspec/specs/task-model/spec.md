# task-model Specification

## Purpose
TBD - created by archiving change e5-s9-full-command-output-capture. Update Purpose after archive.
## Requirements
### Requirement: Full Command Capture

The Task model SHALL have a `full_command` field (Text, nullable) to store the complete user command text.

#### Scenario: User submits a command that creates a new task

- **WHEN** `TaskLifecycleManager.process_turn()` creates a new task from a USER COMMAND turn
- **THEN** the complete `text` parameter SHALL be persisted to `task.full_command`

#### Scenario: User submits an empty or null command

- **WHEN** the command text is None or empty
- **THEN** `task.full_command` SHALL remain NULL

### Requirement: Full Output Capture

The Task model SHALL have a `full_output` field (Text, nullable) to store the complete agent final message text.

#### Scenario: Task completes with agent text

- **WHEN** `TaskLifecycleManager.complete_task()` is called with a non-empty `agent_text` parameter
- **THEN** the complete `agent_text` SHALL be persisted to `task.full_output`

#### Scenario: Task completes without agent text

- **WHEN** `complete_task()` is called with empty or no `agent_text`
- **THEN** `task.full_output` SHALL remain NULL

### Requirement: On-demand Full Text API

The system SHALL provide a `GET /api/tasks/<task_id>/full-text` endpoint that returns `full_command` and `full_output` fields.

#### Scenario: Task exists with full text data

- **WHEN** a GET request is made to `/api/tasks/<task_id>/full-text` for a task with stored full text
- **THEN** the response SHALL be `200 OK` with `{ "full_command": "...", "full_output": "..." }`

#### Scenario: Task not found

- **WHEN** a GET request is made to `/api/tasks/<task_id>/full-text` for a non-existent task ID
- **THEN** the response SHALL be `404 Not Found`

### Requirement: Full Text Exclusion from SSE

Full text fields SHALL NOT be included in SSE `card_refresh` event payloads or in the `/api/agents/<id>/tasks` endpoint response.

#### Scenario: Card refresh broadcast

- **WHEN** `broadcast_card_refresh()` builds the card state dictionary
- **THEN** the dictionary SHALL NOT contain `full_command` or `full_output` keys

#### Scenario: Agent tasks API response

- **WHEN** `GET /api/agents/<id>/tasks` is called
- **THEN** the response SHALL NOT include `full_command` or `full_output` fields

### Requirement: Dashboard Drill-down UI

The dashboard agent card SHALL display drill-down buttons for the instruction line (03) and completion summary line (04) that open a scrollable modal displaying the full stored text.

#### Scenario: User clicks drill-down on instruction

- **WHEN** the user clicks the "View full" button on the instruction line of an agent card
- **THEN** the system SHALL fetch `/api/tasks/<id>/full-text` and display `full_command` in a scrollable modal

#### Scenario: User clicks drill-down on completion summary

- **WHEN** the user clicks the "View full" button on the completion summary line of an agent card
- **THEN** the system SHALL fetch `/api/tasks/<id>/full-text` and display `full_output` in a scrollable modal

#### Scenario: Full text not available

- **WHEN** the drill-down is clicked but the task has no stored full text (null fields)
- **THEN** the modal SHALL display a "No full text available" message

### Requirement: Project View Transcript Display

The project view agent chat transcript SHALL display the full agent output for completed tasks in an expandable section.

#### Scenario: Completed task with full output in transcript

- **WHEN** a completed task is rendered in the project view transcript
- **THEN** an expandable section SHALL be available to view the full output

#### Scenario: Expand full output in transcript

- **WHEN** the user expands the full output section for a task
- **THEN** the system SHALL fetch `/api/tasks/<id>/full-text` on demand and display `full_output`

### Requirement: Mobile-Friendly Display

The full text modal and project view transcript expansion SHALL be scrollable and readable on mobile viewports (minimum 320px width).

#### Scenario: Full text on mobile viewport

- **WHEN** the full text modal is displayed on a viewport of 320px width
- **THEN** text SHALL wrap naturally, be legible, and the modal SHALL be dismissible

