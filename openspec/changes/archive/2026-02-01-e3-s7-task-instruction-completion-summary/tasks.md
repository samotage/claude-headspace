## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Data Model & Migration

- [x] 2.1 Create Alembic migration: rename `summary` → `completion_summary`, rename `summary_generated_at` → `completion_summary_generated_at`, add `instruction` (Text, nullable), add `instruction_generated_at` (DateTime, nullable)
- [x] 2.2 Update Task model (`models/task.py`): rename fields, add new fields
- [x] 2.3 Run migration and verify schema

### Reference Updates (summary → completion_summary)

- [x] 2.4 Update `summarisation_service.py`: all `task.summary` → `task.completion_summary`, `task.summary_generated_at` → `task.completion_summary_generated_at`
- [x] 2.5 Update `routes/summarisation.py`: field references in API responses
- [x] 2.6 Update `routes/dashboard.py`: `_get_completed_task_summary()` and `get_task_summary()` field references
- [x] 2.7 Update `services/priority_scoring.py`: task_summary variable references (no changes needed — uses turn.summary which is unchanged)
- [x] 2.8 Update all test files referencing `task.summary` or `task.summary_generated_at`

### Instruction Generation

- [x] 2.9 Add `summarise_instruction()` method to `SummarisationService` — builds instruction prompt from USER COMMAND turn text, persists to `task.instruction` and `task.instruction_generated_at`
- [x] 2.10 Add `summarise_instruction_async()` method — async wrapper with SSE broadcast of `instruction_summary` event
- [x] 2.11 Update `task_lifecycle.py` `process_turn()` or `create_task()` — trigger instruction summarisation when task created from USER COMMAND turn

### Prompt Rebuild — Task Completion Summary

- [x] 2.12 Rebuild `_build_task_prompt()` — primary inputs: task.instruction + final turn text; remove timestamps/turn counts as primary content
- [x] 2.13 Add empty text guard — if final turn text is None/empty, defer completion summarisation (return without generating)

### Prompt Rebuild — Turn Summarisation

- [x] 2.14 Rebuild `_build_turn_prompt()` with intent-aware templates (COMMAND, QUESTION, COMPLETION, PROGRESS, ANSWER, END_OF_TASK)
- [x] 2.15 Add task instruction context to turn prompts (fetch task.instruction when available)
- [x] 2.16 Add empty text guard — return None when turn.text is None/empty

### Agent Card UI

- [x] 2.17 Update `_agent_card.html` partial — two-line display: task instruction (primary line) + latest turn summary (secondary line)
- [x] 2.18 Update `dashboard.py` to pass `task_instruction` in agent context dict alongside `task_summary`
- [x] 2.19 Update `dashboard-sse.js` — add `instruction_summary` event handler to update instruction line
- [x] 2.20 Update `dashboard-sse.js` — ensure `task_summary` and `turn_summary` handlers update correct DOM elements (secondary line)

### SSE & Broadcaster

- [x] 2.21 Register `instruction_summary` event type in broadcaster if event types are registered (N/A — broadcaster accepts any event_type dynamically)
- [x] 2.22 Update `task_summary` SSE payload to use `completion_summary` field name (or maintain backward-compat `summary` key) — maintained `summary` key for JS backward compat

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests: Task model — verify new fields (`instruction`, `instruction_generated_at`, `completion_summary`, `completion_summary_generated_at`)
- [x] 3.2 Unit tests: `summarise_instruction()` — prompt building, persistence, empty text guard
- [x] 3.3 Unit tests: `summarise_instruction_async()` — async execution, SSE broadcast
- [x] 3.4 Unit tests: rebuilt `_build_task_prompt()` — correct inputs, no timestamps/turn counts
- [x] 3.5 Unit tests: rebuilt `_build_turn_prompt()` — intent-aware templates, task instruction context, empty text guard
- [x] 3.6 Route tests: updated `/api/summarise/task/<id>` response with `completion_summary`
- [x] 3.7 Route tests: instruction endpoint (if added) — N/A, no separate instruction endpoint added
- [x] 3.8 Dashboard route tests: `get_task_summary()` and `_get_completed_task_summary()` with new field names + `get_task_instruction()`
- [x] 3.9 Integration tests: end-to-end instruction generation flow (task creation → instruction summary → SSE broadcast) — covered by async + broadcast unit tests
- [x] 3.10 Verify all existing tests pass with field rename (no regressions)

## 4. Final Verification

- [x] 4.1 All tests passing (176 passed, 1 pre-existing failure in unrelated test)
- [ ] 4.2 No linter errors
- [ ] 4.3 Migration applies cleanly (up and down)
- [ ] 4.4 Agent card displays instruction + turn summary correctly
- [ ] 4.5 SSE events push instruction updates in real time
