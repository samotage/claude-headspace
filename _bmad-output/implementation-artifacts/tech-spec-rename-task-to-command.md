---
title: 'Rename Task Model to Command'
slug: 'rename-task-to-command'
created: '2026-02-18'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack:
  - Python 3.10+ / Flask 3.0+
  - PostgreSQL / SQLAlchemy 3.1+ / Alembic (Flask-Migrate)
  - Vanilla JS / Tailwind CSS 3.x
  - Jinja2 templates
  - SSE (Server-Sent Events)
  - pytest + factory-boy (tests)
files_to_modify:
  # --- App Factory + Config (2 files) ---
  - src/claude_headspace/app.py
  - src/claude_headspace/config.py
  # --- Models (6 files, 1 rename) ---
  - src/claude_headspace/models/task.py          # RENAME → command.py
  - src/claude_headspace/models/agent.py
  - src/claude_headspace/models/turn.py
  - src/claude_headspace/models/event.py
  - src/claude_headspace/models/inference_call.py
  - src/claude_headspace/models/__init__.py
  # --- Services (23 files, 1 rename) ---
  - src/claude_headspace/services/task_lifecycle.py  # RENAME → command_lifecycle.py
  - src/claude_headspace/services/state_machine.py
  - src/claude_headspace/services/hook_receiver.py
  - src/claude_headspace/services/hook_deferred_stop.py
  - src/claude_headspace/services/hook_extractors.py
  - src/claude_headspace/services/card_state.py
  - src/claude_headspace/services/summarisation_service.py
  - src/claude_headspace/services/prompt_registry.py
  - src/claude_headspace/services/event_schemas.py
  - src/claude_headspace/services/__init__.py
  - src/claude_headspace/services/intent_detector.py
  - src/claude_headspace/services/inference_service.py
  - src/claude_headspace/services/notification_service.py
  - src/claude_headspace/services/priority_scoring.py
  - src/claude_headspace/services/activity_aggregator.py
  - src/claude_headspace/services/agent_reaper.py
  - src/claude_headspace/services/transcript_reconciler.py
  - src/claude_headspace/services/voice_formatter.py
  - src/claude_headspace/services/team_content_detector.py
  - src/claude_headspace/services/tmux_watchdog.py
  - src/claude_headspace/services/agent_lifecycle.py
  - src/claude_headspace/services/config_editor.py
  - src/claude_headspace/services/event_writer.py
  # --- Routes (8 files) ---
  - src/claude_headspace/routes/dashboard.py
  - src/claude_headspace/routes/projects.py
  - src/claude_headspace/routes/respond.py
  - src/claude_headspace/routes/hooks.py
  - src/claude_headspace/routes/summarisation.py
  - src/claude_headspace/routes/voice_bridge.py
  - src/claude_headspace/routes/notifications.py
  # --- Templates (4 files, 1 rename) ---
  - templates/dashboard.html
  - templates/partials/_agent_card.html
  - templates/partials/_kanban_task_card.html  # RENAME → _kanban_command_card.html
  - templates/partials/_kanban_view.html
  # --- JavaScript (7 files) ---
  - static/js/dashboard-sse.js
  - static/js/sse-client.js
  - static/js/agent-info.js
  - static/js/project_show.js
  - static/js/logging-inference.js
  - static/js/card-tooltip.js
  - static/js/full-text-modal.js
  # --- Voice Chat (6 files) ---
  - static/voice/voice-sse-handler.js
  - static/voice/voice-chat-controller.js
  - static/voice/voice-chat-renderer.js
  - static/voice/voice-state.js
  - static/voice/voice-sidebar.js
  - static/voice/voice.html
  # --- CSS (2 files + rebuild) ---
  - static/voice/voice.css
  - static/css/src/input.css
  # --- Migration (1 new file) ---
  - migrations/versions/xxxx_rename_task_to_command.py  # NEW
  # --- Tests (51 files, 3 renames) ---
  - tests/integration/factories.py
  - tests/services/test_task_lifecycle.py             # RENAME → test_command_lifecycle.py
  - tests/services/test_task_lifecycle_summarisation.py  # RENAME → test_command_lifecycle_summarisation.py
  - tests/routes/test_task_full_text.py               # RENAME → test_command_full_text.py
  - tests/test_models.py
  - tests/integration/test_factories.py
  # ... plus 45 more test files (see Tests section)
  # --- Root Files ---
  - config.example.yaml                # openrouter.models.task → command
  - README.md                          # Task model documentation
  - brain_reboot/waypoint.md           # Minor task reference
  # --- Documentation ---
  - CLAUDE.md
  - ~/.claude/CLAUDE.md  # User's global instructions (TASK COMPLETE → COMMAND COMPLETE)
  - docs/application/claude_code_setup_prompt.md  # Setup prompt that installs the completion signal
  - docs/help/*.md (7 files)
  - docs/architecture/*.md (~10 files)
  - docs/conceptual/*.md
  - docs/diagrams/*.md
  - docs/beads/*.md
  - docs/bugs/*.md
  - docs/ideas/*.md (~3 files)
  - docs/investigations/*.md
  - docs/reviews_remediation/*.md (~8 files)
  - docs/roadmap/*.md (~8 files)
  - docs/sprints/*.md (~4 files)
  - docs/testing/*.md (~2 files)
  - docs/workshop/*.md (~7 files)
  - docs/prompts/*.md
  - openspec/specs/task-model/spec.md  # RENAME dir → command-model/
  - openspec/specs/*.md (~34 files)
  - openspec/changes/archive/**/*.md (~97 files)
  - docs/prds/**/*.md (~30 files)
code_patterns:
  - 'Flask app factory with service injection via app.extensions'
  - 'SQLAlchemy ORM with Alembic migrations'
  - 'Service classes instantiated directly (not via app.extensions for TaskLifecycleManager)'
  - 'SSE broadcasting via Broadcaster service'
  - 'Jinja2 templates with context dict from routes'
  - 'Vanilla JS consuming SSE events by type name'
  - 'PostgreSQL native enums (CREATE TYPE) for state/intent; InferenceLevel is varchar NOT a PG enum'
test_patterns:
  - 'pytest with conftest.py fixture injection (app, client, db_session)'
  - 'factory-boy for integration tests (TaskFactory → CommandFactory)'
  - 'MagicMock for service unit tests (mock_task → mock_command)'
  - 'Autouse _force_test_database fixture enforces _test DB'
  - 'No task refs in root conftest.py (clean)'
---

# Tech Spec: Rename Task Model to Command

## Overview

### Problem Statement

The `Task` domain model name conflicts with the next project phase where "task" will take on a different meaning. The current model represents commands issued to Claude Code agents — its states (IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE) and lifecycle are fundamentally about commands, not tasks in the broader sense.

### Solution

Complete cross-cutting rename of every domain-model reference from "task" → "command" across the entire codebase: database schema, Python models/services/routes, SSE wire format, JavaScript frontend, voice chat UI, CSS, help documentation, architecture docs, OpenSpec specs, CLAUDE.md, and all tests. Staged in dependency order with a single reversible Alembic migration.

### In Scope

- **DB migration:** Table `tasks` → `commands`, FK columns `task_id` → `command_id`, enum values, index names, check constraints
- **Models (6 files):** `task.py` → `command.py`, `Task` → `Command`, `TaskState` → `CommandState`, FK/relationship refs in agent, turn, event, inference_call, `__init__.py`
- **Services (23 files):** `task_lifecycle.py` → `command_lifecycle.py`, `TaskLifecycleManager` → `CommandLifecycleManager`, all method names, prompt templates; `event_writer.py` (task_id parameter)
- **Routes (8 files):** API URLs (including `/api/summarise/task/<id>` → `/api/summarise/command/<id>`) (`/api/tasks/` → `/api/commands/`, `/api/agents/<id>/tasks` → `/api/agents/<id>/commands`), template context vars
- **App factory + config (2 files):** `app.py` + `config.py` — notification event defaults, model level keys
- **Templates (4 files):** `_kanban_task_card.html` → `_kanban_command_card.html`, all template variables
- **Dashboard JS (7 files):** SSE event names (`task_summary` → `command_summary`), DOM selectors, data attributes, API URLs
- **Voice Chat UI (6 files):** CSS classes, HTML IDs, JS references (`.chat-task-*` → `.chat-command-*`), voice-sidebar.js
- **CSS (2 files):** `input.css` + `voice.css` classes, then rebuild `main.css`
- **Help docs (7 files):** User-facing documentation in `docs/help/`
- **Architecture/conceptual docs (~10 files):** `docs/architecture/`, `docs/diagrams/`, `docs/conceptual/`
- **Additional docs (~40 files):** `docs/beads/`, `docs/bugs/`, `docs/ideas/`, `docs/investigations/`, `docs/reviews_remediation/`, `docs/roadmap/`, `docs/sprints/`, `docs/testing/`, `docs/workshop/`, `docs/prompts/`
- **OpenSpec (~97+ files):** Specs (including `task-model/` dir rename → `command-model/`), archived change docs
- **PRDs (~30 files):** Historical PRDs referencing Task model
- **Root files:** `config.example.yaml`, `README.md`, `brain_reboot/waypoint.md`
- **CLAUDE.md:** Project guide (Task States, model table, service descriptions)
- **Tests (~50 unique files, some overlap between categories):** 3 file renames, factory class rename, all assertions/fixtures
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
- **TaskLifecycleManager is NOT an app.extension:** It's instantiated directly via constructor in `hook_receiver.py`, `hook_deferred_stop.py`, `agent_reaper.py`, and `voice_bridge.py`. The `transcript_reconciler.py` reference to `current_app.extensions.get("task_lifecycle")` is dead code.

### Technical Constraints

- Database migration must be safe and reversible (ALTER TABLE RENAME, not DROP/CREATE)
- PostgreSQL enum values require `ALTER TYPE ... RENAME VALUE` (for actual PG enums: `taskstate`, `turnintent`)
- **`InferenceLevel` is NOT a PostgreSQL enum** — it's a Python `str, enum.Enum` with a `String(20)` (varchar) column. Migration uses `UPDATE` statement, not `ALTER TYPE`
- PostgreSQL enum type name `taskstate` → `commandstate` requires recreation (PG doesn't support `ALTER TYPE RENAME`)
- SSE contract changes require lockstep Python + JS deploy
- Flask debug reloader handles most Python changes, but migration requires `flask db upgrade`
- Tailwind CSS rebuild required after `input.css` changes

### Critical DO NOT CHANGE List

These use "task" but are NOT domain-model references:

1. **`<task-notification>` XML tag** (hook_receiver.py lines ~764, ~769, ~1379) — literal XML tag injected by Claude Code. All three occurrences must be preserved.
2. **`TurnIntent.COMMAND`** — this is a turn intent enum value, not the Command model
3. **Old migration file contents** — historical records, untouched
4. **Generic English** — "background tasks", non-domain prose

### Marker String Change: "TASK COMPLETE" → "COMMAND COMPLETE"

The `"TASK COMPLETE"` marker string in `intent_detector.py` (line ~71) is the completion signal output by Claude Code agents. It IS renamed to `"COMMAND COMPLETE"` as part of this refactor. This requires coordinated changes:
- `intent_detector.py`: Update regex pattern
- Project `CLAUDE.md`: Update Task Completion Signal section
- User's global `~/.claude/CLAUDE.md`: Update Task Completion Signal section
- `docs/application/claude_code_setup_prompt.md`: Update Step 8 (installs the completion signal for new users)
- `test_intent_detector.py`: Update test assertions

### Database Migration Details

The new Alembic migration must handle:

1. **Rename table:** `ALTER TABLE tasks RENAME TO commands`
2. **Rename FK columns:**
   - `turns.task_id` → `turns.command_id`
   - `events.task_id` → `events.command_id`
   - `inference_calls.task_id` → `inference_calls.command_id`
3. **Rename enum type:** `ALTER TYPE taskstate RENAME TO commandstate` (PG supports `ALTER TYPE ... RENAME TO` for the type name itself)
4. **Rename enum value:** `ALTER TYPE turnintent RENAME VALUE 'end_of_task' TO 'end_of_command'` (PG 10+ supports this)
5. **Update InferenceLevel values:** `UPDATE inference_calls SET level = 'command' WHERE level = 'task'` — NOTE: `InferenceLevel` is a Python-only `str, enum.Enum`; the DB column `inference_calls.level` is `String(20)` (varchar), NOT a PostgreSQL enum type. There is no `inferencelevel` PG type to alter.
6. **Rename check constraint:** `ck_inference_calls_has_parent` references `task_id` → `command_id`
7. **Rename indexes:**
   - `ix_tasks_agent_id` → `ix_commands_agent_id`
   - `ix_tasks_agent_id_state` → `ix_commands_agent_id_state`
   - `ix_tasks_state` → `ix_commands_state`
   - `ix_turns_task_id` → `ix_turns_command_id`
   - `ix_turns_task_id_timestamp` → `ix_turns_command_id_timestamp`
   - `ix_turns_task_id_actor` → `ix_turns_command_id_actor`
8. **Rename sequence:** `ALTER SEQUENCE tasks_id_seq RENAME TO commands_id_seq`
9. **Rename PK constraint:** `ALTER INDEX tasks_pkey RENAME TO commands_pkey`
10. **Rename FK constraints:** `ALTER TABLE turns RENAME CONSTRAINT turns_task_id_fkey TO turns_command_id_fkey` (+ same pattern for events, inference_calls FK constraints referencing `commands.id`)
11. **Rename additional indexes:** `ix_events_task_id` → `ix_events_command_id`, `ix_inference_calls_task_id` → `ix_inference_calls_command_id` (if they exist — verify with `\di` before migration)

### Test File Inventory

**File Renames (3):**
- `tests/services/test_task_lifecycle.py` → `test_command_lifecycle.py`
- `tests/services/test_task_lifecycle_summarisation.py` → `test_command_lifecycle_summarisation.py`
- `tests/routes/test_task_full_text.py` → `test_command_full_text.py`

**Files with Direct Task/TaskState Imports (21):**
tests/services/test_state_machine.py, test_task_lifecycle.py, test_transcript_reconciler.py, test_turn_reliability.py, test_hook_receiver.py, test_card_state.py, test_full_command_output.py, test_task_lifecycle_summarisation.py, test_intent_detector.py, test_summarisation_service.py, test_notification_service.py, test_priority_scoring.py, test_inference_service.py, test_inference_gating.py, test_brain_reboot.py; tests/routes/test_voice_bridge.py, test_respond.py, test_dashboard.py, test_dashboard_interactivity.py, test_task_full_text.py; tests/test_models.py

**Files with TaskFactory Usage (8):**
tests/integration/factories.py, test_factories.py, test_model_constraints.py, test_summary_persistence.py, test_cross_service_flow.py, test_respond_flow.py, test_persistence_flow.py, test_inference_call.py

**Files with Indirect Task Refs (22):**
tests/services/test_agent_reaper.py, test_team_content_detector.py, test_voice_formatter.py, test_voice_auth.py, test_config_editor.py, test_activity_aggregator.py, test_prompt_registry.py, test_summarisation_frustration.py, test_progress_summary.py; tests/routes/test_voice_bridge_upload.py, test_voice_bridge_client.py, test_projects.py, test_inference.py, test_summarisation.py, test_project_show_tree.py, test_agents.py; tests/e2e/test_voice_app_baseline.py, test_debounce.py, test_edge_cases.py, test_multi_agent.py, test_turn_lifecycle.py, test_voice_chat_ordering.py; tests/e2e/helpers/dashboard_assertions.py

---

## Implementation Plan

### Execution Strategy

All code changes happen first (Tasks 1-18), then the migration runs and the server restarts (Task 19), then full validation (Task 20). The application will be offline between when code changes start and when the migration completes. This is a feature branch — no partial deploy occurs.

### Task Sequence

- [ ] **Task 1: Write Alembic Migration File (DO NOT RUN)**
  - File: `migrations/versions/xxxx_rename_task_to_command.py` (NEW)
  - Action: Generate migration with `flask db migrate -m "rename task to command"`, then hand-edit the generated file to perform all 8 operations from the Database Migration Details section. Use raw `op.execute()` for SQL that Alembic can't auto-detect (enum type rename, enum value rename, check constraint update).
  - Specific operations in `upgrade()`:
    1. `op.rename_table('tasks', 'commands')`
    2. `op.alter_column('turns', 'task_id', new_column_name='command_id')` (+ same for events, inference_calls)
    3. Enum type `taskstate` → `commandstate`: Execute `ALTER TYPE taskstate RENAME TO commandstate` — **CORRECTION**: PostgreSQL DOES support `ALTER TYPE ... RENAME TO` for the type name itself (just not for the type's schema). Use this instead of DROP/CREATE.
    4. `op.execute("ALTER TYPE turnintent RENAME VALUE 'end_of_task' TO 'end_of_command'")`
    5. `op.execute("UPDATE inference_calls SET level = 'command' WHERE level = 'task'")` — InferenceLevel is varchar, NOT a PG enum
    6. Drop and recreate `ck_inference_calls_has_parent` constraint with `command_id` replacing `task_id`
    7. Rename all indexes (6+ renames) using `op.execute("ALTER INDEX old_name RENAME TO new_name")` — includes `ix_events_task_id` → `ix_events_command_id`, `ix_inference_calls_task_id` → `ix_inference_calls_command_id` (verify existence with `\di` first)
    8. Rename sequence: `op.execute("ALTER SEQUENCE tasks_id_seq RENAME TO commands_id_seq")`
    9. Rename PK constraint: `op.execute("ALTER INDEX tasks_pkey RENAME TO commands_pkey")`
    10. Rename FK constraints: `op.execute("ALTER TABLE turns RENAME CONSTRAINT turns_task_id_fkey TO turns_command_id_fkey")` (+ events, inference_calls FK constraints)
  - `downgrade()` — specific reverse operations (reverse order of upgrade):
    1. Rename FK constraints back: `ALTER TABLE turns RENAME CONSTRAINT turns_command_id_fkey TO turns_task_id_fkey` (+ events, inference_calls)
    2. Rename PK constraint back: `ALTER INDEX commands_pkey RENAME TO tasks_pkey`
    3. Rename sequence back: `ALTER SEQUENCE commands_id_seq RENAME TO tasks_id_seq`
    4. Rename all indexes back (8+ renames): `ALTER INDEX ix_commands_* RENAME TO ix_tasks_*`, `ix_events_command_id` → `ix_events_task_id`, etc.
    5. Drop and recreate `ck_inference_calls_has_parent` constraint with `task_id`
    6. `op.execute("UPDATE inference_calls SET level = 'task' WHERE level = 'command'")` — InferenceLevel is varchar
    7. `op.execute("ALTER TYPE turnintent RENAME VALUE 'end_of_command' TO 'end_of_task'")`
    8. `op.execute("ALTER TYPE commandstate RENAME TO taskstate")`
    9. Rename FK columns back: `op.alter_column('turns', 'command_id', new_column_name='task_id')` (+ events, inference_calls)
    10. `op.rename_table('commands', 'tasks')`
  - Notes: Do NOT run `flask db upgrade` yet. The migration file is staged for Task 19.

- [ ] **Task 2: Rename and Update Core Model File**
  - File: `src/claude_headspace/models/task.py` → RENAME to `command.py`
  - Action: `git mv models/task.py models/command.py`, then inside the file:
    - Class `Task` → `Command`
    - Class `TaskState` → `CommandState`
    - `__tablename__ = "tasks"` → `__tablename__ = "commands"`
    - Enum type name `name="taskstate"` → `name="commandstate"`
    - Docstrings: "Task" → "Command", "unit of work" → "unit of work commanded to an agent"
    - `get_recent_turns()` method — update import `from .turn import Turn` (unchanged), but method docstring references "task" → "command"
    - Index: `Index("ix_tasks_agent_id_state", ...)` → `Index("ix_commands_agent_id_state", ...)`
    - `__repr__`: `<Task ...>` → `<Command ...>`

- [ ] **Task 3: Update Models Package and Related Models**
  - Files:
    - `src/claude_headspace/models/__init__.py`
    - `src/claude_headspace/models/agent.py`
    - `src/claude_headspace/models/turn.py`
    - `src/claude_headspace/models/event.py`
    - `src/claude_headspace/models/inference_call.py`
  - Action per file:
    - **`__init__.py`**: Change `from .task import Task, TaskState` → `from .command import Command, CommandState`. Update `__all__` list. Update module docstring.
    - **`agent.py`**: Relationship `tasks` → `commands` (including `order_by` referencing `Task.started_at` → `Command.started_at`). Method `get_current_task()` → `get_current_command()`. Property `state` — update internal variable names. Import `Task` → `Command`, `TaskState` → `CommandState`. All type hints `"Task"` → `"Command"`.
    - **`turn.py`**: Column `task_id` → `command_id` (FK target `commands.id`). Relationship `task` → `command`. `TurnIntent.END_OF_TASK` → `END_OF_COMMAND` (value `"end_of_task"` → `"end_of_command"`). Composite indexes: `ix_turns_task_id_timestamp` → `ix_turns_command_id_timestamp`, `ix_turns_task_id_actor` → `ix_turns_command_id_actor`. Type hints `"Task"` → `"Command"`.
    - **`event.py`**: Column `task_id` → `command_id` (FK target `commands.id` with SET NULL). Relationship if any.
    - **`inference_call.py`**: Column `task_id` → `command_id` (FK target `commands.id`). `InferenceLevel.TASK` → `InferenceLevel.COMMAND` (value `"task"` → `"command"`). Check constraint `ck_inference_calls_has_parent` — update the COALESCE expression from `task_id` → `command_id`. Relationship `task` → `command` if present.

- [ ] **Task 4: Rename and Update Core Service — CommandLifecycleManager**
  - Files:
    - `src/claude_headspace/services/task_lifecycle.py` → RENAME to `command_lifecycle.py`
    - `src/claude_headspace/services/state_machine.py`
    - `src/claude_headspace/services/__init__.py`
  - Action per file:
    - **`task_lifecycle.py` → `command_lifecycle.py`**: `git mv`. Class `TaskLifecycleManager` → `CommandLifecycleManager`. All method names: `create_task()` → `create_command()`, `complete_task()` → `complete_command()`, `get_current_task()` → `get_current_command()`, `update_task_state()` → `update_command_state()`, `_ensure_task()` → `_ensure_command()`, etc. All internal variable names `current_task` → `current_command`, `new_task` → `new_command`. All imports from `models.task` → `models.command`. Logging messages. Docstrings. Free function `get_instruction_for_notification` — rename parameter `task` → `command` if applicable.
    - **HIGH-RISK dataclass: `SummarisationRequest`**: Field `.task` → `.command`. **CRITICAL**: The string literal `type="task_completion"` (lines ~26, ~339) must change to `"command_completion"`. This string is a contract with `summarisation_service.py` (which checks `req.type == "task_completion"` at line ~531) and `prompt_registry.py` (template keys `task_completion`, `task_completion_from_activity`, `task_completion_from_instruction`). All three must change in lockstep or summarisation silently breaks. **NOTE**: The existing `.command_text` field stays as-is — after rename there will be both `.command` (the Command object) and `.command_text` (the raw text string). This naming overlap is acknowledged but not blocking.
    - **HIGH-RISK dataclass: `TurnProcessingResult`**: Field `.task` → `.command` AND field `.new_task_created` → `.new_command_created` (line 42, used at lines 418, 465, 506). Both fields are accessed extensively: `result.task`, `result.task.state`, `result.task.id`, `result.task.instruction`, `result.task.turns` — at least **15+ access points in `hook_receiver.py`** and **8+ in `voice_bridge.py`**. `result.new_task_created` is checked in `hook_receiver.py` for conditional logic. A missed rename causes `AttributeError` at runtime. After completing the rename, verify with: `grep -n "\.task\b\|new_task" command_lifecycle.py hook_receiver.py voice_bridge.py | grep -v "DO NOT"`.
    - **`state_machine.py`**: All `TaskState` refs → `CommandState`. Import path change. Variable names in transition table. Docstrings.
    - **`__init__.py`**: Change `from .task_lifecycle import TaskLifecycleManager, TurnProcessingResult, get_instruction_for_notification` → `from .command_lifecycle import CommandLifecycleManager, TurnProcessingResult, get_instruction_for_notification`. Update `__all__`. Comment `# Task lifecycle` → `# Command lifecycle`.

- [ ] **Task 5: Update Hook Services**
  - Files:
    - `src/claude_headspace/services/hook_receiver.py` (~1600 lines, 200+ refs)
    - `src/claude_headspace/services/hook_deferred_stop.py`
    - `src/claude_headspace/services/hook_extractors.py`
  - Action per file:
    - **`hook_receiver.py`**: Change all imports from `task_lifecycle` → `command_lifecycle`, `TaskLifecycleManager` → `CommandLifecycleManager`, `SummarisationRequest` import path. Change ~200+ `current_task` variable refs → `current_command`. Change method calls: `.create_task()` → `.create_command()`, `.complete_task()` → `.complete_command()`, `.get_current_task()` → `.get_current_command()`, `.process_turn()` stays (it's a turn method). Change `Task` and `TaskState` imports → `Command`, `CommandState`. Change all `task.id` → `command.id`, `task.state` → `command.state`, `task.instruction` → `command.instruction`. **DO NOT CHANGE** `<task-notification>` XML tag literals (lines ~764, ~769, ~1379 — three occurrences total). Change SSE broadcast keys: `task_id` → `command_id`, `task_summary` → `command_summary`, `task_instruction` → `command_instruction`, `task_completion_summary` → `command_completion_summary`. Change `TurnIntent.END_OF_TASK` → `TurnIntent.END_OF_COMMAND`. Rename constant `INFERRED_TASK_COOLDOWN_SECONDS` → `INFERRED_COMMAND_COOLDOWN_SECONDS` (line 82 and usage at line 1536). Update comments at lines 80-81 ("Don't infer a new task" → "Don't infer a new command"). Change log message `"inferred PROCESSING task_id="` → `"inferred PROCESSING command_id="` (line 1590).
    - **`hook_deferred_stop.py`**: Change `from .task_lifecycle import TaskLifecycleManager` → `from .command_lifecycle import CommandLifecycleManager`. Change `from .task_lifecycle import get_instruction_for_notification` → `from .command_lifecycle import ...`. Change all variable names and method calls.
    - **`hook_extractors.py`**: Change `agent.get_current_task()` → `agent.get_current_command()`. Change `current_task.plan_file_path`, `current_task.plan_content`, `task_id=current_task.id` → `command_*` equivalents. Change `mark_question_answered(task)` function parameter → `mark_question_answered(command)` and its internal `task.turns` → `command.turns`.

- [ ] **Task 6: Update Intelligence & Display Services**
  - Files:
    - `src/claude_headspace/services/card_state.py`
    - `src/claude_headspace/services/summarisation_service.py`
    - `src/claude_headspace/services/prompt_registry.py`
    - `src/claude_headspace/services/event_schemas.py`
    - `src/claude_headspace/services/inference_service.py`
    - `src/claude_headspace/services/priority_scoring.py`
    - `src/claude_headspace/services/notification_service.py`
  - Action per file:
    - **`card_state.py`**: Rename 15+ functions: `get_task_summary()` → `get_command_summary()`, `get_task_instruction()` → `get_command_instruction()`, `get_task_completion_summary()` → `get_command_completion_summary()`, etc. Change returned JSON dict keys: `current_task_id` → `current_command_id`, `task_summary` → `command_summary`, `task_instruction` → `command_instruction`, `task_completion_summary` → `command_completion_summary`. Change user-facing display strings: `"Idle - ready for task"` → `"Idle - ready for command"` (line 387), `"Task complete"` → `"Command complete"` (line 406), `"No active task"` → `"No active command"` (lines 220, 256). Change all imports and variable names.
    - **`summarisation_service.py`**: Change `SummarisationRequest.task` accesses → `.command`. Change `InferenceLevel.TASK` → `InferenceLevel.COMMAND`. Change prompt template keys. Change variable names (`task_summary`, `task` params). Change `summarise_task()` method → `summarise_command()` (line 311) and all call sites (line 532: `self.summarise_task(req.task)` → `self.summarise_command(req.command)`, line 356: `purpose="summarise_task"` → `purpose="summarise_command"`). Change `turn.task` relationship accesses throughout → `turn.command`. Change `"task_summary_updated"` broadcast reason string (line 544) → `"command_summary_updated"`. Change LLM prompt context strings: `f"Task instruction: {instruction}"` → `f"Command instruction: {instruction}"` (lines 651, 740). Change `f"Prior task: {prior.instruction}"` → `f"Prior command: {prior.instruction}"` (line 626). Rename methods `_get_prior_task_context()` → `_get_prior_command_context()` and `_resolve_task_prompt()` → `_resolve_command_prompt()` if present.
    - **`prompt_registry.py`**: Rename template keys: `task_completion` → `command_completion`, `task_completion_from_activity` → `command_completion_from_activity`, `task_completion_from_instruction` → `command_completion_from_instruction`, `turn_end_of_task` → `turn_end_of_command` (line 58). Update prompt text: "Task: {instruction}" → "Command: {instruction}", "Write a task board entry" → "Write a command board entry". Change `TASK` level references.
    - **`event_schemas.py`**: Change schema field names that reference `task_id` → `command_id`. Change any event type names containing "task". Update comment referencing `task_lifecycle.py`.
    - **`inference_service.py`**: Change `InferenceLevel.TASK` → `InferenceLevel.COMMAND`. Change `task_id` parameter names. Change `InferenceCall.task_id` → `InferenceCall.command_id`.
    - **`priority_scoring.py`**: Change `Task`/`TaskState` imports → `Command`/`CommandState`. Change query joins and variable names.
    - **`notification_service.py`**: Change event names `task_complete` → `command_complete` in ALL hardcoded dicts: defaults (line 21), prefix map (line 95), description map (line 100), titles map (line 128). Change method `notify_task_complete()` → `notify_command_complete()` (line 151) and its internal `event_type="task_complete"` → `"command_complete"` (line 153). Change callers in `hook_receiver.py` (line 189) and `hook_deferred_stop.py` (line 97): `svc.notify_task_complete(...)` → `svc.notify_command_complete(...)`. Change any method params or log messages referencing "task".

- [ ] **Task 7: Update Remaining Services**
  - Files:
    - `src/claude_headspace/services/intent_detector.py`
    - `src/claude_headspace/services/activity_aggregator.py`
    - `src/claude_headspace/services/agent_reaper.py`
    - `src/claude_headspace/services/transcript_reconciler.py`
    - `src/claude_headspace/services/voice_formatter.py`
    - `src/claude_headspace/services/team_content_detector.py`
    - `src/claude_headspace/services/tmux_watchdog.py`
    - `src/claude_headspace/services/agent_lifecycle.py`
    - `src/claude_headspace/services/config_editor.py`
  - Action per file:
    - **`intent_detector.py`**: Change `TurnIntent.END_OF_TASK` → `TurnIntent.END_OF_COMMAND`. Change `"TASK COMPLETE"` marker regex → `"COMMAND COMPLETE"` (line ~71). Change function `_detect_end_of_task()` → `_detect_end_of_command()` (line 213) and all call sites (lines 418, 474). Change variable names and imports.
    - **`activity_aggregator.py`**: Change `Task`/`TaskState` imports → `Command`/`CommandState`. Change query references and variable names.
    - **`agent_reaper.py`**: Change `from .task_lifecycle import TaskLifecycleManager` → `from .command_lifecycle import CommandLifecycleManager`. Change all instantiation and method calls. Change `Task`/`TaskState` imports.
    - **`transcript_reconciler.py`**: Change dead-code reference `current_app.extensions.get("task_lifecycle")` → `current_app.extensions.get("command_lifecycle")` (or remove if confirmed dead). Change `Turn.task_id` → `Turn.command_id` in queries. Change variable names.
    - **`voice_formatter.py`**: Change function parameter `tasks` → `commands` in `format_output()`. Change dict accesses `task.get("completion_summary")`, `task.get("instruction")`, `task.get("full_command")`, `task.get("full_output")` → `command.get(...)`. Change display strings: `"Task completed"` → `"Command completed"`, `"Unknown task"` → `"Unknown command"`, `"Task: {instr}"` → `"Command: {instr}"`, `"{len(tasks)} task{'s'...}"` → `"{len(commands)} command{'s'...}"`.
    - **`team_content_detector.py`**: Change any `task`-related variable names and string patterns.
    - **`tmux_watchdog.py`**: Change `from ..models.task import Task` → `from ..models.command import Command`. Change SQLAlchemy join: `Turn.task` → `Turn.command`, `Task.agent_id` → `Command.agent_id`. (Note: this file does NOT import `TaskState`.)
    - **`agent_lifecycle.py`**: Heavy file — 20+ domain refs. Change `Task`/`TaskState` imports → `Command`/`CommandState`. Change `agent.tasks[:5]` → `agent.commands[:5]`, `agent.tasks[:10]` → `agent.commands[:10]`, all `task.id`, `task.state.value`, `task.instruction`, `task.completion_summary`, `task.started_at`, `task.completed_at`, `task.turns` → `command.*`. **JSON KEY CONTRACT**: Change `"tasks": tasks_info` → `"commands": commands_info`. This key is consumed by `agent-info.js` (Task 10) as `data.tasks` → must become `data.commands` in lockstep.
    - **`config_editor.py`**: Change `FieldSchema("models.task", "string", "Model for task summaries", ...)` → `FieldSchema("models.command", "string", "Model for command summaries", ...)` (line 363). Update `help_text` from "task-level summaries" → "command-level summaries" and "task synthesis" → "command synthesis". Change notification section description "complete tasks" → "complete commands" (line 301). Change any other `task`-related config key references.
    - **`event_writer.py`**: Change `write_event()` parameter `task_id` → `command_id` (line 101). Change `Event(task_id=task_id)` constructor → `Event(command_id=command_id)` (line 111). Change retry fallback `event.task_id` → `event.command_id` (line 130). Change import `from ..models.event import Event` if needed.

- [ ] **Task 8: Update Routes**
  - Files:
    - `src/claude_headspace/routes/dashboard.py`
    - `src/claude_headspace/routes/projects.py`
    - `src/claude_headspace/routes/respond.py`
    - `src/claude_headspace/routes/hooks.py`
    - `src/claude_headspace/routes/summarisation.py`
    - `src/claude_headspace/routes/voice_bridge.py`
    - `src/claude_headspace/routes/notifications.py`
    - `src/claude_headspace/app.py` (notification config default)
  - Action per file:
    - **`dashboard.py`**: Change `Task`/`TaskState` imports → `Command`/`CommandState`. Change template context vars: `current_task` → `current_command`, `task_summary` → `command_summary`, etc.
    - **`projects.py`**: Change URL paths: `/api/agents/<id>/tasks` → `/api/agents/<id>/commands`, `/api/tasks/<id>/turns` → `/api/commands/<id>/turns`, `/api/tasks/<id>/full-text` → `/api/commands/<id>/full-text`. Change all imports, variable names, query joins, JSON response keys.
    - **`respond.py`**: Heavy file — 15+ domain refs. Change `from ..models.task import TaskState` → `from ..models.command import CommandState`. Change `current_task = agent.get_current_task()` → `current_command = agent.get_current_command()`, `current_task.state`, `current_task.turns`, `current_task.id`, `current_task.instruction`. Change `_count_options(task)` → `_count_options(command)`. Change `mark_question_answered(current_task)` → `mark_question_answered(current_command)`. Change `TaskState.AWAITING_INPUT` → `CommandState.AWAITING_INPUT`, `TaskState.PROCESSING` → `CommandState.PROCESSING`. Change `task_id=current_task.id` → `command_id=current_command.id`.
    - **`hooks.py`**: Change any `task`-related imports and variable names.
    - **`summarisation.py`**: Change route URL `/task/<int:task_id>` → `/command/<int:command_id>` (line 61). Change function `summarise_task()` → `summarise_command()` (line 62). Change `turn.task` → `turn.command` and `turn.task.agent` → `turn.command.agent` (line 49-51). Change all variable names (`task` → `command`), JSON response keys (`task_id` → `command_id`), error messages ("Task not found" → "Command not found"), and `"manual_task_summary"` → `"manual_command_summary"` broadcast reason (line 99). Change `from ..models.task import Task` → `from ..models.command import Command`.
    - **`voice_bridge.py`**: Change `from ..services.task_lifecycle import TaskLifecycleManager` → `from ..services.command_lifecycle import CommandLifecycleManager`. Change `Task`/`TaskState` imports. Change query joins on `Turn.task_id` → `Turn.command_id`. Change JSON response keys: `task_id` → `command_id`, `task_instruction` → `command_instruction`, `task_summary` → `command_summary`. **`agent_output()` endpoint**: Change `Task` query to `Command`. Rename variable `tasks` → `commands`, `task_dicts` → `command_dicts`. Change dict key `"task_id": task.id` → `"command_id": command.id` (line 838). Change top-level JSON response key `"tasks": task_dicts` → `"commands": command_dicts` (line 852). Change fallback string `f"{len(tasks)} recent tasks."` → `f"{len(commands)} recent commands."` (line 849). **Transcript endpoint**: Change `"type": "task_boundary"` → `"type": "command_boundary"` (line 1042).
    - **`notifications.py`**: Change event name refs `task_complete` → `command_complete`.
    - **`app.py`**: Change notification default `{"task_complete": True, "awaiting_input": True}` → `{"command_complete": True, "awaiting_input": True}` (line ~197).
    - **`config.py`**: Change `"task_complete": True` default (line ~67) → `"command_complete": True`. Change `"task": "anthropic/claude-haiku-4.5"` model level key (line ~98) → `"command": "..."`. Change `events.get("task_complete", True)` (line ~406) → `events.get("command_complete", True)`.

- [ ] **Task 9: Update Templates**
  - Files:
    - `templates/partials/_kanban_task_card.html` → RENAME to `_kanban_command_card.html`
    - `templates/dashboard.html`
    - `templates/partials/_agent_card.html`
    - `templates/partials/_kanban_view.html`
  - Action per file:
    - **`_kanban_task_card.html`**: `git mv` to `_kanban_command_card.html`. Change all template variables: `{{ task.id }}` → `{{ command.id }}`, `{{ task.state }}` → `{{ command.state }}`, `{{ task_summary }}` → `{{ command_summary }}`, etc. Change CSS classes.
    - **`dashboard.html`**: Change `{% include '_kanban_task_card.html' %}` → `{% include '_kanban_command_card.html' %}`. Change all `task`-related data attributes, IDs, and template variables.
    - **`_agent_card.html`**: Change template variables: `task_summary`, `task_instruction`, `task_completion_summary`, `current_task_id` → `command_*` equivalents. Change data attributes.
    - **`_kanban_view.html`**: Change include path. Change any `task`-related template variables and CSS classes.

- [ ] **Task 10: Update Dashboard JavaScript**
  - Files:
    - `static/js/dashboard-sse.js`
    - `static/js/sse-client.js`
    - `static/js/agent-info.js`
    - `static/js/project_show.js`
    - `static/js/logging-inference.js`
    - `static/js/card-tooltip.js`
    - `static/js/full-text-modal.js`
  - Action: Across all 7 files:
    - Change SSE event type handlers: `task_summary` → `command_summary`, `task_complete` → `command_complete`, `task_instruction` → `command_instruction`
    - Change JSON payload key accesses: `data.task_id` → `data.command_id`, `data.task_summary` → `data.command_summary`, etc.
    - Change DOM selectors and data attributes: `[data-task-id]` → `[data-command-id]`, `.task-summary` → `.command-summary`, `.task-instruction` → `.command-instruction`
    - Change variable names: `taskId` → `commandId`, `taskSummary` → `commandSummary`, etc.
    - Change string literals in `querySelector`, `getElementById`, `dataset.taskId` → `dataset.commandId`
  - Heavy-change files requiring extra attention:
    - **`full-text-modal.js`**: Change API URL `/api/tasks/<id>/full-text` → `/api/commands/<id>/full-text`. Change cache key `taskId` → `commandId`. Change function param `show(taskId, type)` → `show(commandId, type)`.
    - **`project_show.js`**: Change `expandedTasks` → `expandedCommands`, `taskTurns` → `commandTurns`, API URL `/api/agents/<id>/tasks` → `/api/agents/<id>/commands`, `/api/tasks/<id>/turns` → `/api/commands/<id>/turns`, `toggleTaskTurns()` → `toggleCommandTurns()`, DOM IDs `task-arrow-*` → `command-arrow-*`, `task-turns-*` → `command-turns-*`, `task-instruction` → `command-instruction`, `task-summary` → `command-summary`, `task-stats` → `command-stats`.
    - **`agent-info.js`**: Change `data.tasks` → `data.commands`, "Task History" section title → "Command History", task rendering variables and DOM structure.
    - **`dashboard-sse.js`**: Change `handleTaskSummary` → `handleCommandSummary`, SSE listener `client.on('task_summary', ...)` → `client.on('command_summary', ...)`, `.task-summary` selectors, `data.task_instruction` → `data.command_instruction`.
    - **`logging-inference.js`**: Change `case "task":` → `case "command":` (InferenceLevel enum display).
    - **`card-tooltip.js`**: Change `.task-instruction, .task-summary` selectors → `.command-instruction, .command-summary`.

- [ ] **Task 11: Update Voice Chat UI**
  - Files:
    - `static/voice/voice-sse-handler.js`
    - `static/voice/voice-chat-controller.js`
    - `static/voice/voice-chat-renderer.js`
    - `static/voice/voice-state.js`
    - `static/voice/voice-sidebar.js`
    - `static/voice/voice.html`
  - Action per file:
    - **`voice-sse-handler.js`**: Change SSE event handlers for `task_*` events → `command_*`. Change payload key accesses. Change `t.type === 'task_boundary'` → `'command_boundary'` (lines 412-413).
    - **`voice-chat-controller.js`**: Change `task_id` refs → `command_id`. Change method calls.
    - **`voice-chat-renderer.js`**: Change `createTaskSeparatorEl()` → `createCommandSeparatorEl()`, `maybeInsertTaskSeparator()` → `maybeInsertCommandSeparator()`. Change CSS class `.chat-task-separator` → `.chat-command-separator`. Change `data-task-id` → `data-command-id`. Change `turn.type === 'task_boundary'` → `'command_boundary'` (line 105).
    - **`voice-state.js`**: Change `VoiceState.chatLastTaskId` → `VoiceState.chatLastCommandId`. Change all `task_*` property names.
    - **`voice-sidebar.js`**: Change `task_summary` → `command_summary`, `task_instruction` → `command_instruction` references.
    - **`voice.html`**: Change any inline `task`-related IDs, classes, or data attributes.

- [ ] **Task 12: Update CSS and Rebuild Tailwind**
  - Files:
    - `static/css/src/input.css`
    - `static/voice/voice.css`
  - Action:
    - **`input.css`**: Rename CSS classes: `.task-instruction` → `.command-instruction`, `.task-summary` → `.command-summary`, `.agent-info-task-*` → `.agent-info-command-*`, `.chat-task-instruction` → `.chat-command-instruction`, `.kanban-completed-task` → `.kanban-completed-command`. Be thorough — search for every `task` substring in selector names.
    - **`voice.css`**: Rename classes: `.chat-task-instruction` → `.chat-command-instruction`, `.chat-task-separator` → `.chat-command-separator`, `.chat-task-separator::before` → `.chat-command-separator::before`, `.chat-task-separator::after` → `.chat-command-separator::after`, `.chat-task-separator span` → `.chat-command-separator span`.
    - **Rebuild**: Run `npx tailwindcss -i static/css/src/input.css -o static/css/main.css`
    - **Verify**: Check compiled `main.css` contains all renamed selectors. Spot-check that other custom selectors (`.objective-banner-*`, `.card-editor`, `.state-strip`, `.metric-card`, `.logging-subtab`) are preserved.

- [ ] **Task 13: Rename Test Files and Update Test Factories**
  - Files:
    - `tests/services/test_task_lifecycle.py` → RENAME to `test_command_lifecycle.py`
    - `tests/services/test_task_lifecycle_summarisation.py` → RENAME to `test_command_lifecycle_summarisation.py`
    - `tests/routes/test_task_full_text.py` → RENAME to `test_command_full_text.py`
    - `tests/integration/factories.py`
    - `tests/integration/test_factories.py`
  - Action:
    - `git mv` the 3 test files
    - **`factories.py`**: Rename `TaskFactory` → `CommandFactory`. Change `model = Task` → `model = Command`. Change imports from `models.task` → `models.command`. Change `TurnFactory.task` SubFactory → `TurnFactory.command`.
    - **`test_factories.py`**: Change `TaskFactory` refs → `CommandFactory`. Change assertions.
    - Inside the 3 renamed test files: Update all imports, class names, method names, variable names, and assertions to use `command`/`Command`/`CommandState`/`CommandLifecycleManager`.

- [ ] **Task 14: Update Service Unit Tests**
  - Files (22 files): `tests/services/test_state_machine.py`, `test_command_lifecycle.py` (renamed in Task 13), `test_transcript_reconciler.py`, `test_turn_reliability.py`, `test_hook_receiver.py`, `test_card_state.py`, `test_full_command_output.py`, `test_command_lifecycle_summarisation.py` (renamed in Task 13), `test_intent_detector.py`, `test_summarisation_service.py`, `test_notification_service.py`, `test_priority_scoring.py`, `test_inference_service.py`, `test_inference_gating.py`, `test_brain_reboot.py`, `test_agent_reaper.py`, `test_team_content_detector.py`, `test_voice_formatter.py`, `test_voice_auth.py`, `test_config_editor.py`, `test_activity_aggregator.py`, `test_prompt_registry.py`, `test_summarisation_frustration.py`, `test_progress_summary.py`, `test_event_schemas.py`
  - Action: Apply bulk rename patterns across all files:
    - `from claude_headspace.models import Task, TaskState` → `from claude_headspace.models import Command, CommandState`
    - `from claude_headspace.models.task import Task, TaskState` → `from claude_headspace.models.command import Command, CommandState`
    - `from claude_headspace.services.task_lifecycle import TaskLifecycleManager` → `from claude_headspace.services.command_lifecycle import CommandLifecycleManager`
    - `mock_task = MagicMock()` → `mock_command = MagicMock()`
    - `agent.get_current_task.return_value = mock_task` → `agent.get_current_command.return_value = mock_command`
    - `result["task_summary"]` → `result["command_summary"]` (and all similar dict key accesses)
    - `TaskState.IDLE` → `CommandState.IDLE` (all enum values)
    - `TurnIntent.END_OF_TASK` → `TurnIntent.END_OF_COMMAND`
    - `InferenceLevel.TASK` → `InferenceLevel.COMMAND`
    - Variable names: `current_task` → `current_command`, `task_data` → `command_data`, etc.
  - Notes: **DO NOT change** `TurnIntent.COMMAND` — it's a turn intent, not the Command model. In `test_intent_detector.py`, update `"TASK COMPLETE"` test assertions → `"COMMAND COMPLETE"`.

- [ ] **Task 15: Update Route, Integration, and E2E Tests**
  - Files:
    - Route tests (12): `tests/routes/test_command_full_text.py` (renamed), `test_voice_bridge.py`, `test_voice_bridge_upload.py`, `test_voice_bridge_client.py`, `test_respond.py`, `test_dashboard.py`, `test_dashboard_interactivity.py`, `test_projects.py`, `test_inference.py`, `test_summarisation.py`, `test_project_show_tree.py`, `test_agents.py`
    - Integration tests (8): `tests/integration/test_factories.py` (done in Task 13), `test_model_constraints.py`, `test_summary_persistence.py`, `test_cross_service_flow.py`, `test_respond_flow.py`, `test_persistence_flow.py`, `test_inference_call.py`
    - E2E tests (7): `tests/e2e/test_voice_app_baseline.py`, `test_debounce.py`, `test_edge_cases.py`, `test_multi_agent.py`, `test_turn_lifecycle.py`, `test_voice_chat_ordering.py`, `tests/e2e/helpers/dashboard_assertions.py`
    - Root: `tests/test_models.py`
  - Action: Same bulk rename patterns as Task 14, plus:
    - Route tests: Change URL paths in test requests (`/api/tasks/` → `/api/commands/`)
    - Integration tests: Change `TaskFactory` → `CommandFactory`, `Turn(task_id=...)` → `Turn(command_id=...)`
    - E2E tests: Change CSS selectors (`.chat-task-*` → `.chat-command-*`), data attributes (`data-task-id` → `data-command-id`), SSE event names
    - `tests/test_models.py`: Change model imports and assertions

- [ ] **Task 16: Update CLAUDE.md, Global CLAUDE.md, and Setup Prompt**
  - Files:
    - `CLAUDE.md` (project)
    - `~/.claude/CLAUDE.md` (user's global instructions)
    - `docs/application/claude_code_setup_prompt.md` (installation prompt)
  - Action for project `CLAUDE.md`:
    - Data Models table: `Task` row → `Command`, `task_id` → `command_id` in related model descriptions
    - "Task States" section → "Command States"
    - `TaskState` → `CommandState`, `TaskLifecycleManager` → `CommandLifecycleManager`
    - Service descriptions: "task creation", "task lifecycle", "task-level summaries", "task state" → "command" equivalents
    - API endpoints: `/api/tasks/` → `/api/commands/`
    - Turn Intents: `END_OF_TASK` → `END_OF_COMMAND`
    - Inference Levels: `TURN, TASK, PROJECT, OBJECTIVE` → `TURN, COMMAND, PROJECT, OBJECTIVE`
    - Event types: any referencing "task"
    - Task Completion Signal section: `TASK COMPLETE` → `COMMAND COMPLETE`
    - **DO NOT change** generic English usage of "task" in non-model contexts
  - Action for global `~/.claude/CLAUDE.md`:
    - "Task Completion Signal" section → "Command Completion Signal"
    - `TASK COMPLETE` marker → `COMMAND COMPLETE`
    - All references to "task" in that section → "command"
  - Action for `docs/application/claude_code_setup_prompt.md`:
    - Step 8 heading: "Configure global Claude Code instructions" — update description mentioning "task completion signal" → "command completion signal"
    - Step 8 grep check: `grep -q "Task Completion Signal"` → `grep -q "Command Completion Signal"`
    - Step 8 section heading in markdown block: `## Task Completion Signal` → `## Command Completion Signal`
    - All `TASK COMPLETE` marker strings in the embedded markdown block → `COMMAND COMPLETE` (lines ~333, ~339, and all examples ~347-351)
    - Step 8 append logic reference: `"Task Completion Signal" section` → `"Command Completion Signal" section`
    - Step 8 verification grep: `grep "Task Completion Signal"` → `grep "Command Completion Signal"`
    - Step 10 checklist line: `Global Claude Code instructions configured` — verify wording still accurate

- [ ] **Task 17: Update Root Files, Help, and Architecture Documentation**
  - Files:
    - `config.example.yaml` (root)
    - `README.md` (root)
    - `brain_reboot/waypoint.md`
    - `docs/help/*.md` (7 files)
    - `docs/architecture/*.md` (~10 files)
    - `docs/conceptual/*.md`
    - `docs/diagrams/*.md`
    - `docs/testing/*.md` (~2 files)
  - Action per file:
    - **`config.example.yaml`**: Change `task: anthropic/claude-haiku-4.5` under `openrouter.models` → `command: anthropic/claude-haiku-4.5`. Change any `task_complete` notification event keys.
    - **`README.md`**: Change all domain-model Task references: "5-state task lifecycle" → "5-state command lifecycle", "Task summarisation" → "Command summarisation", `POST /api/summarise/task/<id>` → `POST /api/summarise/command/<id>`, "Task Lifecycle" section, etc. Heavy file — many references.
    - **`brain_reboot/waypoint.md`**: Change "recent tasks" → "recent commands" (minor).
    - **docs/ files**: Search for domain-model "task" references and rename to "command": "Task model" → "Command model", "Task states" → "Command states", `TaskState` → `CommandState`, `TaskLifecycleManager` → `CommandLifecycleManager`, code examples, API endpoints, state machine diagrams.
  - Notes: Be conservative. Only rename clear domain-model references. Leave generic English "task" as-is.

- [ ] **Task 18: Update OpenSpec, PRDs, and Remaining Docs**
  - Files:
    - `openspec/specs/task-model/` → RENAME dir to `command-model/`
    - `openspec/specs/*.md` (~34 files)
    - `openspec/changes/archive/**/*.md` (~97 files)
    - `docs/prds/**/*.md` (~30 files)
    - `docs/beads/*.md` (heavy — architecture doc discussing Task/Command rename)
    - `docs/bugs/*.md` (task separators, task_id, task boundaries)
    - `docs/ideas/*.md` (~3 files)
    - `docs/investigations/*.md` (Task/Turn data loss)
    - `docs/reviews_remediation/*.md` (~8 files — state machine, turn capture, voice chat)
    - `docs/roadmap/*.md` (~8 files — Task lifecycle, summarisation)
    - `docs/sprints/*.md` (~4 files)
    - `docs/workshop/*.md` (~7 files — agent teams, ERDs with Task model)
    - `docs/prompts/*.md` (test audit)
  - Action:
    - `git mv openspec/specs/task-model openspec/specs/command-model`
    - Across ALL files: rename domain-model references (Task → Command, TaskState → CommandState, task_id → command_id, `tasks` table → `commands` table, etc.)
    - Update any cross-references to the `task-model/` spec directory
  - Notes: These are historical/reference documents. Focus on correctness of model name references. Don't rewrite narrative prose. Leave generic English "task" as-is.

- [ ] **Task 19: Update Config, Run Migration, Restart, and Smoke Test**
  - Action (sequential):
    1. **Stop the server** before any migration. If the server is running against the dev database with old column names and the migration renames them, the live server will immediately throw SQL errors.
    2. **Update `config.yaml`** (requires user approval — protected file, symlinked to `otl_support`): Change `task:` → `command:` under `openrouter.models`. Change any `task_complete` notification event keys. This MUST happen before server restart or `config.py` will read old `task:` key but code expects `command:` key, causing silent model selection fallback.
    3. Run migration on test database first: `DATABASE_URL=postgresql://localhost/claude_headspace_test flask db upgrade`
    4. Verify schema: `psql claude_headspace_test -c "\dt"` (confirm `commands` table exists, `tasks` does not)
    5. Verify columns: `psql claude_headspace_test -c "\d turns"` (confirm `command_id` column)
    6. Verify enum: `psql claude_headspace_test -c "SELECT typname FROM pg_type WHERE typname IN ('commandstate', 'taskstate')"` (confirm `commandstate` exists, `taskstate` does not)
    7. Run migration on development database: `flask db upgrade` (confirm target database first)
    8. Restart server: `./restart_server.sh`
    9. Smoke test: `curl -sk https://smac.griffin-blenny.ts.net:5055/health`
    10. Visual verification: Take Playwright screenshot of dashboard
  - Notes: If migration fails, `flask db downgrade` to the previous revision. Restart the server with old code if needed.

- [ ] **Task 20: Full Validation — Run Complete Test Suite**
  - Action:
    1. Ensure test database exists: `createdb claude_headspace_test` (if not already)
    2. Run full test suite: `pytest --tb=short`
    3. Fix any failures (expect: import errors from missed renames, assertion mismatches on JSON keys)
    4. Re-run until all tests pass
    5. Take Playwright screenshot of dashboard with active agents (if available) to verify UI renders correctly
    6. Verify SSE events in browser devtools (check event names are `command_*` not `task_*`)
  - Notes: This is the final gate. All 960+ tests must pass. Any failure indicates a missed rename.

---

## Acceptance Criteria

- [ ] **AC 1:** Given the Alembic migration has been applied, when I query `\dt` in psql, then I see table `commands` and do NOT see table `tasks`.

- [ ] **AC 2:** Given the migration has been applied, when I query `\d turns`, then the column is named `command_id` (not `task_id`), and it references `commands.id`.

- [ ] **AC 3:** Given the migration has been applied, when I query `SELECT typname FROM pg_type WHERE typname = 'commandstate'`, then I get one row; querying for `taskstate` returns zero rows.

- [ ] **AC 4:** Given the migration has been applied, when I query `SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'turnintent'`, then I see `end_of_command` and do NOT see `end_of_task`.

- [ ] **AC 5:** Given the Flask app is running, when I import `from claude_headspace.models import Command, CommandState`, then the import succeeds. Importing `Task` or `TaskState` from models raises `ImportError`.

- [ ] **AC 6:** Given the Flask app is running, when I `GET /api/agents/<id>/commands`, then I receive a JSON response with command data. `GET /api/agents/<id>/tasks` returns 404.

- [ ] **AC 7:** Given the SSE stream is connected, when a command completes, then the SSE event payload contains keys `command_id`, `command_summary`, `command_completion_summary` — not `task_*` equivalents.

- [ ] **AC 8:** Given the dashboard is loaded, when I inspect the DOM for an agent card, then I see `data-command-id` attributes and `.command-summary` CSS classes — not `task` equivalents.

- [ ] **AC 9:** Given the voice chat UI is loaded, when a new command boundary occurs, then the separator element has class `.chat-command-separator` and attribute `data-command-id` — not `task` equivalents.

- [ ] **AC 10:** Given the full test suite runs, when `pytest` completes, then all tests pass with zero failures.

- [ ] **AC 11:** Given the migration downgrade is run (`flask db downgrade`), when I query `\dt`, then the original `tasks` table is restored and all data is intact.

- [ ] **AC 12:** Given CLAUDE.md is updated, when I search for `TaskState`, `Task model`, `task_id`, or `TASK COMPLETE`, then zero domain-model matches are found (excluding only `<task-notification>` XML tag and generic English usage).

- [ ] **AC 13:** Given the migration has been applied, when I query `SELECT DISTINCT level FROM inference_calls WHERE level = 'task'`, then zero rows are returned; querying for `level = 'command'` returns rows (InferenceLevel is varchar, not a PG enum).

- [ ] **AC 14:** Given a Claude Code agent outputs `COMMAND COMPLETE`, when the intent detector processes the turn, then it correctly detects `TurnIntent.END_OF_COMMAND` intent.

- [ ] **AC 15:** Given a command completes, when the notification service fires, then the event type is `command_complete` and the macOS notification title is "Command Complete" (not "Task Complete").

---

## Dependencies

### External Dependencies
- PostgreSQL 10+ (required for `ALTER TYPE ... RENAME VALUE`)
- Node.js + npm (required for Tailwind CSS rebuild)
- Alembic / Flask-Migrate (database migration tooling)

### Internal Dependencies
- All code changes (Tasks 2-18) must complete before the migration runs (Task 19)
- Template file rename (Task 9) must be in lockstep with any template include references
- CSS class renames (Task 12) must be in lockstep with template/JS changes (Tasks 9-11)
- Test file renames (Task 13) must happen before test content updates (Tasks 14-15)
- SSE event name changes in Python (Tasks 5-8) must be in lockstep with JS consumers (Tasks 10-11)

### Configuration Dependencies
- `config.yaml` (symlinked to `otl_support`) contains `task:` under `openrouter.models` and potentially `task_complete` notification event key — must be updated manually (protected file, requires user approval)
- `config.example.yaml` contains the same `task:` model level key — updated in Task 17

---

## Testing Strategy

### Unit Tests
- All existing ~960 tests must pass after the rename
- No new unit tests are needed — this is a pure rename with identical behaviour
- Tests themselves are renamed/updated to use the new names

### Integration Tests
- `tests/integration/` tests use real PostgreSQL — they validate the migration is correct
- `CommandFactory` replaces `TaskFactory` — test DB operations use new column names
- Cross-service flow tests validate the full lifecycle with renamed models

### Manual Testing
1. **Database migration:** Verify up and down migration on test database
2. **Dashboard UI:** Take Playwright screenshots — verify cards render with command data
3. **SSE events:** Open browser devtools Network tab, filter SSE, confirm event names
4. **Voice chat:** Open voice UI, verify command separators render correctly
5. **Health endpoint:** Confirm `/health` returns 200 after restart

### Regression Risk Areas
- **SSE contract:** If any JS file still listens for `task_*` events, it will silently ignore the renamed `command_*` events — no error, just missing updates
- **Template variables:** If a route still passes `task_summary` but the template expects `command_summary`, Jinja2 will render empty — no error
- **CSS classes:** If HTML uses `.command-summary` but CSS still defines `.task-summary`, styles will be missing — visual regression only
- **Database queries:** If any service still queries `task_id` column after migration, it will raise a hard SQL error — easy to detect

---

## Notes

### Silent-Failure Contracts (Cross-Layer String Matches)

These are string-value contracts where a mismatch causes **silent failure** (no error, just broken behaviour):

1. **Summarisation pipeline**: `SummarisationRequest.type = "task_completion"` (command_lifecycle.py) ↔ `req.type == "task_completion"` check (summarisation_service.py) ↔ prompt template keys `task_completion*` (prompt_registry.py). All three must rename in lockstep.
2. **SSE event names**: Python broadcast `task_summary`/`command_summary` (card_state.py, hook_receiver.py) ↔ JS listener `client.on('task_summary', ...)` (dashboard-sse.js, voice-sse-handler.js). Must match exactly.
3. **JSON response keys**: Route/service returns `"tasks"` key (agent_lifecycle.py, card_state.py, voice_bridge.py) ↔ JS accesses `data.tasks` (agent-info.js, project_show.js). Must match exactly.
4. **Notification event names**: `"task_complete"` (notification_service.py, config.py, config.yaml, app.py) — all four sources must agree.
5. **CSS class names**: HTML/JS creates `.chat-task-separator` ↔ CSS defines `.chat-task-separator` (voice.css, input.css). Must match exactly.
6. **COMMAND COMPLETE marker**: `intent_detector.py` regex ↔ CLAUDE.md output instruction ↔ `~/.claude/CLAUDE.md` ↔ `claude_code_setup_prompt.md`. All four must match.
7. **Broadcast reason strings**: `"task_summary_updated"` (summarisation_service.py line 544) and `"manual_task_summary"` (summarisation.py route line 99) are passed to `broadcast_card_refresh()`. While these are currently debug/logging strings, they must rename for consistency and to avoid confusion during future debugging.
8. **Voice transcript `task_boundary` type**: Python emits `"type": "task_boundary"` (voice_bridge.py line 1042) ↔ JS checks `turn.type === 'task_boundary'` (voice-chat-renderer.js line 105) and `t.type === 'task_boundary'` (voice-sse-handler.js lines 412-413). Must rename to `"command_boundary"` in lockstep or voice chat transcript separators silently vanish.

**Verification after rename**: Run `grep -rn "task_" static/js/ static/voice/ | grep -v vendor` and confirm zero remaining domain-model matches. Run `grep -rn '"task' src/claude_headspace/services/card_state.py src/claude_headspace/services/command_lifecycle.py` and confirm zero remaining `"task_*"` string literals.

### High-Risk Items
1. **SSE event contract (silent failures):** Mismatched event names between Python and JS produce no errors — just missing UI updates. Mitigation: Grep for any remaining `task_` in JS files after the rename; verify SSE in browser devtools.
2. **hook_receiver.py size (1600+ lines, 200+ renames):** Highest density of changes. Easy to miss one. Mitigation: Run `grep -n "task" hook_receiver.py` after the rename and manually verify each remaining match is a DO NOT CHANGE item.
3. **PostgreSQL enum type rename:** `ALTER TYPE taskstate RENAME TO commandstate` — verify this works on the project's PostgreSQL version. If it fails, fall back to the DROP/CREATE cycle documented in the migration details.
4. **Template cache:** Flask and browsers cache aggressively. After the rename, hard-refresh and `./restart_server.sh` are required. Take Playwright screenshots to verify.
5. **"COMMAND COMPLETE" marker coordination:** The `intent_detector.py` regex, project CLAUDE.md, and global `~/.claude/CLAUDE.md` must all change in lockstep. If the detector changes but CLAUDE.md still says "TASK COMPLETE", active Claude Code sessions will output the old marker and headspace won't detect completion. Mitigation: Update all three in the same task; restart any active Claude Code sessions after the change.

### Known Limitations
- Old Alembic migration files will still reference `tasks` table and `task_id` columns — this is intentional (historical records)
- `<task-notification>` XML tags will still say "task" — this is a Claude Code protocol tag
- `config.yaml` notification key update requires manual approval (protected file)

### Future Considerations
- When the new "Task" concept is introduced (the reason for this rename), its model, table, and routes will use the now-freed "task" namespace
- Consider adding import aliases in `models/__init__.py` during a transition period if external consumers exist (none known currently)
