# Tasks: e1-s3-domain-models

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Enum Definitions
- [ ] 2.1.1 Create TaskState enum (idle, commanded, processing, awaiting_input, complete)
- [ ] 2.1.2 Create TurnActor enum (user, agent)
- [ ] 2.1.3 Create TurnIntent enum (command, answer, question, completion, progress)

### 2.2 Model Files
- [ ] 2.2.1 Create `src/claude_headspace/models/` directory structure
- [ ] 2.2.2 Create `models/__init__.py` with exports
- [ ] 2.2.3 Create `models/objective.py` - Objective and ObjectiveHistory models
- [ ] 2.2.4 Create `models/project.py` - Project model
- [ ] 2.2.5 Create `models/agent.py` - Agent model with state derived property
- [ ] 2.2.6 Create `models/task.py` - Task model with TaskState enum
- [ ] 2.2.7 Create `models/turn.py` - Turn model with TurnActor, TurnIntent enums
- [ ] 2.2.8 Create `models/event.py` - Event model with nullable FKs

### 2.3 Relationships & Constraints
- [ ] 2.3.1 Define foreign key relationships (Project→Agent→Task→Turn)
- [ ] 2.3.2 Define Objective→ObjectiveHistory relationship
- [ ] 2.3.3 Define Event nullable FK relationships
- [ ] 2.3.4 Implement cascade delete behavior (Project→Agent→Task→Turn)
- [ ] 2.3.5 Implement SET NULL on Event FK deletes

### 2.4 Database Indexes
- [ ] 2.4.1 Add index on agents.project_id
- [ ] 2.4.2 Add index on agents.session_uuid
- [ ] 2.4.3 Add index on tasks.agent_id
- [ ] 2.4.4 Add index on tasks.state
- [ ] 2.4.5 Add index on turns.task_id
- [ ] 2.4.6 Add index on events.timestamp
- [ ] 2.4.7 Add index on events.event_type
- [ ] 2.4.8 Add indexes on events.project_id, events.agent_id

### 2.5 Query Methods
- [ ] 2.5.1 Implement Agent.get_current_task() - most recent incomplete task
- [ ] 2.5.2 Implement Agent.state derived property
- [ ] 2.5.3 Implement Task.get_recent_turns() - ordered by timestamp

### 2.6 Migration
- [ ] 2.6.1 Generate migration with `flask db migrate`
- [ ] 2.6.2 Review and adjust migration file if needed
- [ ] 2.6.3 Run migration with `flask db upgrade`

## 3. Testing (Phase 3)

### 3.1 Unit Tests
- [ ] 3.1.1 Test all 7 models can be instantiated
- [ ] 3.1.2 Test enum validation rejects invalid values
- [ ] 3.1.3 Test complete object graph creation (Objective→Project→Agent→Task→Turn)
- [ ] 3.1.4 Test Event creation with various FK combinations

### 3.2 Relationship Tests
- [ ] 3.2.1 Test foreign key constraint enforcement
- [ ] 3.2.2 Test cascade delete (Project→Agent→Task→Turn)
- [ ] 3.2.3 Test SET NULL on Event FK deletes

### 3.3 Query Pattern Tests
- [ ] 3.3.1 Test Agent.get_current_task() returns correct task
- [ ] 3.3.2 Test Agent.state derived property
- [ ] 3.3.3 Test Task.get_recent_turns() ordering
- [ ] 3.3.4 Test Event filtering by project/agent/event_type

### 3.4 Migration Tests
- [ ] 3.4.1 Test migration runs cleanly (flask db upgrade)
- [ ] 3.4.2 Test migration is reversible (flask db downgrade)

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Migration runs without errors on clean database
- [ ] 4.4 Manual verification: create full object graph via Python shell
