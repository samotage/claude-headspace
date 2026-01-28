# Specification: e1-s3-domain-models

## ADDED Requirements

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

The system SHALL persist Tasks with id, agent_id FK, state (5-value enum), started_at, and completed_at (nullable).

#### Scenario: Valid Task State
- **WHEN** a Task is created with state = "processing"
- **THEN** the task is persisted with the valid enum value

#### Scenario: Invalid Task State
- **WHEN** a Task is created with state = "invalid_state"
- **THEN** a validation error is raised

---

### Requirement: TaskState Enum

The TaskState enum SHALL contain exactly 5 values: idle, commanded, processing, awaiting_input, complete.

#### Scenario: Enum Values
- **WHEN** TaskState enum is queried for values
- **THEN** exactly 5 values are returned matching the specification

---

### Requirement: Turn Model

The system SHALL persist Turns with id, task_id FK, actor (2-value enum), intent (5-value enum), text, and timestamp.

#### Scenario: Create Turn
- **WHEN** a Turn is created with task_id, actor="user", intent="command", text
- **THEN** the turn is persisted with FK relationship to Task

---

### Requirement: TurnActor Enum

The TurnActor enum SHALL contain exactly 2 values: user, agent.

#### Scenario: TurnActor Enum Values
- **WHEN** TurnActor enum is queried for values
- **THEN** exactly 2 values are returned: user, agent

---

### Requirement: TurnIntent Enum

The TurnIntent enum SHALL contain exactly 5 values: command, answer, question, completion, progress.

#### Scenario: TurnIntent Enum Values
- **WHEN** TurnIntent enum is queried for values
- **THEN** exactly 5 values are returned: command, answer, question, completion, progress

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
- turns.task_id
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
