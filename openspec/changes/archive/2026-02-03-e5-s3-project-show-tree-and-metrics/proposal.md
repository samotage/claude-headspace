## Why

The project show page (E5-S2) provides metadata, controls, waypoint, brain reboot, and progress summary — but the most data-rich aspects of a project (agents, tasks, turns, activity metrics, inference usage, archives) are not visible. Users cannot explore a project's full operational hierarchy or view activity trends from a single page.

## What Changes

- Add accordion object tree to project show page: agents → commands → turns with lazy loading
- Add new API endpoints: `GET /api/agents/<id>/commands`, `GET /api/commands/<id>/turns`, `GET /api/projects/<id>/inference-summary`
- Add activity metrics section with day/week/month toggle and period navigation (reusing activity.js patterns)
- Add archive history section listing archived artifacts with view action
- Add inference metrics summary showing aggregate calls, tokens, and cost
- Enhance SSE handling on project show page for real-time accordion updates
- Add CSS transitions for smooth accordion expand/collapse

## Impact

- Affected specs: project-show-core (extends), activity (reuses patterns)
- Affected code:
  - `templates/project_show.html` — add accordion tree, metrics, archive, inference sections
  - `static/js/project_show.js` — add accordion logic, lazy loading, metrics, enhanced SSE
  - `src/claude_headspace/routes/projects.py` — add agent tasks, command turns, inference summary endpoints
  - `static/css/src/input.css` — add accordion transition styles
- New files:
  - `tests/routes/test_project_show_tree.py` — tests for new API endpoints
- Prior changes: builds on `e5-s2-project-show-core` (archived 2026-02-03)
- Reuses patterns from: `static/js/activity.js` (chart rendering, period navigation), `src/claude_headspace/routes/activity.py` (metrics query pattern), `src/claude_headspace/routes/archive.py` (archive listing)
