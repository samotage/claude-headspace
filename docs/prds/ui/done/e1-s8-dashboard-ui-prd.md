---
validation:
  status: valid
  validated_at: '2026-01-29T10:24:41+11:00'
---

## Product Requirements Document (PRD) — Dashboard UI Core

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 8 — Core dashboard layout, agent cards, and state visualization
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

The Dashboard UI is the primary user interface for Claude Headspace, providing a real-time visual command center for monitoring multiple Claude Code agents across projects. This PRD covers the **core dashboard structure**: the main layout, header bar with status counts, project groups with traffic light indicators, and agent cards with state visualization.

The dashboard reduces context-switching overhead by surfacing agent states at a glance. Users can see which agents need input, which are working, and which are idle—without manually checking each terminal window. The Kanban-style layout groups agents by project, matching the mental model of developers working across multiple codebases.

This is Part 1 of 2 PRDs for Sprint 8. Part 2 (e1-s8b-dashboard-interactivity-prd.md) covers the interactivity layer: recommended next panel, sort controls, SSE real-time updates, and click-to-focus integration.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace monitors Claude Code sessions across multiple projects. Sprints 1-7 established the foundational architecture: Flask application, Postgres database, domain models (Agent, Task, Turn), file watcher, event system, state machine, and SSE real-time transport.

Sprint 8 delivers the user-facing dashboard that makes this infrastructure visible and actionable. Without a dashboard, users must manually track agent states across terminal windows—defeating the purpose of the monitoring system.

### 1.2 Target User

Developers using Claude Code across multiple projects simultaneously. They need:
- At-a-glance visibility of all agent states
- Quick identification of agents needing attention (awaiting input)
- Project-based organization matching their workflow

### 1.3 Success Moment

The user opens the dashboard and immediately sees:
- How many agents need input (orange badge in header)
- Which projects have agents requiring attention (red traffic light)
- The specific agent card showing "Input needed" with its current question

They click the card and focus shifts to the correct iTerm window.

---

## 2. Scope

### 2.1 In Scope

**Dashboard Route & Layout:**
- Flask route serving the dashboard page
- Kanban-style layout with project groups
- Dark terminal aesthetic (consistent with base template)

**Header Bar:**
- Application title and navigation tabs (dashboard, objective, logging)
- Status counts: INPUT NEEDED, WORKING, IDLE
- Hooks/polling status indicator

**Project Groups:**
- Project header with name and active agent count
- Traffic light indicator (red/yellow/green based on agent states)
- Collapsible project sections
- Waypoint preview section (read-only display)

**Agent Cards:**
- Session ID (truncated UUID)
- Status badge (ACTIVE/IDLE based on `last_seen_at` recency)
- Uptime display (time since `started_at`)
- State bar with colour coding (5 states)
- Task summary (current task description or "No active task")
- Priority score badge (displays value; default 50 in Epic 1)
- "Headspace" button placeholder (wired up in Part 2)

**State Visualization:**
- Colour-coded state bars per TaskState enum:
  - IDLE: Grey
  - COMMANDED: Yellow
  - PROCESSING: Blue
  - AWAITING_INPUT: Orange
  - COMPLETE: Green

**Responsive Layout:**
- Mobile (≥320px): Single column, stacked cards
- Tablet (≥768px): Two-column layout
- Desktop (≥1024px): Multi-column with sidebar potential
- Touch targets minimum 44px for iOS compatibility

### 2.2 Out of Scope

- Recommended next panel (Part 2)
- Sort controls (Part 2)
- SSE real-time updates / live refresh (Part 2)
- Click-to-focus iTerm integration (Part 2)
- Config tab UI (Epic 2)
- Help tab (Later)
- Priority scoring logic / LLM inference (Epic 3)
- Waypoint editing (Objective Tab)
- Dark/light theme toggle (dark only)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| SC1 | Dashboard route (`/` or `/dashboard`) returns 200 and renders template | HTTP GET returns 200, HTML contains expected structure |
| SC2 | All projects from database displayed as groups | Count of project groups matches `SELECT COUNT(*) FROM projects` |
| SC3 | All agents displayed within their project groups | Count of agent cards matches `SELECT COUNT(*) FROM agents WHERE project_id = ?` per project |
| SC4 | Header status counts accurate | INPUT NEEDED = agents with `AWAITING_INPUT`, WORKING = `COMMANDED` + `PROCESSING`, IDLE = `IDLE` + `COMPLETE` |
| SC5 | Traffic lights reflect project state | Red if any agent `AWAITING_INPUT`, yellow if any `COMMANDED`/`PROCESSING`, green otherwise |
| SC6 | Agent cards display all required fields | Session ID, status, uptime, state bar, task summary, priority visible |
| SC7 | State bars colour-coded correctly | 5 distinct colours matching TaskState enum values |
| SC8 | Project sections collapsible | Click collapse → agents hidden, click expand → agents visible |
| SC9 | Responsive on mobile | Layout readable and usable at 320px viewport width |
| SC10 | Responsive on tablet | Two-column layout at 768px viewport width |
| SC11 | Responsive on desktop | Multi-column layout at 1024px+ viewport width |

### 3.2 Non-Functional Success Criteria

| # | Criterion | Target |
|---|-----------|--------|
| NFR1 | Initial page load time | < 2 seconds with 10 projects, 50 agents |
| NFR2 | Database queries per page load | ≤ 5 queries (avoid N+1) |
| NFR3 | Touch target size | ≥ 44px for interactive elements |
| NFR4 | Accessibility | Semantic HTML, ARIA labels for state indicators |

---

## 4. Functional Requirements (FRs)

### Dashboard Route

**FR1:** The application provides a dashboard route at `/` (root) that serves the dashboard page.

**FR2:** The dashboard route queries the database for all projects and their associated agents, including current task state for each agent.

**FR3:** The dashboard route calculates status counts (INPUT NEEDED, WORKING, IDLE) from agent states before rendering.

### Header Bar

**FR4:** The header bar displays the application title "CLAUDE >_headspace" with terminal aesthetic styling.

**FR5:** The header bar displays navigation tabs: dashboard (active), objective, logging. Tabs link to their respective routes.

**FR6:** The header bar displays status count badges:
- INPUT NEEDED: Count of agents where `state = AWAITING_INPUT`
- WORKING: Count of agents where `state IN (COMMANDED, PROCESSING)`
- IDLE: Count of agents where `state IN (IDLE, COMPLETE)`

**FR7:** The header bar displays a hooks/polling indicator showing current monitoring mode (placeholder text until Part 2 SSE integration).

### Project Groups

**FR8:** Each project is displayed as a collapsible group section with a header row.

**FR9:** The project header displays:
- Traffic light indicator (coloured dot)
- Project name
- Active agent count (agents where `last_seen_at` within configured timeout)

**FR10:** Traffic light colour is determined by:
- Red: Any agent in project has `state = AWAITING_INPUT`
- Yellow: Any agent in project has `state IN (COMMANDED, PROCESSING)` and none `AWAITING_INPUT`
- Green: All agents have `state IN (IDLE, COMPLETE)`

**FR11:** Project sections can be collapsed/expanded by clicking the header. Collapsed state hides agent cards within.

**FR12:** Each project group displays a waypoint preview section showing the project's waypoint summary (if available) in read-only format.

### Agent Cards

**FR13:** Each agent is displayed as a card within its project group.

**FR14:** Agent cards display the session ID as a truncated UUID (first 8 characters with # prefix, e.g., "#2e3fe060").

**FR15:** Agent cards display a status badge:
- "ACTIVE" (green): `last_seen_at` within 5 minutes
- "IDLE" (grey): `last_seen_at` older than 5 minutes

**FR16:** Agent cards display uptime as human-readable duration since `started_at` (e.g., "up 32h 38m").

**FR17:** Agent cards display a state bar with colour and label matching the current TaskState:
- IDLE: Grey bar, "Idle - ready for task"
- COMMANDED: Yellow bar, "Command received"
- PROCESSING: Blue bar, "Processing..."
- AWAITING_INPUT: Orange bar, "Input needed"
- COMPLETE: Green bar, "Task complete"

**FR18:** Agent cards display a task summary:
- If current task exists: First 100 characters of most recent turn text
- If no current task: "No active task"

**FR19:** Agent cards display a priority score badge showing numeric value (default 50 for all agents in Epic 1).

**FR20:** Agent cards include a "Headspace" button (placeholder in Part 1, wired to focus API in Part 2).

### Responsive Layout

**FR21:** On mobile viewports (< 768px), agent cards stack in a single column. Project groups take full width.

**FR22:** On tablet viewports (768px - 1023px), agent cards display in a two-column grid within each project group.

**FR23:** On desktop viewports (≥ 1024px), agent cards display in a multi-column grid (3+ columns based on available width).

**FR24:** All interactive elements (buttons, collapse toggles) have minimum touch target size of 44x44 pixels.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The dashboard page loads within 2 seconds for a dataset of 10 projects with 50 total agents.

**NFR2:** Database queries are optimized to avoid N+1 patterns. Use eager loading for project→agents→tasks relationships.

**NFR3:** The dashboard uses semantic HTML elements (`<header>`, `<main>`, `<section>`, `<article>`) for accessibility.

**NFR4:** State indicators (traffic lights, state bars) include ARIA labels describing the state for screen readers.

**NFR5:** The dashboard follows the existing dark terminal aesthetic established in `templates/base.html` (colours: `bg-void`, `text-primary`).

---

## 6. UI Overview

### Header Bar Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE >_headspace   [dashboard]  [objective]  [logging]                │
├─────────────────────────────────────────────────────────────────────────┤
│ INPUT NEEDED [0]    WORKING [2]    IDLE [7]    ● HOOKS polling          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Project Group Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ● project-name                                              [3 active]  │
│ [▼]                                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ ▶ Waypoint: Next up - implement dashboard...                   [Edit]   │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐            │
│ │  Agent Card 1   │ │  Agent Card 2   │ │  Agent Card 3   │            │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Agent Card Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ● ACTIVE  #2e3fe060                                    up 32h 38m       │
├─────────────────────────────────────────────────────────────────────────┤
│ ████████████████████████████████████████  Processing...                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Working on implementing the dashboard UI component...                   │
├─────────────────────────────────────────────────────────────────────────┤
│ [50]                                                     [Headspace]    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Mobile Layout (Single Column)

```
┌──────────────────────┐
│ CLAUDE >_headspace   │
│ [≡] Menu             │
├──────────────────────┤
│ INPUT [0] WORK [2]   │
│ IDLE [7]             │
├──────────────────────┤
│ ● project-name [3]   │
├──────────────────────┤
│ ┌──────────────────┐ │
│ │  Agent Card 1    │ │
│ └──────────────────┘ │
│ ┌──────────────────┐ │
│ │  Agent Card 2    │ │
│ └──────────────────┘ │
└──────────────────────┘
```

---

## 7. Tech Context (Implementation Guidance)

This section provides technical context for implementers. These are not requirements but guidance on patterns and constraints.

**Tech Stack:**
- Tailwind CSS for styling (build pipeline already configured)
- HTMX for collapse/expand interactivity (no page reload)
- Jinja2 templates extending `base.html`

**Existing Patterns:**
- Base template uses: `bg-void`, `text-primary`, `font-mono`
- Extend from `templates/base.html`
- Follow Flask blueprint pattern for routes

**Database Models Available:**
- `Project`: `id`, `name`, `path`, `agents` relationship
- `Agent`: `id`, `session_uuid`, `project_id`, `iterm_pane_id`, `started_at`, `last_seen_at`, `state` property, `tasks` relationship
- `Task`: `id`, `agent_id`, `state` (TaskState enum), `turns` relationship
- `Turn`: `id`, `task_id`, `actor`, `intent`, `text`, `timestamp`
- `TaskState`: `IDLE`, `COMMANDED`, `PROCESSING`, `AWAITING_INPUT`, `COMPLETE`

**Query Optimization:**
- Use `joinedload()` or `selectinload()` for eager loading relationships
- Single query pattern: `Project.query.options(selectinload(Project.agents).selectinload(Agent.tasks))`

---

## 8. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| Sprint 7: SSE System | Soft | Dashboard renders without SSE; Part 2 adds live updates |
| Sprint 3: Domain Models | Hard | Requires Project, Agent, Task, Turn models |
| Sprint 1: Flask Bootstrap | Hard | Requires base template and app factory |

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial draft - Core dashboard (Part 1 of 2) |
