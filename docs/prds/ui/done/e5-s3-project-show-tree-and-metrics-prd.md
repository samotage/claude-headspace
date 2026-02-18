---
validation:
  status: valid
  validated_at: '2026-02-04T09:38:49+11:00'
---

## Product Requirements Document (PRD) — Project Show Page (Tree & Metrics)

**Project:** Claude Headspace
**Scope:** Accordion object tree (agents, tasks, turns), activity metrics, archive history, inference metrics, and SSE real-time updates for the project show page
**Sprint:** E5-S3
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft
**Depends on:** E5-S2 (Project Show Core)

---

## Executive Summary

This PRD extends the Project Show page (delivered in E5-S2) with an interactive accordion-based object tree and embedded activity metrics. The object tree allows users to drill into the full hierarchy of a project's agents, tasks, and turns — with frustration scores, inference metrics, and timing data at each level. Activity metrics (currently only on the `/activity` page) are embedded directly into the project show page with day/week/month windowing and period navigation.

Together with E5-S2, this completes the Project Show page as the canonical, comprehensive view of a project in Claude Headspace.

---

## 1. Context & Purpose

### 1.1 Context

E5-S2 delivers the project show page with metadata, controls, waypoint, brain reboot, and progress summary. However, the most data-rich aspects of a project — its agents, their tasks and turns, associated metrics, and historical activity — are not yet visible on the show page.

Currently, agent data is only visible on the dashboard (as cards in Kanban columns), command/turn data is not directly browsable in the UI at all (only via API), and activity metrics live on a separate `/activity` page. Users cannot explore a project's full operational tree from a single location.

### 1.2 Target User

Developers who want to understand a project's operational history — which agents ran, what tasks they worked on, what turns occurred, where frustration was detected — and see activity trends over time, all from the project show page.

### 1.3 Success Moment

The user opens a project's show page and expands the "Agents" accordion. They see 3 agents listed with state, priority score, and timing. They click an agent to expand its tasks — seeing 5 tasks with states and completion summaries. They click a task to see its turns with frustration scores highlighted. Below the tree, they see this week's activity chart showing turn counts and active agent hours.

---

## 2. Scope

### 2.1 In Scope

- **Accordion object tree:** Expandable/collapsible sections for the project's data hierarchy
  - Agents accordion: list of all agents (active and ended) with state, priority score, session timing
  - Commands accordion (per agent): list of tasks with state, instruction preview, completion summary, timing
  - Turns accordion (per command): list of turns with actor, intent, summary, frustration score
- **Lazy data loading:** Each accordion section fetches its data from the API when expanded (not on page load)
- **Metrics at each level:**
  - Agent level: priority score, turn count, active duration
  - Command level: state, duration, turn count
  - Turn level: frustration score (visually highlighted when elevated), actor, intent
- **Activity metrics section:** Embedded project-scoped activity metrics on the show page
  - Default to week view
  - Day/week/month toggle
  - Period navigation arrows (back/forward)
  - Turn count, average turn time, active agents, frustration aggregates
  - Time-series visualisation (matching activity page pattern)
- **Archive history section:** List of archived waypoints and other artifacts with timestamps
- **Inference metrics summary:** Aggregate inference call count, total tokens, total cost for the project
- **SSE real-time updates:** Show page listens for relevant SSE events and updates displayed data
  - Agent state changes update the agents accordion
  - Command state changes update the tasks accordion
  - New turns update the turns accordion
  - Project changes update metadata and controls
- **Tests:** Route tests for any new endpoints, JavaScript unit tests where applicable

### 2.2 Out of Scope

- Agent control actions from the show page (focus, dismiss, respond — stay on dashboard)
- Editing tasks or turns from the show page (read-only display)
- Per-project headspace monitoring (headspace is system-wide)
- Creating new agents or tasks from the show page
- Filtering or search within the accordion tree
- Exporting metrics data
- New database models or columns (all data exists)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Project show page displays an "Agents" accordion section — collapsed by default
2. Expanding the Agents section fetches and displays all agents for the project (active and ended)
3. Each agent row shows: state indicator, session UUID (truncated), priority score, started/ended timestamps, active duration
4. Clicking an agent row expands a nested "Commands" section showing that agent's tasks
5. Each command row shows: state badge, instruction (truncated), completion summary (if complete), started/completed timestamps, turn count
6. Clicking a command row expands a nested "Turns" section showing that command's turns
7. Each turn row shows: actor badge (USER/AGENT), intent, summary text, frustration score (highlighted if >= 4)
8. Activity metrics section displays below the accordion tree with week view as default
9. Day/week/month toggle switches the metrics view
10. Period navigation arrows move the window back and forward
11. Activity metrics show: turn count, average turn time, active agent count, frustration turn count
12. Activity metrics include a time-series chart (matching the activity page pattern)
13. Archive history section lists archived waypoints and artifacts with timestamps
14. Inference metrics summary shows total inference calls, tokens, and cost for the project
15. SSE events update the accordion data in real-time without page reload

### 3.2 Non-Functional Success Criteria

1. Expanding an accordion section loads data within 300ms
2. Page does not load accordion data until sections are expanded (lazy loading)
3. Accordion animations are smooth (no layout jank)
4. Vanilla JavaScript only — no external dependencies
5. All new routes and endpoints have tests

---

## 4. Functional Requirements (FRs)

### Accordion Object Tree

**FR1:** The project show page shall include an "Agents" accordion section that is collapsed by default and shows a count badge (e.g., "Agents (3)").

**FR2:** When the Agents accordion is expanded, the system shall fetch agent data from the API and display a list of all agents belonging to the project, including both active and ended agents.

**FR3:** Each agent row in the accordion shall display: state indicator (colour-coded), session UUID or identifier (truncated), priority score (0-100), started timestamp, ended timestamp (or "Active"), and calculated active duration.

**FR4:** Ended agents shall be visually distinguished from active agents (e.g., muted styling, "Ended" badge).

**FR5:** Clicking an agent row shall expand a nested Commands section within that agent, fetching the agent's tasks from the API.

**FR6:** Each command row shall display: state badge (IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE), instruction text (truncated to one line with expand option), completion summary (if state is COMPLETE), started/completed timestamps, and turn count.

**FR7:** Clicking a command row shall expand a nested Turns section within that command, fetching the command's turns from the API.

**FR8:** Each turn row shall display: actor badge (USER or AGENT, colour-coded), intent label, summary text, and frustration score.

**FR9:** Turns with a frustration score at or above the yellow threshold (configurable, default 4) shall be visually highlighted (e.g., amber background or icon).

**FR10:** Turns with a frustration score at or above the red threshold (configurable, default 7) shall be visually highlighted with a stronger indicator (e.g., red background or icon).

**FR11:** All accordion sections shall support collapse/expand toggling. Collapsing a parent collapses all nested children.

### Lazy Data Loading

**FR12:** Accordion sections shall not fetch data until the user expands them. The initial page load shall not include agent, task, or turn data.

**FR13:** While data is being fetched for an accordion section, a loading indicator shall be displayed within the section.

**FR14:** If a data fetch fails, an error message shall be displayed within the section with a "Retry" option.

**FR15:** Once data is fetched for a section, it shall be cached client-side. Collapsing and re-expanding shall not re-fetch unless the user explicitly refreshes or an SSE event invalidates the cache.

### Activity Metrics Section

**FR16:** The project show page shall include an Activity Metrics section displaying project-scoped activity data.

**FR17:** The metrics section shall default to the week (7-day) view.

**FR18:** The metrics section shall provide a toggle to switch between day, week, and month views.

**FR19:** The metrics section shall provide period navigation arrows to move the time window backward and forward (e.g., previous week / next week).

**FR20:** The forward arrow shall be disabled when viewing the current period (cannot navigate into the future).

**FR21:** The metrics section shall display summary cards showing: total turn count, average turn time, active agent count, and total frustration turn count for the selected period.

**FR22:** The metrics section shall display a time-series chart showing activity over the selected period, matching the pattern used on the `/activity` page.

### Archive History Section

**FR23:** The project show page shall include an Archive History section listing archived artifacts (waypoints, brain reboots, progress summaries) with their timestamps.

**FR24:** Each archive entry shall show the artifact type, timestamp, and a link or button to view the archived content.

**FR25:** If no archives exist, the section shall display an appropriate empty state message.

### Inference Metrics Summary

**FR26:** The project show page shall display an inference metrics summary showing aggregate data for the project: total inference calls, total input/output tokens, and total cost.

**FR27:** The inference metrics shall be scoped to the project (summing all inference calls related to the project's agents and tasks).

### SSE Real-Time Updates

**FR28:** The project show page shall connect to the SSE endpoint filtered for the current project's events.

**FR29:** When a `card_refresh` or agent state change event is received for an agent in the current project, the Agents accordion shall update if it is currently expanded.

**FR30:** When a command state change event is received, the corresponding agent's Commands section shall update if it is currently expanded.

**FR31:** When a `project_changed` or `project_settings_changed` event is received, the page header metadata shall update.

**FR32:** SSE updates shall not disrupt the user's current accordion expand/collapse state.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The project show page (with accordions collapsed) shall load within 500ms. Accordion expansion shall fetch data within 300ms.

**NFR2:** The accordion tree shall use vanilla JavaScript consistent with the existing UI pattern.

**NFR3:** Accordion expand/collapse shall use smooth CSS transitions.

**NFR4:** The activity metrics chart shall reuse the same charting approach as the `/activity` page for consistency.

**NFR5:** All new or modified routes shall have route tests following the existing test architecture.

---

## 6. UI Overview

### Accordion Object Tree

```
+-----------------------------------------------------------------------+
|                                                                        |
|  (... metadata, controls, waypoint, brain reboot from E5-S2 ...)      |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  v Agents (3)                                                          |
|  ------------------------------------------------------------------   |
|  | [green] abc-1234...  | Score: 85 | Active | Started 2h ago     |   |
|  |                                                                 |   |
|  |   v Commands (5)                                                   |   |
|  |   +-----------------------------------------------------------+|   |
|  |   | [COMPLETE] Fix auth bug          | 3 turns | 25 min       ||   |
|  |   |                                                            ||   |
|  |   |   v Turns (3)                                              ||   |
|  |   |   +------------------------------------------------------+||   |
|  |   |   | [USER]  COMMAND  "Fix the login bug"        frust: 0  |||   |
|  |   |   | [AGENT] PROGRESS "Investigating auth..."    frust: -  |||   |
|  |   |   | [USER]  ANSWER   "Yes, that file"           frust: 6  |||   |
|  |   |   +------------------------------------------------------+||   |
|  |   |                                                            ||   |
|  |   | [PROCESSING] Add caching layer   | 1 turn  | 5 min        ||   |
|  |   | > Commands (collapsed)                                        ||   |
|  |   +-----------------------------------------------------------+|   |
|  |                                                                 |   |
|  | [grey] def-5678...   | Score: -- | Ended  | 3h ago — 1h 20m    |   |
|  | > Commands (collapsed)                                             |   |
|  |                                                                 |   |
|  | [blue] ghi-9012...   | Score: 42 | Active | Started 30m ago    |   |
|  | > Commands (collapsed)                                             |   |
|  ------------------------------------------------------------------   |
|                                                                        |
+-----------------------------------------------------------------------+
```

### Activity Metrics Section

```
+-----------------------------------------------------------------------+
|                                                                        |
|  Activity Metrics                                                      |
|  ------------------------------------------------------------------   |
|                                                                        |
|  [< prev]  This Week (27 Jan - 2 Feb)  [next >]                       |
|                                                                        |
|  [Day] [Week*] [Month]                                                 |
|                                                                        |
|  +-------------+  +-------------+  +-------------+  +-------------+   |
|  | Turns       |  | Avg Time    |  | Agents      |  | Frustration |   |
|  | 142         |  | 3.2 min     |  | 4 active    |  | 8 elevated  |   |
|  +-------------+  +-------------+  +-------------+  +-------------+   |
|                                                                        |
|  [====== time series chart ======]                                     |
|  |  .    .                       |                                     |
|  | . .. ..  .    .  .            |                                     |
|  |..........  ....  ..  .   .    |                                     |
|  +-------------------------------+                                     |
|                                                                        |
+-----------------------------------------------------------------------+
```

### Archive History Section

```
+-----------------------------------------------------------------------+
|                                                                        |
|  Archive History                                                       |
|  ------------------------------------------------------------------   |
|                                                                        |
|  | Type           | Archived              | Action                 |  |
|  |----------------|-----------------------|------------------------|  |
|  | Waypoint       | 2 Feb 2026 14:30      | [View]                 |  |
|  | Waypoint       | 1 Feb 2026 09:15      | [View]                 |  |
|  | Brain Reboot   | 31 Jan 2026 16:00     | [View]                 |  |
|  | Progress       | 30 Jan 2026 11:45     | [View]                 |  |
|                                                                        |
+-----------------------------------------------------------------------+
```

### Inference Metrics Summary

```
+-----------------------------------------------------------------------+
|                                                                        |
|  Inference Usage                                                       |
|  ------------------------------------------------------------------   |
|                                                                        |
|  +------------------+  +------------------+  +------------------+     |
|  | Total Calls      |  | Total Tokens     |  | Total Cost       |     |
|  | 284              |  | 1.2M             |  | $0.47            |     |
|  +------------------+  +------------------+  +------------------+     |
|                                                                        |
+-----------------------------------------------------------------------+
```

---

## 7. Technical Context (for implementers)

### API Endpoints Used

| Endpoint | Purpose on Show Page |
|----------|---------------------|
| `GET /api/projects/<id>` | Project metadata + agents list (for accordion) |
| `GET /api/metrics/projects/<id>` | Project activity metrics (with window params) |
| `GET /api/projects/<id>/archives` | Archive history listing |
| `GET /api/inference/calls?project_id=<id>` | Inference calls for metrics summary |
| `GET /api/events/stream?project_id=<id>` | SSE stream filtered for project |

### New API Endpoints Needed

The existing `GET /api/projects/<id>` returns agents but not their tasks/turns. To support lazy-loaded accordion drill-down, the following endpoints may need to be added or extended:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/agents/<id>/commands` | List tasks for an agent (if not already available) |
| `GET /api/commands/<id>/turns` | List turns for a command (if not already available) |
| `GET /api/projects/<id>/inference-summary` | Aggregate inference metrics for project |

Check existing routes before creating new ones — the data may already be accessible through existing endpoints.

### Accordion Implementation Pattern

Use a nested structure where each level is a container that:
1. Renders a header row (always visible) with expand/collapse toggle
2. On expand: fetches data via API, renders child rows, caches result
3. Each child row can itself be an accordion container for the next level
4. Collapse hides children but preserves cached data

### Activity Metrics Pattern

Reuse the same JavaScript patterns from the `/activity` page (`static/js/activity.js`) for:
- Day/week/month toggle
- Period navigation (back/forward arrows with date range display)
- Summary card rendering
- Time-series chart rendering

### Files to Create

| File | Purpose |
|------|---------|
| `templates/partials/_project_accordion.html` | Accordion tree partial |
| `templates/partials/_project_metrics.html` | Activity metrics partial |

### Files to Modify

| File | Change |
|------|--------|
| `templates/project_show.html` | Add accordion tree, metrics, archive, inference sections |
| `static/js/project_show.js` | Add accordion logic, lazy loading, metrics, SSE handling |
| `src/claude_headspace/routes/projects.py` | Add any new API endpoints needed for drill-down |

---

## 8. Risks & Mitigation

### Risk 1: Deep Nesting Performance

**Risk:** A project with many agents, each with many tasks and turns, could result in a very large DOM when fully expanded.

**Mitigation:** Lazy loading ensures only expanded sections are in the DOM. Consider pagination or "show more" for agents/tasks with very high counts (>50 items).

### Risk 2: SSE Event Volume

**Risk:** A highly active project could generate many SSE events, causing frequent DOM updates while the user is reading.

**Mitigation:** Debounce accordion updates (e.g., batch updates every 2 seconds). Only update sections that are currently expanded.

### Risk 3: Stale Cached Accordion Data

**Risk:** Cached accordion data becomes stale if the user leaves the page open for a long time.

**Mitigation:** SSE events invalidate and refresh cached data for expanded sections. Collapsed sections re-fetch when next expanded after an SSE invalidation.

### Risk 4: Activity Chart Duplication

**Risk:** Duplicating the activity page's chart logic could lead to maintenance burden.

**Mitigation:** Extract shared charting logic into a reusable JavaScript module if not already modular. Both pages should use the same rendering code.

---

## 9. Acceptance Criteria

### Accordion Object Tree

- [ ] Agents accordion is present and collapsed by default with count badge
- [ ] Expanding Agents fetches and shows all project agents (active and ended)
- [ ] Agent rows show: state indicator, ID, priority score, timing, duration
- [ ] Ended agents are visually distinguished from active agents
- [ ] Clicking an agent expands its Commands section (lazy loaded)
- [ ] Task rows show: state badge, instruction, summary, timing, turn count
- [ ] Clicking a task expands its Turns section (lazy loaded)
- [ ] Turn rows show: actor badge, intent, summary, frustration score
- [ ] Frustration scores >= 4 are highlighted (yellow threshold)
- [ ] Frustration scores >= 7 are highlighted (red threshold)
- [ ] Loading indicators shown while fetching accordion data
- [ ] Error state with retry shown on fetch failure
- [ ] Collapsing a parent collapses nested children

### Activity Metrics

- [ ] Activity metrics section displays on the project show page
- [ ] Default view is week (7 days)
- [ ] Day/week/month toggle works
- [ ] Period navigation arrows work (back/forward)
- [ ] Forward arrow disabled when viewing current period
- [ ] Summary cards show: turn count, avg turn time, active agents, frustration count
- [ ] Time-series chart displays activity over selected period

### Archive History

- [ ] Archive section lists archived artifacts with type and timestamp
- [ ] Each archive entry has a view action
- [ ] Empty state shown when no archives exist

### Inference Metrics

- [ ] Inference summary shows total calls, tokens, and cost for the project

### SSE Real-Time Updates

- [ ] SSE connection established with project filter
- [ ] Agent state changes update expanded Agents accordion
- [ ] Command state changes update expanded Commands accordion
- [ ] Project changes update page metadata
- [ ] SSE updates don't disrupt accordion expand/collapse state
