# Proposal Summary: e1-s3-domain-models

## Architecture Decisions
- Use SQLAlchemy ORM with Flask integration (follows existing project pattern from Sprint 2)
- Models organized in `src/claude_headspace/models/` directory with separate files per domain concept
- PostgreSQL native ENUM types for CommandState, TurnActor, TurnIntent (database-level validation)
- Derived Agent.state property computed from current command (no denormalization)
- Event foreign keys are nullable with SET NULL on delete (preserves audit trail)

## Implementation Approach
- Create 7 SQLAlchemy models in dedicated files following the file structure from PRD Section 6
- Define enums as Python Enum classes that map to PostgreSQL ENUM types
- Use Flask-Migrate (Alembic) for database migrations
- Implement cascade delete at the ORM level for Project→Agent→Task→Turn chain
- Add indexes during migration for query performance

## Files to Modify
### Models (new files)
- `src/claude_headspace/models/__init__.py` - Export all models
- `src/claude_headspace/models/objective.py` - Objective, ObjectiveHistory
- `src/claude_headspace/models/project.py` - Project
- `src/claude_headspace/models/agent.py` - Agent with state property
- `src/claude_headspace/models/command.py` - Command, CommandState enum
- `src/claude_headspace/models/turn.py` - Turn, TurnActor, TurnIntent enums
- `src/claude_headspace/models/event.py` - Event

### Migrations
- `migrations/versions/` - New migration file for all tables

## Acceptance Criteria
1. All 7 models can be instantiated via SQLAlchemy ORM
2. Database migrations run cleanly (`flask db upgrade`) with no errors
3. Foreign key relationships enforced at database level
4. Enum fields reject invalid values
5. Complete object graph creation works: Objective → Project → Agent → Command → Turn
6. Query patterns work:
   - Agent.get_current_command() returns most recent incomplete command
   - Task.get_recent_turns() returns turns ordered by timestamp
   - Events filterable by project/agent/event_type
7. ObjectiveHistory tracks changes with started_at/ended_at

## Constraints and Gotchas
- Sprint 2 (Database Setup) must be complete - PostgreSQL configured, SQLAlchemy integrated
- UUID type for session_uuid (not string) - caller generates UUIDs
- Timestamp fields default to UTC (not local time)
- This sprint is purely data layer - no state machine logic (Sprint 6)
- No API endpoints - just models and migrations
- Event FKs use SET NULL on delete (not cascade) to preserve audit trail

## Git Change History

### Related Files
Based on git context analysis:
- **Config:** Project has config files in `_bmad/_config/`, `_bmad/core/`
- **Models:** No existing models directory (this is the first data layer sprint)
- **Tests:** No existing test files (tests will be new)

### OpenSpec History
- No previous OpenSpec changes for this subsystem (first implementation)

### Implementation Patterns
- Project follows Flask application factory pattern
- Database integration established in Sprint 2 (e1-s2-database-setup)
- Recent commit (197b7daa) completed database setup

## Q&A History
- No clarifications needed - PRD was complete and unambiguous
- All open questions resolved during PRD workshop

## Dependencies
### Required packages (already installed from Sprint 2)
- Flask-SQLAlchemy
- Flask-Migrate
- psycopg2-binary

### External services
- PostgreSQL database (configured in Sprint 2)

### Database migrations needed
- Single migration creating all 7 tables with:
  - ENUM types for CommandState, TurnActor, TurnIntent
  - Foreign key constraints
  - Indexes on query columns

## Testing Strategy
### Unit Tests
- Test each model instantiation
- Test enum validation (reject invalid values)
- Test complete object graph creation

### Integration Tests
- Test FK constraints at database level
- Test cascade delete behavior
- Test SET NULL on Event FK deletes

### Query Pattern Tests
- Test Agent.get_current_command()
- Test Agent.state derived property
- Test Turn ordering by timestamp
- Test Event filtering

### Migration Tests
- Test `flask db upgrade` runs cleanly
- Test `flask db downgrade` is reversible

## OpenSpec References
- proposal.md: openspec/changes/e1-s3-domain-models/proposal.md
- tasks.md: openspec/changes/e1-s3-domain-models/tasks.md
- spec.md: openspec/changes/e1-s3-domain-models/specs/domain-models/spec.md
