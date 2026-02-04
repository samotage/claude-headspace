## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Agent Hero Style (Phase 2a)

- [ ] 2.1 Update card_state service to include hero characters (first 2 chars) as separate field alongside truncated UUID
- [ ] 2.2 Update dashboard route to pass hero characters in agent data
- [ ] 2.3 Update `_agent_card.html` partial: replace `#{{ agent.session_uuid }}` with hero-style markup (first 2 chars large, remainder smaller, no `#` prefix)
- [ ] 2.4 Update `_agent_card.html` card header: move active indicator and uptime to far right
- [ ] 2.5 Update `_recommended_next.html` partial: apply hero-style identity display
- [ ] 2.6 Update `project_show.html` template: apply hero-style to agent lists
- [ ] 2.7 Update `activity.js`: render agent identities with hero style (first 2 chars emphasised)
- [ ] 2.8 Update `logging.js`: render agent column cells with hero style, change filter dropdown format to `0a - 0a5510d4`
- [ ] 2.9 Update `dashboard-sse.js` `handleCardRefresh`: update hero-style rendering for dynamic card updates
- [ ] 2.10 Add CSS for hero-style identity: `.agent-hero` large text, `.agent-hero-trail` smaller text
- [ ] 2.11 Remove all `#` prefixes from agent ID displays across templates and JS

## 3. Kanban Layout (Phase 2b)

- [ ] 3.1 Update `_sort_controls.html`: add "Kanban" as first sort option, shift existing options
- [ ] 3.2 Update dashboard route: add `kanban` sort mode handling, query tasks grouped by lifecycle state
- [ ] 3.3 Create `_kanban_view.html` partial: column layout with IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE columns
- [ ] 3.4 Create `_kanban_task_card.html` partial: task card with agent hero identity, instruction/summary, metadata
- [ ] 3.5 Update `dashboard.html`: conditionally render Kanban view when sort mode is `kanban`
- [ ] 3.6 Implement Kanban data preparation in dashboard route: group agents/tasks by state, handle idle agents, handle completed tasks
- [ ] 3.7 Implement multi-project horizontal sections in Kanban view
- [ ] 3.8 Implement priority ordering within Kanban columns when prioritisation is enabled
- [ ] 3.9 Implement COMPLETE column: collapsed accordion, fixed height, independent scroll
- [ ] 3.10 Implement completed task persistence until agent reaper removes parent agent
- [ ] 3.11 Add CSS for Kanban layout: column widths, scroll containers, accordion styles
- [ ] 3.12 Update `dashboard-sse.js`: handle state transitions in Kanban view (move cards between columns)
- [ ] 3.13 Update `dashboard-sse.js`: handle `card_refresh` events for Kanban view cards
- [ ] 3.14 Update `dashboard-sse.js`: handle `session_created`/`session_ended` events for Kanban view

## 4. Activity Metrics on Dashboard (Phase 2c)

- [ ] 4.1 Create `_activity_bar.html` partial: compact horizontal metrics bar with 5 metric cards
- [ ] 4.2 Update dashboard route: fetch overall activity metrics for initial render
- [ ] 4.3 Update `dashboard.html`: include activity bar partial below menu, above state summary
- [ ] 4.4 Update `dashboard-sse.js`: listen for turn events and fetch updated metrics via `/api/metrics/overall`
- [ ] 4.5 Add CSS for dashboard activity bar: compact card styling, responsive layout

## 5. Frustration Metric Change (Phase 2d)

- [ ] 5.1 Update activity route `/api/metrics/overall` response: ensure frustration represents immediate (last 10 turns)
- [ ] 5.2 Update `activity.js`: change frustration display label to "Immediate" on overall, project, and agent sections
- [ ] 5.3 Update dashboard activity bar: display frustration as immediate (last 10 turns)

## 6. Testing (Phase 3)

- [ ] 6.1 Update existing dashboard route tests for new sort mode and data preparation
- [ ] 6.2 Add tests for Kanban data grouping logic
- [ ] 6.3 Update card_state service tests for hero character fields
- [ ] 6.4 Update logging route tests for agent filter format changes
- [ ] 6.5 Verify SSE event handling works with Kanban view (manual or E2E)

## 7. Final Verification

- [ ] 7.1 All tests passing
- [ ] 7.2 No linter errors
- [ ] 7.3 Tailwind CSS rebuilt and verified
- [ ] 7.4 Manual verification of all views: dashboard (all 3 sort modes), activity page, logging page, project detail page
