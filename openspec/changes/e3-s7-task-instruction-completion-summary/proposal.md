## Why

Task summaries are currently useless — the prompts receive only timestamps, turn counts, and a final turn text that may be empty. Turn summaries lack task context entirely. The result is filler like "The task started on 2026-02-01 and was completed, taking 9 turns." This defeats the core value proposition of Headspace's intelligence layer.

This change introduces task-level instruction tracking (what was commanded) and rebuilds all summarisation prompts to produce context-aware, actionable summaries that let users immediately understand what each agent was asked to do and what it's currently doing.

## What Changes

### Data Model
- **NEW** `instruction` field (Text, nullable) on Task model — LLM-derived summary of the initiating USER COMMAND turn
- **NEW** `instruction_generated_at` field (DateTime, nullable) on Task model
- **BREAKING** Rename `task.summary` → `task.completion_summary` across entire codebase
- **BREAKING** Rename `task.summary_generated_at` → `task.completion_summary_generated_at`
- Alembic migration for field rename and new field addition

### Summarisation Service
- New `summarise_instruction()` method — generates 1-2 sentence instruction summary from USER COMMAND turn text
- New `summarise_instruction_async()` method — async wrapper with SSE broadcast
- Rebuild `_build_task_prompt()` — primary inputs become task instruction + agent's final message (no timestamps/turn counts)
- Rebuild `_build_turn_prompt()` — intent-aware templates with task instruction context
- Empty text guard — skip summarisation when turn.text is None/empty (return None)
- Completion summary deferred if final turn text not yet populated

### Task Lifecycle
- Trigger instruction summarisation when task created from USER COMMAND turn
- Ensure async instruction generation does not block hook pipeline

### SSE Events
- New `instruction_summary` event type broadcast when instruction generated
- Existing `task_summary` event continues for completion summaries (field name updated in payload)

### Agent Card UI
- Two-line display: task instruction (primary) + latest turn summary (secondary)
- SSE handler for `instruction_summary` event updates instruction line independently
- Idle state behaviour preserved

### Reference Updates
- All `task.summary` references → `task.completion_summary` across services, routes, templates, SSE handlers, tests
- All `task.summary_generated_at` references → `task.completion_summary_generated_at`

## Impact

- Affected specs: Task model, summarisation capabilities, agent card display, SSE event contracts
- Affected code:
  - `src/claude_headspace/models/task.py` — field rename + new fields
  - `src/claude_headspace/services/summarisation_service.py` — prompt rebuild + new instruction methods
  - `src/claude_headspace/services/task_lifecycle.py` — instruction trigger on task creation
  - `src/claude_headspace/routes/summarisation.py` — updated field references, new instruction endpoint
  - `src/claude_headspace/routes/dashboard.py` — `get_task_summary()` and `_get_completed_task_summary()` updated for new fields
  - `src/claude_headspace/services/priority_scoring.py` — `task_summary` variable references
  - `templates/partials/_agent_card.html` — two-line instruction + turn summary display
  - `static/js/dashboard-sse.js` — new instruction_summary handler, updated task_summary handler
  - `templates/logging_inference.html` — if referencing task summary field
  - `migrations/versions/` — new migration for field rename + addition
  - All test files referencing `task.summary` or `task.summary_generated_at`
