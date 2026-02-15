# domain-models Specification

## Purpose
TBD - created by archiving change e1-s3-domain-models. Update Purpose after archive.
## Requirements
### Requirement: Objective Model

The system SHALL persist a global Objective with id, current_text (required), constraints (optional), and set_at timestamp.

#### Scenario: Create Objective
- **WHEN** a new Objective is created with current_text
- **THEN** the objective is persisted with auto-generated id and default set_at timestamp

#### Scenario: Objective without current_text
- **WHEN** an Objective is created without current_text
- **THEN** a validation error is raised

---

### Requirement: ObjectiveHistory Model

The system SHALL track objective history with objective_id FK, text, constraints, started_at, and ended_at (nullable for current).

#### Scenario: Track Objective Change
- **WHEN** an objective is updated
- **THEN** the previous ObjectiveHistory record has ended_at set
- **AND** a new ObjectiveHistory record is created with current values

---

### Requirement: Project Model

The system SHALL persist Projects with id, name, path (required), github_repo (nullable), current_branch (nullable), and created_at.

#### Scenario: Create Project
- **WHEN** a new Project is created with name and path
- **THEN** the project is persisted with auto-generated id and default created_at

---

### Requirement: Agent Model

The system SHALL persist Agents with id, session_uuid (UUID), project_id FK, iterm_pane_id (nullable), started_at, and last_seen_at.

#### Scenario: Create Agent
- **WHEN** a new Agent is created with session_uuid and project_id
- **THEN** the agent is persisted with FK relationship to Project

#### Scenario: Agent State Derivation
- **WHEN** Agent.state is accessed
- **THEN** it returns the current task's state, or IDLE if no active task

---

### Requirement: Task Model

The Task model SHALL include fields for instruction tracking and renamed completion summary.

#### Scenario: Task instruction field

- **WHEN** the migration is applied
- **THEN** the tasks table SHALL have a nullable `instruction` text field
- **AND** a nullable `instruction_generated_at` timestamp field

#### Scenario: Task completion summary field rename

- **WHEN** the migration is applied
- **THEN** the tasks table `summary` column SHALL be renamed to `completion_summary`
- **AND** the `summary_generated_at` column SHALL be renamed to `completion_summary_generated_at`
- **AND** existing data SHALL be preserved during the rename

#### Scenario: Backward compatibility with existing tasks

- **WHEN** a task exists from before this change with NULL `completion_summary` and NULL `instruction`
- **THEN** the task SHALL display without errors in the dashboard
- **AND** the agent card SHALL show appropriate fallback text

### Requirement: TaskState Enum

The TaskState enum SHALL contain exactly 5 values: idle, commanded, processing, awaiting_input, complete.

#### Scenario: Enum Values
- **WHEN** TaskState enum is queried for values
- **THEN** exactly 5 values are returned matching the specification

---

### Requirement: Turn Model

The system SHALL persist Turns with id, task_id FK, actor (2-value enum), intent (6-value enum), text, timestamp, timestamp_source (String(20), nullable, default="server"), and jsonl_entry_hash (String(64), nullable, indexed).

#### Scenario: Create Turn
- **WHEN** a Turn is created with task_id, actor="user", intent="command", text
- **THEN** the turn is persisted with FK relationship to Task
- **AND** `timestamp_source` defaults to "server"
- **AND** `jsonl_entry_hash` defaults to NULL

#### Scenario: Turn timestamp provenance tracking
- **WHEN** a Turn is created via a hook event
- **THEN** `timestamp_source` SHALL be "server" (datetime.now at creation time)
- **WHEN** the Turn's timestamp is corrected from JSONL data during reconciliation
- **THEN** `timestamp_source` SHALL be updated to "jsonl"
- **WHEN** a Turn is created from a user action (e.g., voice command, dashboard respond)
- **THEN** `timestamp_source` SHALL be "user"

#### Scenario: Turn JSONL deduplication hash
- **WHEN** a Turn is reconciled against a JSONL transcript entry
- **THEN** `jsonl_entry_hash` SHALL be set to a SHA-256 content hash of the actor and text
- **AND** the hash SHALL be used to prevent duplicate Turn creation during reconciliation

#### Scenario: Turn ordering
- **WHEN** turns are queried for display (e.g., transcript API, chat view)
- **THEN** turns SHALL be ordered by `(timestamp, id)` composite ordering instead of `id` alone

---

### Requirement: TurnActor Enum

The TurnActor enum SHALL contain exactly 2 values: user, agent.

#### Scenario: TurnActor Enum Values
- **WHEN** TurnActor enum is queried for values
- **THEN** exactly 2 values are returned: user, agent

---

### Requirement: TurnIntent Enum

The TurnIntent enum SHALL contain exactly 6 values: command, answer, question, completion, progress, end_of_task.

#### Scenario: TurnIntent Enum Values
- **WHEN** TurnIntent enum is queried for values
- **THEN** exactly 6 values are returned: command, answer, question, completion, progress, end_of_task

---

### Requirement: Event Model

The system SHALL persist Events with id, timestamp, project_id (nullable FK), agent_id (nullable FK), task_id (nullable FK), turn_id (nullable FK), event_type (string), and payload (JSON).

#### Scenario: Event with Partial FKs
- **WHEN** an Event is created with only project_id set
- **THEN** the event is persisted with other FKs as NULL

#### Scenario: Event on Entity Delete
- **WHEN** an Agent referenced by an Event is deleted
- **THEN** the Event.agent_id is SET NULL (not cascade deleted)

---

### Requirement: Relationship Constraints

The system SHALL enforce:
- Project has many Agents (one-to-many)
- Agent has many Tasks (one-to-many)
- Task has many Turns (one-to-many)
- Objective has many ObjectiveHistory records (one-to-many)

#### Scenario: FK Constraint Violation
- **WHEN** an Agent is created with invalid project_id
- **THEN** a foreign key constraint error is raised

---

### Requirement: Cascade Delete Behavior

The system SHALL cascade deletes: Project→Agents→Tasks→Turns.

#### Scenario: Project Delete Cascade
- **WHEN** a Project is deleted
- **THEN** all associated Agents, Tasks, and Turns are deleted

---

### Requirement: Database Indexes

The system SHALL create indexes for:
- agents.project_id, agents.session_uuid
- tasks.agent_id, tasks.state
- turns.task_id, turns.timestamp (individual), turns.(task_id, timestamp) (composite), turns.(task_id, actor) (composite), turns.jsonl_entry_hash
- events.timestamp, events.event_type, events.project_id, events.agent_id

#### Scenario: Query Performance
- **WHEN** querying agents by project_id
- **THEN** the query uses the index (verified via EXPLAIN)

---

### Requirement: Query Patterns

The system SHALL support these query patterns:
1. Get current (most recent incomplete) task for an agent
2. Get recent turns for a task ordered by timestamp
3. Get events filtered by project/agent/event_type

#### Scenario: Get Current Task
- **WHEN** Agent.get_current_task() is called
- **THEN** the most recent task with state != 'complete' is returned

#### Scenario: No Current Task
- **WHEN** Agent.get_current_task() is called on agent with no tasks
- **THEN** None is returned

