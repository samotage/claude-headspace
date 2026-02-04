# Proposal Summary: e5-s6-dashboard-restructure

## Architecture Decisions
- Pure display/layout changes — no model, migration, or API contract changes
- Kanban view implemented as a third sort mode alongside existing "project" and "priority" views
- Hero style identity computed server-side (card_state + dashboard route) and rendered via Jinja2 markup + CSS
- Dashboard activity bar fetches initial data server-side, then updates via SSE-triggered AJAX to existing `/api/metrics/overall`
- Frustration metric change is a display concern — existing data (frustration_score per turn) is already available; just change which aggregation is shown

## Implementation Approach
- **Hero style:** Add `hero_chars` (first 2) and `hero_trail` (remaining 6) fields to card state dict. Create CSS classes for large/small rendering. Update all templates and JS that reference agent identity.
- **Kanban:** Add `kanban` sort mode to dashboard route. Group tasks by lifecycle state. Create new partials for Kanban columns and task cards. Reuse existing agent cards in IDLE column. SSE updates move cards between columns by re-rendering or DOM manipulation.
- **Activity bar:** Create compact metrics partial. Include in dashboard.html between header and state summary. SSE turn events trigger fetch of `/api/metrics/overall` to refresh values.
- **Frustration:** Change displayed frustration to use immediate (last 10 turns) rolling average. This is already computed by HeadspaceMonitor as `frustration_rolling_10`.

## Files to Modify

### Templates (Jinja2)
- `templates/partials/_agent_card.html` — hero style identity, card header reorder (active indicator + uptime to far right)
- `templates/partials/_sort_controls.html` — add "Kanban" as first sort option
- `templates/partials/_project_column.html` — minor adjustments for hero style
- `templates/partials/_header.html` — no changes needed (activity bar goes in dashboard.html, not header)
- `templates/partials/_recommended_next.html` — hero style identity
- `templates/dashboard.html` — add activity bar, conditionally render Kanban view
- `templates/activity.html` — frustration label change to "Immediate"
- `templates/logging.html` — no template changes (agent display is JS-driven)
- `templates/project_show.html` — hero style for agent lists

### New Templates
- `templates/partials/_activity_bar.html` — compact metrics bar partial
- `templates/partials/_kanban_view.html` — Kanban column layout per project
- `templates/partials/_kanban_task_card.html` — task card for Kanban columns

### Routes (Python)
- `src/claude_headspace/routes/dashboard.py` — add `kanban` sort mode, prepare Kanban data (group tasks by state), fetch overall activity metrics

### Services (Python)
- `src/claude_headspace/services/card_state.py` — add `hero_chars` and `hero_trail` to card state dict

### JavaScript
- `static/js/dashboard-sse.js` — handle Kanban view updates (card movement between columns), activity bar SSE updates, hero style in card_refresh handler
- `static/js/logging.js` — hero style in agent table cells, filter dropdown format `0a - 0a5510d4`
- `static/js/activity.js` — hero style for agent identity, frustration label change

### CSS
- `static/css/src/input.css` — hero style classes (`.agent-hero`, `.agent-hero-trail`), Kanban column layout, Kanban task card, activity bar compact styling, COMPLETE column scroll + accordion

## Acceptance Criteria
1. Agents displayed with 2-char hero identity (large) + trailing chars (small) in all views
2. No `#` prefix on any agent ID display
3. Kanban view is first/default sort option
4. Tasks appear in correct lifecycle state columns
5. Idle agents in IDLE column, completed tasks as accordions in scrollable COMPLETE column
6. Completed tasks persist until agent reaped
7. Priority ordering within Kanban columns when enabled
8. Multi-project horizontal sections in Kanban view
9. Activity metrics bar on dashboard with real-time SSE updates
10. Frustration = immediate (last 10 turns) on dashboard and activity page

## Constraints and Gotchas
- **Sort mode persistence:** Existing localStorage key `claude_headspace_sort_mode` needs to handle the new `kanban` value. When Kanban becomes default, first-time users with no localStorage value should see Kanban.
- **Full page reload on sort change:** Current sort switching does a full page reload via URL param. This pattern should be maintained for Kanban.
- **card_refresh SSE event:** The `handleCardRefresh` function in `dashboard-sse.js` is the authoritative card update mechanism. It needs to handle both the traditional card view AND the Kanban view. When in Kanban mode, a card_refresh may need to move a task card between columns if the state changed.
- **session_created/session_ended:** These events currently trigger full page reloads. This should continue working for Kanban view.
- **Agent UUID sources:** The dashboard route truncates to 8 chars at line 285, and card_state service does the same at line 372. Both need `hero_chars`/`hero_trail` fields added.
- **Logging filter API:** The `/api/events/filters` endpoint returns full UUIDs (logging.py line 234). The JS truncates client-side to 8 chars (logging.js lines 226-229). The filter format change is purely client-side.
- **Activity metrics API:** `/api/metrics/overall` already returns `frustration_avg` and `frustration_turn_count`. For immediate frustration (last 10 turns), we may need to add a separate field or compute it differently. HeadspaceMonitor already tracks `frustration_rolling_10` in HeadspaceSnapshot — this can be exposed via the headspace API.
- **Tailwind rebuild required:** After CSS changes to `input.css`, must rebuild with `npx tailwindcss -i static/css/src/input.css -o static/css/main.css`.
- **Pre-existing issue:** Project column template has 3 state dots but JS expects 4. This is unrelated to this PRD.

## Git Change History

### Related Files
- Config/docs: `docs/prds/ui/done/e2-s1-config-ui-prd.md`, various OpenSpec archives for UI changes
- Recent dashboard-related commits: `ad57e998` (card_refresh SSE), `d55def2d` (TIMED_OUT display), `42904621` (IDLE green)

### OpenSpec History
- `e1-s8-dashboard-ui` (archived 2026-01-29) — initial dashboard UI
- `e2-s1-config-ui` (archived 2026-01-29) — config page UI
- `e4-s2b-project-controls-ui` (archived 2026-02-02) — project controls

### Implementation Patterns
- Template partials pattern: create `_partial_name.html` in `templates/partials/`
- Route pattern: add sort mode handling in dashboard route, prepare data dict, pass to template
- SSE pattern: register event handlers in `dashboard-sse.js`, update DOM via `querySelector`
- CSS pattern: add custom classes to `static/css/src/input.css`, rebuild Tailwind

## Q&A History
- No clarification questions needed — PRD is clear and internally consistent
- No conflicts with existing codebase detected

## Dependencies
- No new packages or dependencies required
- No database migrations needed
- No external services involved
- Reuses existing `/api/metrics/overall` endpoint and HeadspaceMonitor data

## Testing Strategy
- Update existing dashboard route tests for new `kanban` sort mode
- Add tests for Kanban data grouping logic (tasks by state, idle agents, multi-project)
- Update card_state service tests for `hero_chars`/`hero_trail` fields
- Update logging tests for filter dropdown format
- Manual verification of all views across sort modes
- Verify SSE real-time updates work with Kanban view

## OpenSpec References
- proposal.md: openspec/changes/e5-s6-dashboard-restructure/proposal.md
- tasks.md: openspec/changes/e5-s6-dashboard-restructure/tasks.md
- spec.md: openspec/changes/e5-s6-dashboard-restructure/specs/dashboard/spec.md
