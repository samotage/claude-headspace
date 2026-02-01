# Proposal Summary: e3-s7-task-instruction-completion-summary

## Architecture Decisions
- Task model enriched with `instruction` + `instruction_generated_at` fields; existing `summary` renamed to `completion_summary` (not a new field — rename preserves data)
- Instruction generation uses the same async thread pool pattern as existing turn/task summarisation
- Intent-aware turn prompts use a template map keyed by TurnIntent enum values
- Agent card UI adopts a two-line layout (instruction + turn summary) with independent SSE update paths
- Empty text guard at the summarisation service level (not at caller level) to centralize the skip logic

## Implementation Approach
- Alembic migration uses `ALTER TABLE ... RENAME COLUMN` for zero-downtime field renames (no data copy needed)
- Summarisation service gets three new/rebuilt methods: `summarise_instruction()`, rebuilt `_build_task_prompt()`, rebuilt `_build_turn_prompt()`
- Task lifecycle triggers instruction summarisation in `process_turn()` when creating a task from USER COMMAND
- Dashboard route adds `task_instruction` to the agent context dict; template displays it as primary line
- SSE introduces `instruction_summary` event type; existing `task_summary`/`turn_summary` events continue unchanged
- All `task.summary` → `task.completion_summary` renames done as a bulk find-and-replace pass across the codebase

## Files to Modify

### Models
- `src/claude_headspace/models/task.py` — rename `summary`→`completion_summary`, `summary_generated_at`→`completion_summary_generated_at`, add `instruction`, `instruction_generated_at`

### Migrations
- `migrations/versions/` — new migration for field rename + addition

### Services
- `src/claude_headspace/services/summarisation_service.py` — new `summarise_instruction()`, `summarise_instruction_async()`, rebuilt `_build_task_prompt()`, rebuilt `_build_turn_prompt()`, empty text guards
- `src/claude_headspace/services/task_lifecycle.py` — trigger instruction summarisation on task creation from USER COMMAND
- `src/claude_headspace/services/priority_scoring.py` — update `task_summary` variable that reads from task model

### Routes
- `src/claude_headspace/routes/summarisation.py` — update field references from `summary` to `completion_summary`
- `src/claude_headspace/routes/dashboard.py` — update `get_task_summary()`, `_get_completed_task_summary()` field refs; add `task_instruction` to agent context

### Templates
- `templates/partials/_agent_card.html` — two-line display: instruction (primary) + turn summary (secondary)

### Static JS
- `static/js/dashboard-sse.js` — new `instruction_summary` handler; update existing handlers to target correct DOM elements

### Tests (field rename across all)
- `tests/services/test_summarisation_service.py` — new tests for instruction, rebuilt prompts, empty text guard
- `tests/routes/test_summarisation.py` — updated field references
- `tests/routes/test_dashboard.py` — new instruction display tests
- `tests/services/test_task_lifecycle.py` — instruction trigger test
- `tests/services/test_priority_scoring.py` — updated field references
- All other test files referencing `task.summary` or `task.summary_generated_at`

## Acceptance Criteria
- Every new task created from USER COMMAND has `instruction` populated via async LLM call
- Every completed task has `completion_summary` that references instruction + final agent output
- Turn summaries are intent-aware and include task instruction context
- Empty-text turns produce no summary (None returned)
- Agent card shows instruction (line 1) + latest turn summary (line 2)
- SSE pushes instruction updates independently from turn/task summaries
- All existing tests pass with field rename (no regressions)

## Constraints and Gotchas
- **Migration ordering**: The field rename migration must run before any code referencing `completion_summary` is deployed
- **Async timing**: Instruction generation is async — the agent card may briefly show no instruction before the SSE event arrives
- **Empty text edge case**: The content pipeline (E3-S6) may not have populated turn text by the time summarisation triggers; the empty text guard handles this
- **Priority scoring**: `priority_scoring.py` reads `recent_turn.summary` (turn summary, not task summary) — this is turn-level and unchanged, but the `task_summary` variable in the scoring prompt needs updating
- **Template caching**: Flask may cache templates; server restart required after template changes
- **SSE payload backward compat**: The `task_summary` SSE event payload currently sends `summary` key — decide whether to rename to `completion_summary` in payload or keep `summary` for JS compat

## Git Change History

### Related Files
- Migrations: `c5d6e7f8a9b0_add_inference_calls_table.py`, `f8a9b0c1d2e3_add_input_text_to_inference_calls.py`
- Models: `src/claude_headspace/models/inference_call.py`
- Services: `inference_service.py`, `inference_cache.py`, `inference_rate_limiter.py`, `summarisation_service.py`, `task_lifecycle.py`, `priority_scoring.py`
- Routes: `inference.py`, `summarisation.py`, `dashboard.py`
- Templates: `logging_inference.html`, `dashboard.html`, `partials/_agent_card.html`
- Static: `static/js/logging-inference.js`, `static/js/dashboard-sse.js`
- Tests: `test_inference_service.py`, `test_inference_cache.py`, `test_inference_rate_limiter.py`, `test_summarisation_service.py`

### OpenSpec History
- `e3-s2-turn-task-summarisation` — Original summarisation capability (turn + task summaries, async processing, SSE broadcast)
- `e3-s6-content-pipeline` — Added transcript content extraction into turns (prerequisite for meaningful summaries)

### Implementation Patterns
- Typical structure: models → services → routes → templates → static JS → tests
- Async summarisation via thread pool (`summarise_*_async` methods)
- SSE broadcast pattern: service generates → broadcasts event → JS handler updates DOM
- Inference calls logged via `InferenceCall` model with level/purpose metadata

## Q&A History
- No clarification questions needed — PRD was well-specified with clear requirements and no gaps or conflicts detected

## Dependencies
- No new packages required
- Depends on existing: Flask-SQLAlchemy, Flask-Migrate (Alembic), OpenRouter API client
- Depends on E3-S6 content pipeline being deployed (already merged)

## Testing Strategy
- Unit tests for all new/modified summarisation methods (instruction generation, rebuilt prompts, empty text guards)
- Route tests for updated API response field names
- Dashboard route tests for instruction display in agent context
- Integration tests for end-to-end instruction generation flow
- Full regression pass to verify field rename doesn't break existing tests

## OpenSpec References
- proposal.md: openspec/changes/e3-s7-task-instruction-completion-summary/proposal.md
- tasks.md: openspec/changes/e3-s7-task-instruction-completion-summary/tasks.md
- spec.md (domain-models): openspec/changes/e3-s7-task-instruction-completion-summary/specs/domain-models/spec.md
- spec.md (summarisation): openspec/changes/e3-s7-task-instruction-completion-summary/specs/summarisation/spec.md
- spec.md (dashboard): openspec/changes/e3-s7-task-instruction-completion-summary/specs/dashboard/spec.md
