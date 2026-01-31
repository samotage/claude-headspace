## Why

Claude Headspace's dashboard displays raw turn text and task state, forcing users to read full conversation content to understand agent activity. Turn and task summarisation will generate concise AI summaries in real-time, enabling users to grasp agent activity at a glance across all active sessions.

## What Changes

- Add TurnSummarisationService that generates 1-2 sentence summaries for new turns
- Add TaskSummarisationService that generates 2-3 sentence outcome summaries on task completion
- Add `summary` and `summary_generated_at` fields to Turn and Task models
- Add Alembic migration for new summary fields
- Add summarisation routes blueprint with POST `/api/summarise/turn/<id>` and POST `/api/summarise/task/<id>`
- Integrate with TaskLifecycleManager to trigger summarisation on turn creation and task completion
- Add SSE events for pushing summary updates to the dashboard
- Add "Summarising..." placeholder UX on agent cards while inference is in-flight
- Update dashboard route to include summary data in agent cards
- Graceful degradation when inference service is unavailable

## Impact

- Affected specs: summarisation (new capability)
- Affected code:
  - `src/claude_headspace/services/summarisation_service.py` — new: turn and task summarisation service
  - `src/claude_headspace/routes/summarisation.py` — new: API endpoints blueprint
  - `src/claude_headspace/models/turn.py` — modified: add summary + summary_generated_at fields
  - `src/claude_headspace/models/task.py` — modified: add summary + summary_generated_at fields
  - `src/claude_headspace/services/task_lifecycle.py` — modified: trigger summarisation after turn processing and task completion
  - `src/claude_headspace/routes/dashboard.py` — modified: include summary data in agent card rendering
  - `src/claude_headspace/app.py` — modified: register summarisation blueprint, init summarisation service
  - `templates/partials/_agent_card.html` — modified: display summaries and placeholders
  - `migrations/versions/` — new: migration for summary fields on turns and tasks tables
- Uses E3-S1 inference service (no changes to inference layer)
- Uses existing Broadcaster for SSE events (no changes to SSE transport)
