# Proposal Summary: e5-s3-project-show-tree-and-metrics

## Architecture Decisions
- Three-level accordion: Agents → Tasks → Turns with lazy loading (data fetched only on expand)
- Client-side data caching: re-expanding uses cached data unless SSE invalidates
- New API endpoints for drill-down: `GET /api/agents/<id>/tasks`, `GET /api/tasks/<id>/turns`, `GET /api/projects/<id>/inference-summary`
- Reuse Chart.js and activity.js patterns for metrics charts (bar + line dual-axis)
- SSE updates debounced at 2-second intervals, preserving accordion state
- Activity metrics use existing `GET /api/metrics/projects/<id>` endpoint with `window` and `since`/`until` query params
- Archive listing uses existing `GET /api/projects/<id>/archives` endpoint

## Implementation Approach
- Extend `project_show.html` template with new sections (accordion, metrics, archive, inference)
- Extend `project_show.js` with accordion logic, metrics rendering, and enhanced SSE
- Add 3 new API endpoints in `projects.py` route file
- Add CSS accordion transitions in `input.css`
- Follow existing patterns: IIFE module, vanilla JS, Tailwind CSS, Flask blueprint routes

## Files to Modify
- **Routes:** `src/claude_headspace/routes/projects.py` — add agent tasks, task turns, inference summary endpoints
- **Templates:** `templates/project_show.html` — add accordion tree, activity metrics, archive history, inference summary sections
- **JavaScript:** `static/js/project_show.js` — add accordion logic, lazy loading, metrics rendering (Chart.js), period navigation, enhanced SSE with debouncing
- **CSS:** `static/css/src/input.css` — add accordion transition styles
- **New files:**
  - `tests/routes/test_project_show_tree.py` — tests for new API endpoints

## Acceptance Criteria
- Agents accordion collapsed by default with count badge, lazy loads on expand
- Agent rows show state, ID, priority score, timing, duration; ended agents distinguished
- Clicking agent expands Tasks; clicking task expands Turns (all lazy loaded)
- Frustration scores >= 4 highlighted amber, >= 7 highlighted red
- Loading indicators on expand, error state with retry
- Collapsing parent collapses children; client-side caching
- Activity metrics section with week default, day/week/month toggle, period navigation
- Summary cards: turn count, avg turn time, active agents, frustration count
- Time-series chart matching activity page pattern
- Archive history lists artifacts with type, timestamp, view action
- Inference summary shows total calls, tokens, cost for project
- SSE updates expanded accordions without disrupting state

## Constraints and Gotchas
- Chart.js is already loaded via CDN in base.html (used by activity page) — reuse it
- Activity metrics API returns hourly buckets; JS must aggregate by day for week/month views (follow `_aggregateByDay()` pattern in activity.js)
- Accordion CSS transitions need `max-height` or `grid-template-rows` approach for smooth animation
- SSE debouncing: collect events for 2 seconds, then batch-update affected sections
- Inference summary endpoint must aggregate across all agents for a project, not just the project itself (join through Agent → InferenceCall)
- Turns may not have frustration scores (USER turns get scores, AGENT turns don't) — handle null gracefully
- Large projects could have many agents/tasks — consider showing "Show more" for lists > 50 items
- No new database models needed — all data exists in current schema
- `GET /api/projects/<id>` already returns agents list, but without task/turn detail — new endpoints provide drill-down

## Git Change History

### Related Files
- Routes: `src/claude_headspace/routes/projects.py`, `src/claude_headspace/routes/activity.py`, `src/claude_headspace/routes/archive.py`
- Templates: `templates/project_show.html`
- JavaScript: `static/js/project_show.js`, `static/js/activity.js`
- CSS: `static/css/src/input.css`
- Models: `src/claude_headspace/models/agent.py`, `src/claude_headspace/models/task.py`, `src/claude_headspace/models/turn.py`, `src/claude_headspace/models/inference_call.py`
- Tests: `tests/routes/test_project_show.py`, `tests/routes/test_projects.py`

### OpenSpec History
- `e5-s2-project-show-core` (archived 2026-02-03) — project show page with slug routing, metadata, controls, waypoint, brain reboot, progress summary
- `e4-s2b-project-controls-ui` (archived 2026-02-02) — project controls backend + UI
- `e1-s8-dashboard-ui` (archived 2026-01-29) — dashboard UI patterns
- `e2-s1-config-ui` (archived 2026-01-29) — config UI page pattern

### Implementation Patterns
- Flask blueprint route with JSON responses
- IIFE JavaScript module with namespace isolation
- Chart.js for data visualization (bar + line dual-axis)
- SSE event listeners with debounced handlers
- Lazy loading: fetch on expand, cache in JS variable
- Accordion: CSS transitions with toggle via classList
- Period navigation: offset-based calculation (same as activity.js)

## Q&A History
- No clarifications needed — PRD is clear, builds directly on E5-S2

## Dependencies
- No new packages required
- Chart.js already available (loaded in activity page)
- No database migrations needed
- Existing API endpoints: `GET /api/metrics/projects/<id>`, `GET /api/projects/<id>/archives`, `GET /api/projects/<id>` (agents list)

## Testing Strategy
- Route tests for 3 new API endpoints: agent tasks, task turns, inference summary
- Test 200/404 responses, correct data shape
- Run alongside existing project tests for regression

## OpenSpec References
- proposal.md: openspec/changes/e5-s3-project-show-tree-and-metrics/proposal.md
- tasks.md: openspec/changes/e5-s3-project-show-tree-and-metrics/tasks.md
- spec.md: openspec/changes/e5-s3-project-show-tree-and-metrics/specs/project-show-tree-and-metrics/spec.md
