# Proposal Summary: e5-s9-full-command-output-capture

## Architecture Decisions
- Store full text on the Task model (not Turn) — the PRD treats this as task-level data
- Use `Text` column type (no character limit) per NFR1
- Capture at existing lifecycle points: `process_turn()` for command, `complete_task()` for output
- Serve full text via a dedicated on-demand API endpoint (not in SSE payloads or task list responses)
- Dashboard drill-down uses a vanilla JS modal/overlay consistent with existing UI patterns
- Project view uses expandable accordion pattern consistent with existing task card rendering

## Implementation Approach
- Minimal backend changes: two new fields on Task model, capture at two existing lifecycle methods
- The full command text is already available in `process_turn()` as the `text` parameter (line 324/370 of task_lifecycle.py)
- The full agent output is already available in `complete_task()` as the `agent_text` parameter (line 253/288 of task_lifecycle.py)
- No changes needed to card_state.py — full text is intentionally excluded from `build_card_state()`
- New endpoint `/api/tasks/<id>/full-text` returns both fields on demand
- Frontend fetches on click/expand, not on initial page load

## Files to Modify

### Models
- `src/claude_headspace/models/task.py` — add `full_command` and `full_output` Text fields

### Migrations
- `migrations/versions/` — new Alembic migration adding two nullable Text columns to `tasks` table

### Services
- `src/claude_headspace/services/task_lifecycle.py` — persist full text in `process_turn()` and `complete_task()`
- No changes to `hook_receiver.py` — it already passes `prompt_text` to `process_turn()` and `agent_text` to `complete_task()`
- No changes to `card_state.py` — full text deliberately excluded from SSE payloads
- No changes to `summarisation_service.py` — summarisation pipeline unchanged

### Routes
- `src/claude_headspace/routes/projects.py` — add `GET /api/tasks/<id>/full-text` endpoint

### Frontend
- `templates/partials/_agent_card.html` — add drill-down buttons on lines 03 (instruction) and 04 (completion summary)
- `static/js/dashboard-sse.js` — JS handler for drill-down modal (fetch + display)
- `static/js/project_show.js` — expandable full output in task transcript cards (line ~450-475)
- `static/css/src/input.css` — modal overlay styles, mobile-responsive

## Acceptance Criteria
- Every task with a user command has `full_command` persisted
- Every completed task has `full_output` persisted (when agent text is available)
- Dashboard drill-down button shows full text in scrollable modal
- Project view transcript shows expandable full output
- Full text NOT in SSE card_refresh payloads
- Full text NOT in `/api/agents/<id>/tasks` response
- Modal/overlay usable on 320px+ mobile viewports
- Existing summary display unchanged

## Constraints and Gotchas
- `complete_task()` is called from multiple places (hook:stop, hook:session_end, user:new_command auto-complete) — `full_output` should be set for all paths that have `agent_text`
- Session end forced-completion often has no `agent_text` (line 525 of hook_receiver.py) — `full_output` will be NULL for these, which is acceptable
- Deferred stop (background transcript extraction) also calls `complete_task()` with extracted text — this path already passes `agent_text`
- The `_extract_transcript_content()` function reads from transcript files and returns the agent's last message — this is what gets stored as `full_output`
- The `prompt_text` in `process_user_prompt_submit()` comes from the hook payload and contains the full user command — this is what gets stored as `full_command`
- The existing `instruction` and `completion_summary` fields remain AI-generated summaries — they are NOT affected by this change

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/task.py` (Task model with instruction, completion_summary fields)
- Services: `src/claude_headspace/services/task_lifecycle.py` (TaskLifecycleManager)
- Services: `src/claude_headspace/services/hook_receiver.py` (HookReceiver with stop/user_prompt handling)
- Services: `src/claude_headspace/services/card_state.py` (build_card_state, broadcast_card_refresh)
- Services: `src/claude_headspace/services/summarisation_service.py` (SummarisationService)
- Routes: `src/claude_headspace/routes/projects.py` (agent tasks API, task turns API)
- Templates: `templates/partials/_agent_card.html` (dashboard agent card)
- JS: `static/js/dashboard-sse.js` (SSE event handlers, card rendering)
- JS: `static/js/project_show.js` (project view with agent/task/turn drill-down)

### OpenSpec History
- `e5-s2-project-show-core` (2026-02-03) — project show page with agent/task drill-down

### Implementation Patterns
- Model changes follow existing pattern: `Mapped[str | None] = mapped_column(Text, nullable=True)`
- API endpoints follow existing pattern in `routes/projects.py` (JSON responses with error handling)
- Frontend modals should use vanilla JS (no framework dependencies)
- CSS uses Tailwind utilities in `input.css`, compiled to `main.css`

## Q&A History
- No clarifications needed — PRD is complete and consistent

## Dependencies
- No new packages required
- No external services
- One database migration (two new nullable Text columns)

## Testing Strategy
- Unit tests for Task model field persistence
- Unit tests for `process_turn()` full_command capture
- Unit tests for `complete_task()` full_output capture
- Route tests for the new `/api/tasks/<id>/full-text` endpoint
- Negative tests: verify full text excluded from card_refresh and agent tasks API
- No E2E tests needed for this scope (modal UI testing is visual)

## OpenSpec References
- proposal.md: openspec/changes/e5-s9-full-command-output-capture/proposal.md
- tasks.md: openspec/changes/e5-s9-full-command-output-capture/tasks.md
- spec.md: openspec/changes/e5-s9-full-command-output-capture/specs/task-model/spec.md
