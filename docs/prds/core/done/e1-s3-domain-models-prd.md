---
validation:
  status: valid
  validated_at: '2026-01-29T09:23:27+11:00'
---

# Product Requirements Document (PRD) — Domain Models

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 3 — Core domain models and database schema
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace requires a foundational data layer to track Claude Code sessions (Agents) working on Tasks with Turn-level granularity. This PRD defines the core domain models that enable the 5-state Task/Turn state machine—the primary differentiator of Claude Headspace from simple process monitoring.

The domain models provide the data foundation that all subsequent sprints depend upon: file watcher (Sprint 4), event system (Sprint 5), state machine (Sprint 6), and the dashboard UI (Sprint 8). Without these models, there is no way to persist agents, tasks, turns, or events.

This sprint delivers 7 SQLAlchemy models with proper relationships, enum constraints, and database migrations. The models are purely data layer—business logic (state transitions, intent detection) is deferred to Sprint 6.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace monitors multiple Claude Code sessions across projects, tracking their state in real-time. The system needs to persist:

- **Objectives** that guide prioritisation across all projects
- **Projects** auto-discovered from the filesystem
- **Agents** representing individual Claude Code sessions
- **Tasks** representing units of work with a 5-state lifecycle
- **Turns** representing individual exchanges (user ↔ agent)
- **Events** providing an audit trail of all system activity

The 5-state task model (idle → commanded → processing → awaiting_input → complete) enables the dashboard to show exactly when an agent needs user input vs. when it's actively working.

### 1.2 Target User

Developers using Claude Code across multiple projects who need visibility into agent state and prioritisation guidance.

### 1.3 Success Moment

A developer can query the database to see all active agents, their current task states, and recent turns—providing the data foundation for the real-time dashboard.

---

## 2. Scope

### 2.1 In Scope

- `Objective` model with current text, constraints, and `set_at` timestamp
- `ObjectiveHistory` model (separate table) tracking objective changes over time
- `Project` model with name, path, github_repo, current_branch
- `Agent` model with session_uuid, project_id (FK), iterm_pane_id, started_at, last_seen_at
- `Task` model with agent_id (FK), 5-state enum, started_at, completed_at
- `Turn` model with task_id (FK), actor enum, intent enum, text, timestamp
- `Event` model with nullable FKs, event_type, JSON payload, timestamp
- Database migrations for all models via Flask-Migrate
- Foreign key relationships and constraints
- Enum definitions for TaskState, TurnActor, TurnIntent
- Derived property for Agent.state (from current task)
- Basic query patterns (current task for agent, recent turns for task)

### 2.2 Out of Scope

- State machine transition logic (Sprint 6)
- File watcher / jsonl parsing (Sprint 4)
- Event writer service (Sprint 5)
- API endpoints for CRUD operations (future sprints)
- Intent detection logic (Sprint 6)
- SSE broadcasting (Sprint 7)
- Dashboard UI (Sprint 8)
- Auto-discovery logic for Projects/Agents (Sprint 4)
- Inference call tracking model (Epic 3)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. All 7 models can be instantiated via SQLAlchemy ORM
2. Database migrations run cleanly (`flask db upgrade`) with no errors
3. Foreign key relationships are enforced at the database level
4. Enum fields reject invalid values (e.g., invalid TaskState raises error)
5. Can create complete object graph: Objective → Project → Agent → Task → Turn, plus Events
6. Query patterns work correctly:
   - Get current (most recent incomplete) task for an agent
   - Get recent turns for a task ordered by timestamp
   - Get events filtered by project/agent/event_type
7. ObjectiveHistory records are created when objective changes (started_at/ended_at tracked)

### 3.2 Non-Functional Success Criteria

1. Models follow existing codebase patterns (integrate with app factory)
2. All enum values are documented and match conceptual design
3. Nullable fields are explicitly marked (Event FKs)
4. Cascade delete behavior is defined and tested
5. Models include appropriate indexes for common query patterns

---

## 4. Functional Requirements (FRs)

### FR1: Objective Model

The system shall persist a global Objective with:
- `id`: Primary key
- `current_text`: The current objective text (required)
- `constraints`: Optional constraints text
- `set_at`: Timestamp when the objective was set

### FR2: ObjectiveHistory Model

The system shall track objective history in a separate table with:
- `id`: Primary key
- `objective_id`: Foreign key to Objective
- `text`: The objective text at that time
- `constraints`: The constraints at that time
- `started_at`: When this objective became active
- `ended_at`: When this objective was replaced (nullable for current)

### FR3: Project Model

The system shall persist Projects with:
- `id`: Primary key
- `name`: Project display name (derived from path or git)
- `path`: Absolute filesystem path to project
- `github_repo`: GitHub repository URL (nullable)
- `current_branch`: Current git branch (nullable)
- `created_at`: Timestamp when project was discovered

### FR4: Agent Model

The system shall persist Agents with:
- `id`: Primary key
- `session_uuid`: Unique session identifier (UUID format)
- `project_id`: Foreign key to Project
- `iterm_pane_id`: iTerm2 pane identifier for AppleScript focus (nullable)
- `started_at`: Timestamp when session started
- `last_seen_at`: Timestamp of last activity
- Derived property `state`: Returns current task's state, or `idle` if no active task

### FR5: Task Model

The system shall persist Tasks with:
- `id`: Primary key
- `agent_id`: Foreign key to Agent
- `state`: Enum constrained to exactly 5 values:
  - `idle`
  - `commanded`
  - `processing`
  - `awaiting_input`
  - `complete`
- `started_at`: Timestamp when task started
- `completed_at`: Timestamp when task completed (nullable)

### FR6: Turn Model

The system shall persist Turns with:
- `id`: Primary key
- `task_id`: Foreign key to Task
- `actor`: Enum constrained to exactly 2 values:
  - `user`
  - `agent`
- `intent`: Enum constrained to exactly 5 values:
  - `command`
  - `answer`
  - `question`
  - `completion`
  - `progress`
- `text`: The content of the turn
- `timestamp`: When the turn occurred

### FR7: Event Model

The system shall persist Events with:
- `id`: Primary key
- `timestamp`: When the event occurred
- `project_id`: Foreign key to Project (nullable)
- `agent_id`: Foreign key to Agent (nullable)
- `task_id`: Foreign key to Task (nullable)
- `turn_id`: Foreign key to Turn (nullable)
- `event_type`: String identifying the event type
- `payload`: JSON field for event-specific data

### FR8: Event Type Taxonomy

The system shall support the following event types:
- `session_discovered`: New Claude Code session detected
- `session_ended`: Claude Code session terminated
- `turn_detected`: New turn parsed from jsonl
- `state_transition`: Task state changed
- `hook_received`: Event received from Claude Code hook
- `objective_changed`: Objective was updated

### FR9: Relationship Constraints

The system shall enforce the following relationships:
- Project has many Agents (one-to-many)
- Agent has many Tasks (one-to-many)
- Task has many Turns (one-to-many)
- Objective has many ObjectiveHistory records (one-to-many)
- Event references are nullable (events may occur at any level)

### FR10: Cascade Behavior

The system shall implement the following cascade behavior:
- Project delete → cascades to Agents
- Agent delete → cascades to Tasks
- Task delete → cascades to Turns
- Event foreign keys → SET NULL on referenced entity delete (preserve audit trail)

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Database Indexes

The system shall create indexes for common query patterns:
- `agents.project_id` — for querying agents by project
- `agents.session_uuid` — for looking up agent by session
- `tasks.agent_id` — for querying tasks by agent
- `tasks.state` — for filtering tasks by state
- `turns.task_id` — for querying turns by task
- `events.timestamp` — for time-range queries
- `events.event_type` — for filtering by event type
- `events.project_id`, `events.agent_id` — for filtering by entity

### NFR2: Enum Validation

All enum fields shall validate at both:
- Python/SQLAlchemy level (type checking)
- Database level (CHECK constraint or native ENUM type)

### NFR3: Timestamp Defaults

- `created_at` fields shall default to current UTC timestamp
- `timestamp` fields shall default to current UTC timestamp
- `set_at` fields shall default to current UTC timestamp

### NFR4: UUID Format

- `session_uuid` shall be stored as UUID type (not string)
- UUID generation is handled by the caller (launcher script)

---

## 6. Technical Context

*Note: This section captures architectural decisions for implementation reference.*

### Technology Choices

- **ORM:** SQLAlchemy (integrated with Flask)
- **Migrations:** Flask-Migrate (Alembic wrapper)
- **Database:** PostgreSQL (as established in Sprint 2)

### File Structure

```
src/claude_headspace/
├── models/
│   ├── __init__.py      # Export all models
│   ├── objective.py     # Objective, ObjectiveHistory
│   ├── project.py       # Project
│   ├── agent.py         # Agent
│   ├── task.py          # Task, TaskState enum
│   ├── turn.py          # Turn, TurnActor, TurnIntent enums
│   └── event.py         # Event
```

### Enum Definitions

```python
class TaskState(enum.Enum):
    IDLE = "idle"
    COMMANDED = "commanded"
    PROCESSING = "processing"
    AWAITING_INPUT = "awaiting_input"
    COMPLETE = "complete"

class TurnActor(enum.Enum):
    USER = "user"
    AGENT = "agent"

class TurnIntent(enum.Enum):
    COMMAND = "command"
    ANSWER = "answer"
    QUESTION = "question"
    COMPLETION = "completion"
    PROGRESS = "progress"
```

### Agent State Derivation

```python
@property
def state(self) -> TaskState:
    """Derive agent state from current task."""
    current_task = self.get_current_task()
    if current_task is None:
        return TaskState.IDLE
    return current_task.state
```

---

## 7. Dependencies

### Prerequisites

- Sprint 2 (Database Setup) must be complete:
  - PostgreSQL connection configured
  - SQLAlchemy integrated with Flask app
  - Flask-Migrate initialized

### Blocking

This sprint blocks:
- Sprint 4 (File Watcher) — needs Event model
- Sprint 5 (Event System) — needs all models
- Sprint 6 (State Machine) — needs Task, Turn models
- Sprint 9 (Objective Tab) — needs Objective model

---

## 8. Open Questions

*None — all questions resolved during workshop.*

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
