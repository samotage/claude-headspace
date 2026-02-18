---
validation:
  status: valid
  validated_at: '2026-01-29T11:06:13+11:00'
---

## Product Requirements Document (PRD) — Logging Tab

**Project:** Claude Headspace v3.1
**Scope:** Event log viewing with filtering, pagination, and real-time updates
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

The Logging Tab provides users with a comprehensive view of all system events, enabling visibility into agent activity history, state transitions, and system behavior. This feature serves as the audit trail for the event-driven architecture, allowing users to understand what happened, when, and to which agents.

The logging tab displays events in a table format with columns for timestamp, project, agent, event type, and details. Users can filter events by project, agent, or event type to narrow down to relevant activity. The event list updates in real-time via Server-Sent Events (SSE), ensuring new events appear automatically without manual refresh.

Success is measured by the ability to efficiently browse and filter 10,000+ events with acceptable performance (<500ms query response), clear visibility into event details via inline expansion, and seamless real-time updates that keep the view current as new events occur.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace's event-driven architecture generates events for all significant system activities: session discovery, turn detection, state transitions, hook events, and objective changes. Without a dedicated view for these events, users have no way to:

- Verify the system is working correctly (are events being logged?)
- Debug issues (why did this agent transition to this state?)
- Understand agent activity history (what happened during this session?)
- Validate hook integration (are hooks firing as expected?)

The logging tab addresses these needs by providing a filterable, paginated, real-time view of all system events.

### 1.2 Target User

Primary users are developers and operators monitoring Claude Code sessions who need to:

- Troubleshoot unexpected agent behavior
- Verify state machine transitions are correct
- Confirm hook events are being received
- Review historical agent activity

### 1.3 Success Moment

The user opens the logging tab, applies a filter for a specific agent, and immediately sees all events related to that agent in chronological order. A new event appears in real-time as the agent transitions state, confirming the system is working correctly. The user expands an event row to see the full payload details, understanding exactly what triggered the state change.

---

## 2. Scope

### 2.1 In Scope

- Event log table displaying: timestamp, project name, agent identifier, event type, summary details
- Filter controls for: project (dropdown), agent (dropdown), event type (dropdown)
- Server-side filtering (API returns only matching events)
- Server-side pagination (default 50 events per page)
- Pagination controls (previous/next, page indicator)
- Real-time updates via SSE (new events prepend to list automatically)
- Expandable event rows (click to show full payload/details inline)
- API endpoint: GET `/api/events` with query parameters
- Dark terminal aesthetic consistent with dashboard
- Responsive layout for desktop and tablet

### 2.2 Out of Scope

- Date range filter (future enhancement)
- Full-text search within event payloads
- Event export (CSV, JSON)
- Event deletion or archiving controls
- Event aggregation, statistics, or charts
- Custom event type definitions
- Mobile-specific layouts
- Bulk operations on events

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Event log displays all events with columns: timestamp, project, agent, event type, details summary
2. Filters for project, agent, and event type are available and functional
3. Applying a filter returns only matching events (server-side filtering)
4. Pagination allows navigation through large event sets (50 events per page default)
5. New events appear automatically via SSE without page refresh
6. Clicking an event row expands to show full payload details inline
7. Clearing filters returns to unfiltered view
8. Empty states display appropriate messages (no events, no matching events)

### 3.2 Non-Functional Success Criteria

1. Query performance: API returns results in <500ms with 10,000+ events
2. UI responsiveness: Filter changes reflect within 200ms
3. SSE reliability: New events appear within 1 second of being logged
4. Page load: Initial logging tab loads within 2 seconds
5. Accessibility: Table is navigable via keyboard, expandable rows work with screen readers

---

## 4. Functional Requirements (FRs)

### Event Display

**FR1:** The logging tab displays events in a table with columns: Timestamp, Project, Agent, Event Type, Details.

**FR2:** Timestamps display in human-readable local time format (e.g., "2026-01-29 14:32:05").

**FR3:** Project column displays the project name (not ID).

**FR4:** Agent column displays a truncated session UUID or identifier (e.g., "#2e3f...").

**FR5:** Event Type column displays the event type in a readable format (e.g., "Session Discovered", "State Transition").

**FR6:** Details column displays a brief summary of the event payload (truncated if necessary).

### Filtering

**FR7:** A project filter dropdown lists all projects with events, plus an "All Projects" option.

**FR8:** An agent filter dropdown lists all agents with events, plus an "All Agents" option.

**FR9:** An event type filter dropdown lists all event types, plus an "All Types" option.

**FR10:** Filters can be combined (e.g., filter by project AND event type simultaneously).

**FR11:** Applying a filter immediately updates the event list with matching results.

**FR12:** A "Clear Filters" action resets all filters to their default (all) state.

### Pagination

**FR13:** Events are paginated with a default of 50 events per page.

**FR14:** Pagination controls display: previous page, next page, and current page indicator (e.g., "Page 2 of 15").

**FR15:** The most recent events appear first (descending timestamp order).

**FR16:** Changing filters resets pagination to page 1.

### Real-Time Updates

**FR17:** The logging tab subscribes to SSE for new event notifications.

**FR18:** New events matching current filters appear at the top of the list automatically.

**FR19:** A visual indicator shows when new events have been received (e.g., subtle highlight on new rows).

**FR20:** Real-time updates do not disrupt the user's current scroll position when viewing older events.

### Event Details

**FR21:** Clicking an event row expands it to show the full event payload inline.

**FR22:** Expanded details display the complete JSON payload in a formatted, readable manner.

**FR23:** Clicking an expanded row collapses it back to the summary view.

**FR24:** Only one event row can be expanded at a time (expanding another collapses the previous).

### API Endpoint

**FR25:** GET `/api/events` returns a paginated list of events.

**FR26:** Query parameters supported: `project_id`, `agent_id`, `event_type`, `page`, `per_page`.

**FR27:** Response includes: events array, total count, current page, total pages, and has_next/has_previous flags.

**FR28:** Events in the response include all fields needed for display (with project name and agent identifier resolved).

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The API endpoint uses existing database indexes for efficient querying (project_id, agent_id, event_type, timestamp).

**NFR2:** The logging tab maintains consistent styling with the dashboard (dark terminal aesthetic, Tailwind CSS).

**NFR3:** Filter dropdowns populate dynamically based on actual data (only show projects/agents/types that have events).

**NFR4:** The logging tab gracefully handles connection loss (SSE reconnection with exponential backoff).

**NFR5:** Error states display user-friendly messages (e.g., "Unable to load events. Please try again.").

---

## 6. UI Overview

### Layout

The logging tab follows the existing tab navigation pattern established in Sprint 8 (Dashboard UI). The tab content area contains:

1. **Filter Bar** (top): Horizontal row with three dropdown filters (Project, Agent, Event Type) and a Clear Filters button
2. **Event Table** (main): Full-width table with sortable columns displaying events
3. **Pagination Controls** (bottom): Previous/Next buttons with page indicator

### Event Table

| Timestamp | Project | Agent | Event Type | Details |
|-----------|---------|-------|------------|---------|
| 2026-01-29 14:32:05 | claude-headspace | #2e3f... | State Transition | idle → processing |
| 2026-01-29 14:31:58 | claude-headspace | #2e3f... | Turn Detected | User command received |

### Expanded Row

When a row is clicked, it expands below the summary row to show the full payload:

```
▼ 2026-01-29 14:32:05 | claude-headspace | #2e3f... | State Transition | idle → processing
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │ {                                                                                    │
  │   "previous_state": "idle",                                                          │
  │   "new_state": "processing",                                                         │
  │   "trigger": "turn_detected",                                                        │
  │   "confidence": 1.0                                                                  │
  │ }                                                                                    │
  └─────────────────────────────────────────────────────────────────────────────────────┘
```

### Filter Bar

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Project: [All Projects ▼]  Agent: [All Agents ▼]  Type: [All Types ▼]  [Clear Filters] │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Empty States

- No events at all: "No events recorded yet. Events will appear here as agent activity occurs."
- No matching events: "No events match the current filters. Try adjusting your filter criteria."

### Visual Indicators

- New events via SSE: Brief highlight animation on newly added rows
- Loading state: Skeleton loading or spinner while fetching
- Expanded row: Chevron icon rotates to indicate expanded state

---

## 7. Dependencies

### Required (blocking)

- **Sprint 5 (Event System):** Events must be logged to the database
- **Sprint 7 (SSE System):** Real-time updates require SSE infrastructure
- **Sprint 8 (Dashboard UI):** Tab navigation structure must exist

### Leverages (non-blocking)

- **Sprint 3 (Domain Models):** Event model with indexes already exists
- **Sprint 1 (Flask Bootstrap):** Base template and Tailwind CSS configured

---

## 8. Technical Context

### Existing Infrastructure

The Event model (`src/claude_headspace/models/event.py`) already provides:

- Fields: `id`, `timestamp`, `project_id`, `agent_id`, `command_id`, `turn_id`, `event_type`, `payload`
- EventType constants: `SESSION_DISCOVERED`, `SESSION_ENDED`, `TURN_DETECTED`, `STATE_TRANSITION`, `HOOK_RECEIVED`, `OBJECTIVE_CHANGED`
- Composite indexes for efficient filtering: `ix_events_project_id_timestamp`, `ix_events_agent_id_timestamp`, `ix_events_event_type_timestamp`

### Event Types for Display

| EventType Constant | Display Name | Typical Details |
|-------------------|--------------|-----------------|
| SESSION_DISCOVERED | Session Discovered | New agent session detected |
| SESSION_ENDED | Session Ended | Agent session closed |
| TURN_DETECTED | Turn Detected | New turn in conversation |
| STATE_TRANSITION | State Transition | Command state changed |
| HOOK_RECEIVED | Hook Received | Claude Code hook event |
| OBJECTIVE_CHANGED | Objective Changed | Global objective updated |

---

## 9. Acceptance Tests

### Test 1: Basic Event Display

**Setup:** Database contains 100 events across multiple projects and agents.

**Steps:**
1. Navigate to logging tab
2. Observe event table

**Expected:**
- Table displays events with all columns populated
- Most recent events appear first
- Pagination shows "Page 1 of 2" (50 per page)

### Test 2: Filter by Project

**Setup:** Events exist for projects A and B.

**Steps:**
1. Select "Project A" from project filter

**Expected:**
- Only events for Project A are displayed
- Other filters remain at "All"
- Pagination resets to page 1

### Test 3: Combined Filters

**Setup:** Events exist for multiple projects, agents, and types.

**Steps:**
1. Select a specific project
2. Select a specific event type

**Expected:**
- Only events matching BOTH criteria are displayed

### Test 4: Real-Time Updates

**Setup:** Logging tab is open with filters cleared.

**Steps:**
1. Trigger a new event (e.g., start a Claude Code session)
2. Observe logging tab

**Expected:**
- New event appears at top of list within 1 second
- New row has brief highlight animation
- No page refresh required

### Test 5: Expand Event Details

**Setup:** Events exist in the table.

**Steps:**
1. Click on an event row
2. Observe expanded details

**Expected:**
- Row expands to show full JSON payload
- Payload is formatted and readable
- Clicking again collapses the row

### Test 6: Pagination Navigation

**Setup:** Database contains 150 events.

**Steps:**
1. Observe initial state (Page 1 of 3)
2. Click "Next"
3. Click "Next" again
4. Click "Previous"

**Expected:**
- Navigation updates displayed events correctly
- Page indicator updates accordingly
- Previous disabled on page 1, Next disabled on last page

### Test 7: Performance with Large Dataset

**Setup:** Database contains 10,000+ events.

**Steps:**
1. Navigate to logging tab
2. Apply various filters
3. Navigate pagination

**Expected:**
- Initial load completes within 2 seconds
- Filter queries return within 500ms
- No UI lag or freezing

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD for Epic 1, Sprint 10 |
