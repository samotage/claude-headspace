## Why

The dashboard currently shows AI-generated summaries of command instructions and completion results, but discards the full user command text and agent final message. Users cannot review complete agent responses without returning to the terminal, limiting the dashboard's utility on mobile devices and remote access scenarios.

## What Changes

- Add two new `Text` fields to the Command model: `full_command` and `full_output`
- Persist the full user command text when a command is created (during `process_turn` for USER COMMAND)
- Persist the full agent final message when a command completes (during `complete_task`)
- Add an on-demand API endpoint to fetch full text for a command (not included in SSE card_refresh payloads)
- Add drill-down UI button on dashboard agent card tooltip for instruction and completion summary lines
- Display full text in a scrollable modal/overlay, mobile-friendly (320px+ viewports)
- Show full output in the project view agent chat transcript (expandable section)

## Impact

- Affected specs: command-model, task-lifecycle, hook-receiver, dashboard-ui, project-show
- Affected code:
  - `src/claude_headspace/models/command.py` — add `full_command` and `full_output` fields
  - `migrations/versions/` — new Alembic migration for the two columns
  - `src/claude_headspace/services/command_lifecycle.py` — persist full text during create_task/complete_task
  - `src/claude_headspace/services/hook_receiver.py` — pass full command text through to command lifecycle
  - `src/claude_headspace/services/card_state.py` — no changes needed (full text excluded from card_refresh per FR10)
  - `src/claude_headspace/routes/projects.py` — add API endpoint for on-demand full text fetch; include full text in agent tasks drill-down
  - `templates/partials/_agent_card.html` — add drill-down button to instruction/completion lines
  - `static/js/dashboard.js` or `static/js/dashboard-sse.js` — JS for drill-down modal
  - `static/js/project_show.js` — show full output in task transcript view
  - `static/css/src/input.css` — modal/overlay styles (mobile-friendly)
- Related OpenSpec history: `e5-s2-project-show-core` (project view with agent/task drill-down)
