---
validation:
  status: valid
  timestamp: "2026-02-04"
  estimated_tasks: 23
---

## Product Requirements Document (PRD) — Dashboard Restructure

**Project:** Claude Headspace
**Scope:** Agent hero identity, Kanban task layout, dashboard activity metrics
**Author:** samotage
**Status:** Valid

---

## Executive Summary

The Claude Headspace dashboard is maturing and requires polish to make it more intuitive and information-dense. This PRD covers three complementary improvements: a distinctive "hero style" agent identity system, a task-based Kanban layout, and surfacing real-time activity metrics directly on the dashboard.

The agent hero style replaces the current `#xxxxxxxx` identifier with a two-character prominent display (e.g., "0A") that makes agents instantly recognizable across all views — dashboard, projects, activity, and logging. The Kanban layout introduces a universally understood task-flow view organised by task lifecycle state, replacing the current agent-centric card layout as the default view. Activity metrics from the overall section of the activity page are surfaced on the dashboard with real-time SSE updates, putting system health at a glance without navigation.

These changes are display and layout refinements — no changes to underlying models, state machine, or API contracts.

---

## 1. Context & Purpose

### 1.1 Context
The dashboard currently displays agents as cards identified by an 8-character truncated UUID with a `#` prefix. While functional, agents lack visual personality and are hard to distinguish at a glance. The current sort modes (By Project, By Priority) show agent-centric views, but lack a task-flow perspective that maps to how work actually progresses through the system. Key activity health metrics require navigating to a separate page.

### 1.2 Target User
Developers and operators monitoring multiple Claude Code sessions across projects who need to quickly identify agents, understand task flow, and assess system health.

### 1.3 Success Moment
A user opens the dashboard, immediately sees activity health metrics, scans the Kanban columns to understand where work is flowing, and recognises agents by their two-character hero identity without needing to read full UUIDs.

---

## 2. Scope

### 2.1 In Scope
- Agent hero style identity display (two-character emphasis, trailing smaller characters)
- Hero style applied across all views: dashboard cards, project agent lists, activity page agent sections, logging event/inference tables, logging agent filter dropdowns
- Active indicator repositioned to far right of card header, preceded by uptime
- New "Kanban" sort option as the first/default sort mode
- Task-based Kanban columns organised by task lifecycle state
- Idle agents column for agents without active tasks
- Completed tasks rendered as collapsed accordions in a scrollable COMPLETE column
- Completed tasks retained until parent agent is reaped
- Priority-based ordering within Kanban columns when prioritisation is enabled
- Horizontal project sections in Kanban view when multiple projects are active
- Same agent can appear in multiple Kanban columns (one per task)
- Overall activity metrics bar on dashboard (below menu, above state summary)
- Real-time SSE updates for dashboard activity metrics on every turn
- Frustration metric changed to immediate (last 10 turns) on dashboard and activity page (overall, project, and agent sections)
- Agent filter dropdown format changed to: `0a - 0a5510d4`

### 2.2 Out of Scope
- Changes to task lifecycle states or state machine logic
- New API endpoints (reuse existing activity/metrics endpoints)
- Changes to SSE event structure (use existing event types)
- Agent model or database schema changes
- Priority scoring algorithm changes
- Historical completed task browsing beyond what persists in Kanban (use project detail page for full history)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria
1. Agents are displayed with two-character hero identity (first two hex characters large, remainder trailing smaller) in all views where agents are referenced
2. The `#` prefix is removed from all agent ID displays
3. Kanban view is available as a sort option and is the first/default option
4. Tasks appear in the correct lifecycle state column in the Kanban view
5. Idle agents appear in a dedicated IDLE column
6. Completed tasks collapse to an accordion in a scrollable COMPLETE column
7. Completed tasks persist until their parent agent is reaped
8. Priority ordering applies within Kanban columns when prioritisation is enabled
9. Multiple projects display as horizontal sections in the Kanban view
10. Overall activity metrics are visible on the dashboard below the menu bar
11. Dashboard activity metrics update in real-time via SSE
12. Frustration metric represents immediate frustration (last 10 turns) on both dashboard and activity page

### 3.2 Non-Functional Success Criteria
1. Dashboard remains responsive and usable on smaller viewports
2. Kanban view renders without perceptible delay for up to 20 concurrent tasks across projects

---

## 4. Functional Requirements (FRs)

### Agent Hero Style

**FR1:** Agent identity displays the first two characters of the session UUID prominently (large text) with the remaining characters rendered smaller trailing behind the prominent characters.

**FR2:** The `#` prefix is removed from all agent identity displays across the application.

**FR3:** The agent hero style is applied consistently across: dashboard agent cards, project detail agent lists, activity page agent/project sections, logging event table agent column, logging inference table agent column.

**FR4:** Logging agent filter dropdowns (events and inference) display agents in the format: `0a - 0a5510d4` (hero characters, separator, full truncated UUID).

**FR5:** On dashboard agent cards, the active indicator moves to the far right of the card header, preceded by the uptime display.

### Kanban Layout

**FR6:** A new "Kanban" sort option is added to the dashboard sort controls, positioned as the first option in the list.

**FR7:** The Kanban view displays tasks organised into columns by task lifecycle state: IDLE, COMMANDED, PROCESSING, AWAITING_INPUT, COMPLETE.

**FR8:** Agents without active tasks appear in the IDLE column, displayed as their current agent card representation.

**FR9:** When an agent has an active task, that task appears in the column matching its current lifecycle state. The task card displays the agent hero identity, task instruction/summary, and relevant task metadata.

**FR10:** The same agent can appear in multiple columns simultaneously if it has tasks in different states.

**FR11:** When prioritisation is enabled, tasks within each Kanban column are ordered by their agent's priority score (highest first).

**FR12:** When multiple projects have active agents, the Kanban view displays horizontal sections for each project, with each section containing its own set of state columns.

**FR13:** Completed tasks in the COMPLETE column render as collapsed accordions showing the agent hero identity and task completion summary. The accordion can be expanded to reveal full task details.

**FR14:** The COMPLETE column has a fixed height and scrolls independently to accommodate accumulated completed tasks.

**FR15:** Completed tasks remain in the COMPLETE column until their parent agent is reaped by the agent reaper.

### Activity Data on Dashboard

**FR16:** The dashboard displays overall activity metrics in a bar positioned below the main menu and above the state summary bar (INPUT NEEDED / WORKING / IDLE counts).

**FR17:** The activity metrics displayed are: Total Turns, Turns/Hour, Avg Turn Time, Active Agents, and Frustration (immediate).

**FR18:** The frustration metric on the dashboard represents immediate frustration (rolling average of the last 10 turns).

**FR19:** Dashboard activity metrics update in real-time via SSE whenever a turn is recorded.

**FR20:** The activity page overall section, project sections, and agent sections all change their frustration display to represent immediate frustration (last 10 turns) instead of averaged frustration.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The Kanban view renders and updates without layout shift when tasks transition between columns via SSE updates.

**NFR2:** The dashboard remains functional and readable on viewports down to tablet width (768px).

---

## 6. UI Overview

### Agent Hero Style
Each agent is identified by its first two hex characters rendered at prominent size (e.g., "0A"), with the remaining characters of the truncated UUID displayed smaller, trailing behind. This replaces the current `#0a5510d4` format. The hero style appears everywhere agents are referenced — cards, tables, filters, and lists.

### Dashboard Card Header (Updated)
The card header reorders to: Agent Hero Identity (left), then project name, with uptime and active indicator pushed to the far right.

### Kanban View
The default dashboard view shows vertical columns for each task lifecycle state. Each column is headed by the state name. Task cards within columns show the agent hero, task instruction or summary, and state-relevant information. The IDLE column contains full agent cards for agents not currently working on tasks. The COMPLETE column is scrollable with accordion-collapsed task cards. When multiple projects are active, each project gets its own horizontal band with its own set of columns.

### Activity Metrics Bar
A compact horizontal bar of metric cards sits between the navigation menu and the state summary counts. Cards match the style of the activity page overall section: Total Turns, Turns/Hour, Avg Turn Time, Active Agents, Frustration (immediate). Values update in real-time.

### Logging Filter Dropdowns
Agent filter options display as: `0a - 0a5510d4` — the two-character hero followed by a dash and the full truncated UUID for disambiguation.
