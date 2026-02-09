## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Model & Migration

- [x] 2.1.1 Add `full_command` (Text, nullable) and `full_output` (Text, nullable) fields to `Task` model in `src/claude_headspace/models/task.py`
- [x] 2.1.2 Create Alembic migration for the two new columns

### 2.2 Backend — Capture Logic

- [x] 2.2.1 In `TaskLifecycleManager.process_turn()`, when a new task is created from a USER COMMAND, persist the full command text to `task.full_command`
- [x] 2.2.2 In `TaskLifecycleManager.complete_task()`, persist the `agent_text` parameter to `task.full_output`
- [x] 2.2.3 In `process_user_prompt_submit()` (hook_receiver.py), ensure the full `prompt_text` is passed through to `process_turn()` and subsequently stored on the task

### 2.3 Backend — API Endpoint

- [x] 2.3.1 Add `GET /api/tasks/<task_id>/full-text` endpoint in `routes/projects.py` returning `{ full_command, full_output }` on demand
- [x] 2.3.2 Ensure full text fields are NOT included in the existing `/api/agents/<id>/tasks` response (or SSE card_refresh payloads) — they are loaded on demand only

### 2.4 Frontend — Dashboard Drill-down

- [x] 2.4.1 Add "View full" drill-down button to the instruction line (03) tooltip in `_agent_card.html`
- [x] 2.4.2 Add "View full" drill-down button to the completion summary line (04) tooltip in `_agent_card.html`
- [x] 2.4.3 Create a scrollable modal/overlay component for displaying full text (vanilla JS)
- [x] 2.4.4 Wire drill-down buttons to fetch `/api/tasks/<id>/full-text` and display in modal
- [x] 2.4.5 Add modal/overlay CSS to `static/css/src/input.css` with mobile viewport support (320px+)

### 2.5 Frontend — Project View Transcript

- [x] 2.5.1 Add expandable "Full output" section to the task card in `project_show.js` `_renderTasksList()`
- [x] 2.5.2 Wire expand/collapse to fetch `/api/tasks/<id>/full-text` on demand

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for Task model new fields (test field creation, nullable behavior)
- [x] 3.2 Unit tests for `TaskLifecycleManager.process_turn()` — verify `full_command` is persisted
- [x] 3.3 Unit tests for `TaskLifecycleManager.complete_task()` — verify `full_output` is persisted
- [x] 3.4 Route tests for `GET /api/tasks/<id>/full-text` endpoint (happy path, 404, empty fields)
- [x] 3.5 Verify `/api/agents/<id>/tasks` does NOT include `full_command` or `full_output`
- [x] 3.6 Verify SSE card_refresh events do NOT include full text fields

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Migration runs cleanly on test database
- [ ] 4.4 Manual verification: create a task, complete it, drill down from dashboard
