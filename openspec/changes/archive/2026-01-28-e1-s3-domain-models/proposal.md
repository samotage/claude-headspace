# Proposal: e1-s3-domain-models

## Why

Claude Headspace needs a foundational data layer to persist Agents, Commands, Turns, and Events with a 5-state lifecycle model. Without these core domain models, the system cannot track Claude Code sessions or support the real-time dashboard.

## What Changes

- Add `Objective` model with current_text, constraints, and set_at timestamp
- Add `ObjectiveHistory` model for tracking objective changes over time
- Add `Project` model with name, path, github_repo, current_branch
- Add `Agent` model with session_uuid (UUID), project FK, iterm_pane_id, timestamps
- Add `Task` model with agent FK, 5-state enum (idle/commanded/processing/awaiting_input/complete)
- Add `Turn` model with task FK, actor enum (user/agent), intent enum, text, timestamp
- Add `Event` model with nullable FKs, event_type string, JSON payload
- Create database migrations via Flask-Migrate
- Define enums: CommandState, TurnActor, TurnIntent
- Implement Agent.state derived property (from current command)
- Add database indexes for common query patterns

## Impact

### Affected Specs
- Database schema (new tables: objectives, objective_histories, projects, agents, tasks, turns, events)
- SQLAlchemy model layer

### Affected Code
- `src/claude_headspace/models/__init__.py` (new - export all models)
- `src/claude_headspace/models/objective.py` (new - Objective, ObjectiveHistory)
- `src/claude_headspace/models/project.py` (new - Project)
- `src/claude_headspace/models/agent.py` (new - Agent)
- `src/claude_headspace/models/command.py` (new - Command, CommandState enum)
- `src/claude_headspace/models/turn.py` (new - Turn, TurnActor, TurnIntent enums)
- `src/claude_headspace/models/event.py` (new - Event)
- `migrations/versions/` (new migration file)

### Dependencies
- Sprint 2 (Database Setup) must be complete - PostgreSQL configured, SQLAlchemy integrated

### Blocking
This change blocks:
- Sprint 4 (File Watcher) - needs Event model
- Sprint 5 (Event System) - needs all models
- Sprint 6 (State Machine) - needs Command, Turn models
- Sprint 9 (Objective Tab) - needs Objective model
