## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### New API Endpoints

- [ ] 2.1 Add `GET /api/agents/<id>/tasks` endpoint returning tasks for an agent (state, instruction, completion_summary, started_at, completed_at, turn count)
- [ ] 2.2 Add `GET /api/tasks/<id>/turns` endpoint returning turns for a task (actor, intent, summary, frustration_score, created_at)
- [ ] 2.3 Add `GET /api/projects/<id>/inference-summary` endpoint returning aggregate inference metrics (total calls, input/output tokens, total cost)

### Accordion Object Tree

- [ ] 2.4 Add Agents accordion section to `project_show.html` (collapsed by default, count badge)
- [ ] 2.5 Implement accordion expand/collapse JavaScript logic with CSS transitions in `project_show.js`
- [ ] 2.6 Implement lazy-loaded agent list: fetch on expand, render agent rows (state, ID, priority, timing, duration)
- [ ] 2.7 Distinguish active vs ended agents visually (muted styling, "Ended" badge)
- [ ] 2.8 Implement nested Tasks accordion per agent: lazy-load tasks on expand, render rows (state badge, instruction, summary, timing, turn count)
- [ ] 2.9 Implement nested Turns accordion per task: lazy-load turns on expand, render rows (actor badge, intent, summary, frustration score)
- [ ] 2.10 Highlight frustration scores: amber for >= 4 (yellow threshold), red for >= 7 (red threshold)
- [ ] 2.11 Add loading indicator while fetching accordion data
- [ ] 2.12 Add error state with retry option on fetch failure
- [ ] 2.13 Implement client-side caching: re-expanding uses cached data unless SSE invalidates
- [ ] 2.14 Collapsing a parent collapses all nested children

### Activity Metrics Section

- [ ] 2.15 Add Activity Metrics section to `project_show.html` below accordion tree
- [ ] 2.16 Implement day/week/month toggle (default: week) reusing activity.js patterns
- [ ] 2.17 Implement period navigation arrows (back/forward) with date range display
- [ ] 2.18 Disable forward arrow when viewing current period
- [ ] 2.19 Render summary cards: turn count, avg turn time, active agents, frustration turn count
- [ ] 2.20 Render time-series chart using Chart.js (bar + line pattern from activity.js)

### Archive History Section

- [ ] 2.21 Add Archive History section to `project_show.html`
- [ ] 2.22 Fetch and display archived artifacts from `GET /api/projects/<id>/archives` (type, timestamp, view action)
- [ ] 2.23 Show empty state when no archives exist

### Inference Metrics Summary

- [ ] 2.24 Add Inference Usage section to `project_show.html`
- [ ] 2.25 Fetch and display aggregate inference metrics from new endpoint (total calls, tokens, cost)

### SSE Real-Time Updates

- [ ] 2.26 Enhance SSE handling: update Agents accordion on `card_refresh` events (only if expanded)
- [ ] 2.27 SSE: update Tasks accordion on task state changes (only if expanded)
- [ ] 2.28 SSE: preserve accordion expand/collapse state during updates
- [ ] 2.29 SSE: debounce accordion updates (batch every 2 seconds)

### CSS

- [ ] 2.30 Add accordion transition styles to `static/css/src/input.css`
- [ ] 2.31 Rebuild Tailwind CSS

## 3. Testing (Phase 3)

- [ ] 3.1 Create `tests/routes/test_project_show_tree.py` with tests for new API endpoints (agent tasks, task turns, inference summary)
- [ ] 3.2 Run targeted tests: `pytest tests/routes/test_project_show_tree.py tests/routes/test_project_show.py tests/routes/test_projects.py`

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
