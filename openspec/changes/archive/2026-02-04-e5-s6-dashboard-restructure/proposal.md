## Why

The dashboard needs visual polish and information density improvements. Agents are identified by undifferentiated 8-character hex strings prefixed with `#`, the dashboard lacks a task-flow view that maps to how work progresses through lifecycle states, and key activity health metrics require navigating to a separate page.

## What Changes

### Agent Hero Style (FR1-FR5)
- Replace `#xxxxxxxx` agent identity with two-character hero display (first 2 chars large, remainder trailing smaller)
- Remove `#` prefix from all agent identity displays across the application
- Apply hero style consistently: dashboard cards, project detail agent lists, activity page, logging tables, logging filter dropdowns
- Logging agent filter dropdowns change format to: `0a - 0a5510d4`
- Dashboard card header reorder: active indicator moves to far right, preceded by uptime

### Kanban Layout (FR6-FR15)
- Add "Kanban" as first/default sort option in dashboard sort controls
- Display tasks organised into columns by task lifecycle state: IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE
- Idle agents (no active tasks) appear in dedicated IDLE column as current agent card representation
- Active tasks appear in column matching their lifecycle state with agent hero identity, instruction/summary, metadata
- Same agent can appear in multiple columns (one per task)
- Priority ordering within columns when prioritisation is enabled
- Multiple projects display as horizontal sections with own column sets
- Completed tasks collapse to accordion in scrollable COMPLETE column
- Completed tasks persist until parent agent is reaped

### Activity Metrics on Dashboard (FR16-FR20)
- Add overall activity metrics bar below main menu, above state summary bar
- Display: Total Turns, Turns/Hour, Avg Turn Time, Active Agents, Frustration (immediate)
- Frustration metric represents immediate frustration (last 10 turns rolling average)
- Real-time SSE updates on every turn
- Change frustration display to immediate (last 10 turns) on activity page overall, project, and agent sections

## Impact

- Affected specs: dashboard, activity, logging
- Affected code:
  - **Templates:** `templates/partials/_agent_card.html`, `templates/partials/_sort_controls.html`, `templates/partials/_project_column.html`, `templates/partials/_header.html`, `templates/partials/_recommended_next.html`, `templates/dashboard.html`, `templates/activity.html`, `templates/logging.html`, `templates/project_show.html`
  - **Routes:** `src/claude_headspace/routes/dashboard.py`, `src/claude_headspace/routes/activity.py`
  - **Services:** `src/claude_headspace/services/card_state.py`
  - **JavaScript:** `static/js/dashboard-sse.js`, `static/js/logging.js`, `static/js/activity.js`
  - **CSS:** `static/css/src/input.css`
- No model, migration, or API contract changes
- No new API endpoints (reuses existing `/api/metrics/overall`)
- Previous related changes: `e1-s8-dashboard-ui` (archived 2026-01-29), `e4-s2b-project-controls-ui` (archived 2026-02-02)
