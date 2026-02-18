---
title: 'Rename Task Model to Command'
slug: 'rename-task-to-command'
created: '2026-02-18'
status: 'in-progress'
stepsCompleted: [1]
tech_stack:
  - Python 3.10+ / Flask 3.0+
  - PostgreSQL / SQLAlchemy / Alembic
  - Vanilla JS / Tailwind CSS 3.x
  - Jinja2 templates
  - SSE (Server-Sent Events)
files_to_modify: []
code_patterns: []
test_patterns: []
---

# Tech Spec: Rename Task Model to Command

## Overview

### Problem Statement

The `Task` domain model name conflicts with the next project phase where "task" will take on a different meaning. The current model represents commands issued to Claude Code agents — its states (IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE) and lifecycle are fundamentally about commands, not tasks in the broader sense.

### Solution

Complete cross-cutting rename of every domain-model reference from "task" → "command" across the entire codebase: database schema, Python models/services/routes, SSE wire format, JavaScript frontend, voice chat UI, CSS, help documentation, architecture docs, OpenSpec specs, CLAUDE.md, and all tests. Staged in dependency order with a single reversible Alembic migration.

### In Scope

- **DB migration:** Table `tasks` → `commands`, FK columns `task_id` → `command_id`, enum values (`END_OF_TASK` → `END_OF_COMMAND`, `InferenceLevel.TASK` → `COMMAND`)
- **Models (5 files):** `task.py` → `command.py`, `Task` → `Command`, `TaskState` → `CommandState`, FK/relationship refs in agent, turn, event, inference_call, `__init__.py`
- **Services (22 files):** `task_lifecycle.py` → `command_lifecycle.py`, `TaskLifecycleManager` → `CommandLifecycleManager`, all method names, `app.extensions` keys, prompt templates
- **Routes (6 files):** API URLs (`/api/tasks/` → `/api/commands/`, `/api/agents/<id>/tasks` → `/api/agents/<id>/commands`), template context vars
- **Templates (4 files):** `_kanban_task_card.html` → `_kanban_command_card.html`, all template variables
- **Dashboard JS (5 files):** SSE event names (`task_summary` → `command_summary`), DOM selectors, data attributes
- **Voice Chat UI (5 files):** CSS classes, HTML IDs, JS references (`.chat-task-*` → `.chat-command-*`)
- **CSS (2 files):** `input.css` classes, then rebuild `main.css`
- **Help docs (7 files):** User-facing documentation in `docs/help/`
- **Architecture/conceptual docs (~10 files):** `docs/architecture/`, `docs/diagrams/`, `docs/conceptual/`
- **OpenSpec (~97 files):** Specs and archived changes referencing task model
- **PRDs (~30 files):** Historical PRDs referencing Task model
- **CLAUDE.md:** Project guide (Task States, model table, service descriptions)
- **Tests (51 files):** File renames, factory class, all assertions
- **Notification events:** `task_complete` → `command_complete`
- **Prompt registry:** All LLM prompt templates referencing "task"

### Out of Scope

- Non-domain uses of "task" (Python async tasks, generic English, external tooling)
- Rewriting old Alembic migration files (historical records)
- `vendor/` files (e.g. `marked.min.js`)

## Context for Development

### Key Decisions

- **Full consistency:** All enums renamed (`TurnIntent.END_OF_TASK` → `END_OF_COMMAND`, `InferenceLevel.TASK` → `COMMAND`)
- **SSE events renamed:** Wire format changes in lockstep with JS (`task_summary` → `command_summary`, `task_complete` → `command_complete`)
- **Old migrations untouched:** Only a new migration performs the rename; existing migrations are historical records
- **Domain-only rename:** Generic/non-domain uses of "task" are NOT renamed

### Technical Constraints

- Database migration must be safe and reversible (ALTER TABLE RENAME, not DROP/CREATE)
- PostgreSQL enum values require ALTER TYPE ... RENAME VALUE
- SSE contract changes require lockstep Python + JS deploy
- Flask debug reloader handles most Python changes, but migration requires `flask db upgrade`
- Tailwind CSS rebuild required after `input.css` changes
