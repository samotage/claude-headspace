---
validation:
  status: valid
  validated_at: '2026-01-29T10:33:04+11:00'
---

## Product Requirements Document (PRD) — Dashboard Interactivity

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 8b — Real-time updates, recommended next, sort controls, click-to-focus
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD covers the **interactivity layer** for the Claude Headspace dashboard, building on the core structure defined in Part 1 (`e1-s8-dashboard-ui-prd.md`). It adds real-time updates via Server-Sent Events (SSE), a "Recommended Next" panel that surfaces the highest priority agent, sort controls for flexible organization, and click-to-focus integration that connects dashboard actions to iTerm windows.

Together with Part 1, this completes the Sprint 8 Dashboard UI. Part 1 provides the static structure (layout, cards, state visualization); Part 2 makes it live and actionable. Users see state changes instantly, know which agent to work on next, and can jump to any terminal with a single click.

**Part 1 Reference:** `docs/prds/ui/e1-s8-dashboard-ui-prd.md`

---

## 1. Context & Purpose

### 1.1 Context

Part 1 delivers a static dashboard that displays projects, agents, and their states. However, a static dashboard requires manual refreshes and provides no guidance on which agent to attend to first. Part 2 transforms the dashboard from a snapshot into a live command center.

Sprint 7 (SSE System) provides the real-time event transport infrastructure. Sprint 12 (AppleScript Integration) provides the focus API. This PRD connects the dashboard to both systems.

### 1.2 Target User

Developers managing multiple concurrent Claude Code sessions who need:
- Instant awareness of state changes (no manual refresh)
- Clear guidance on which agent needs attention next
- One-click access to the relevant terminal window
- Flexible views matching different work modes (by project vs. by priority)

### 1.3 Success Moment

An agent finishes processing and asks the user a question. Within 1 second:
- The dashboard updates: agent card shows "Input needed" (orange)
- Header count changes: INPUT NEEDED increments
- Traffic light turns red for that project
- Recommended Next panel highlights this agent
- User clicks the panel → iTerm window focuses on that session

No page refresh. No scanning. No context lost.

---

## 2. Scope

### 2.1 In Scope

**Recommended Next Panel:**
- Panel positioned prominently (above project groups)
- Displays highest priority agent requiring attention
- Shows: agent session ID, project name, current state, priority score
- Displays rationale text (e.g., "Awaiting input for 2 minutes")
- Clicking panel triggers focus on that agent's iTerm window

**Sort Controls:**
- Toggle between "By Project" and "By Priority" views
- By Project: Agents grouped under project headers (Part 1 default layout)
- By Priority: Flat list of all agents ranked by priority/urgency
- Sort preference persists across browser sessions
- Mobile: Dropdown selector with current sort displayed

**SSE Real-time Updates:**
- Dashboard subscribes to event stream on page load
- State changes update DOM elements without page reload
- Updates include: status counts, traffic lights, agent cards, recommended next
- Connection status indicator in header (replaces Part 1 FR7 placeholder)
- Automatic reconnection with progressive delays on disconnect

**Click-to-Focus Integration:**
- Wire Part 1's "Headspace" button (FR20) to focus API
- POST to `/api/focus/<agent_id>` on click
- Success feedback: Brief visual highlight on card
- Error feedback: Toast message with actionable guidance

**Live Status Indicators:**
- Header connection indicator: "● SSE live" (connected) or "○ Reconnecting..." (disconnected)
- Updates Part 1 FR7 hooks/polling indicator to reflect actual connection state

### 2.2 Out of Scope

- Core dashboard layout, structure, styling (Part 1: `e1-s8-dashboard-ui-prd.md`)
- Agent card structure and fields (Part 1: FR13-FR19)
- Project group structure (Part 1: FR8-FR12)
- Responsive breakpoints (Part 1: FR21-FR24)
- SSE endpoint implementation (Sprint 7: `e1-s7-sse-system-prd.md`)
- Focus API implementation (Sprint 12: `e1-s12-applescript-integration-prd.md`)
- LLM-based priority scoring (Epic 3)
- Notification system integration (Epic 2)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| SC1 | Recommended next panel displays highest priority agent | Agent with `AWAITING_INPUT` shown, or most recent `last_seen_at` if none awaiting |
| SC2 | Clicking recommended next panel triggers focus API | POST to `/api/focus/<agent_id>` sent, iTerm window activates |
| SC3 | Sort "By Project" groups agents under project headers | Layout matches Part 1 structure with agents nested in project groups |
| SC4 | Sort "By Priority" shows flat ranked agent list | All agents in single list, ordered by priority score then recency |
| SC5 | Sort preference persists across page loads | Reload page → same sort mode active |
| SC6 | SSE connection established on page load | Network tab shows open connection to `/api/events` |
| SC7 | State changes update dashboard within 1 second | Measure: event timestamp to DOM update < 1000ms |
| SC8 | Header status counts update on state change | `agent_state_changed` event → INPUT NEEDED/WORKING/IDLE counts refresh |
| SC9 | Traffic lights update on state change | Agent state change → parent project traffic light colour recalculated |
| SC10 | Agent cards update on state/turn events | State bar, command summary, status badge update without reload |
| SC11 | SSE reconnects automatically on disconnect | Simulate disconnect → connection re-established within 30 seconds |
| SC12 | "Headspace" button triggers focus API with feedback | Click → API call → success highlight or error toast |
| SC13 | Connection indicator reflects SSE state | Connected: "● SSE live", Disconnected: "○ Reconnecting..." |
| SC14 | Recommended next panel updates on state changes | New highest-priority agent → panel content updates |

### 3.2 Non-Functional Success Criteria

| # | Criterion | Target |
|---|-----------|--------|
| NFR1 | SSE event-to-DOM latency | < 500ms from event received to DOM updated |
| NFR2 | Reconnection behavior | Progressive delays: 1s, 2s, 4s, 8s, max 30s |
| NFR3 | SSE connection overhead | Single connection per browser tab (not per component) |
| NFR4 | Sort transition smoothness | View switch completes in < 200ms |

---

## 4. Functional Requirements (FRs)

### Recommended Next Panel

**FR1:** The dashboard displays a "Recommended Next" panel above the project groups section.

**FR2:** The recommended next panel displays the highest priority agent based on:
- First: Any agent with `state = AWAITING_INPUT` (oldest waiting first)
- Then: Agent with most recent `last_seen_at` (most active)
- Tie-breaker: Alphabetical by project name

**FR3:** The recommended next panel displays:
- Agent session ID (truncated UUID with # prefix)
- Project name
- Current state with colour indicator
- Priority score badge
- Rationale text explaining why this agent is recommended (e.g., "Awaiting input for 3m", "Most recently active")

**FR4:** Clicking anywhere on the recommended next panel triggers the focus API for that agent.

**FR5:** If no agents exist or all agents are inactive, the recommended next panel displays "No agents to recommend" with appropriate styling.

**FR6:** The recommended next panel updates automatically when SSE events indicate a higher-priority agent.

### Sort Controls

**FR7:** The dashboard displays sort controls between the header and the recommended next panel.

**FR8:** Sort controls provide two options:
- "By Project": Agents grouped under project headers (Part 1 default layout)
- "By Priority": Flat list of all agents ranked by priority/urgency

**FR9:** Selecting "By Project" displays the Part 1 layout: project groups containing their agents.

**FR10:** Selecting "By Priority" displays a flat list of all agents ordered by:
- First: Agents with `state = AWAITING_INPUT`
- Then: Agents with `state IN (COMMANDED, PROCESSING)`
- Then: Agents with `state IN (IDLE, COMPLETE)`
- Within each group: Ordered by `last_seen_at` descending (most recent first)

**FR11:** The current sort selection persists across browser sessions.

**FR12:** On mobile viewports, sort controls display as a dropdown selector showing the current sort mode.

### SSE Real-time Updates

**FR13:** On page load, the dashboard establishes an SSE connection to the event stream endpoint.

**FR14:** The dashboard processes the following event types:
- `agent_state_changed`: Update agent card state bar, recalculate status counts and traffic lights
- `turn_created`: Update agent card command summary with new turn text
- `agent_activity`: Update agent card status badge (ACTIVE/IDLE) and uptime
- `session_ended`: Mark agent card as inactive or remove from display

**FR15:** When an `agent_state_changed` event is received:
- The affected agent card's state bar updates to reflect the new state
- Header status counts (INPUT NEEDED, WORKING, IDLE) are recalculated
- The agent's project traffic light is recalculated
- The recommended next panel re-evaluates which agent to display

**FR16:** When the SSE connection is lost, the dashboard automatically attempts to reconnect with progressive delays (increasing intervals up to a maximum).

**FR17:** During reconnection attempts, the dashboard remains usable with the last known state.

### Connection Status Indicator

**FR18:** The header displays a connection status indicator (replacing Part 1 FR7 placeholder).

**FR19:** Connection indicator states:
- Connected: "● SSE live" with green dot
- Disconnected/Reconnecting: "○ Reconnecting..." with grey dot
- Failed (after max retries): "✗ Offline" with red indicator

**FR20:** The connection indicator updates immediately when connection state changes.

### Click-to-Focus Integration

**FR21:** The "Headspace" button on each agent card (Part 1 FR20) triggers the focus API when clicked.

**FR22:** Clicking the Headspace button sends POST request to `/api/focus/<agent_id>`.

**FR23:** On successful focus:
- The agent card displays a brief visual highlight (e.g., border pulse)
- No additional user action required

**FR24:** On focus failure, the dashboard displays a toast notification:
- Permission error: "Grant iTerm automation permission in System Preferences → Privacy → Automation"
- Agent inactive: "Session ended - cannot focus terminal"
- Unknown error: "Could not focus terminal - check if iTerm is running"

**FR25:** The recommended next panel click (FR4) uses the same focus API integration as the Headspace button.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** DOM updates from SSE events complete within 500ms of event receipt.

**NFR2:** SSE reconnection uses progressive delays: initial 1 second, doubling each attempt, maximum 30 seconds between attempts.

**NFR3:** A single SSE connection serves all dashboard components (not one connection per widget).

**NFR4:** Sort view transitions (By Project ↔ By Priority) complete within 200ms with no visible flicker.

**NFR5:** Toast notifications auto-dismiss after 5 seconds but can be manually dismissed.

**NFR6:** The dashboard degrades gracefully if SSE is unavailable: displays last known state with "Offline" indicator, manual refresh still works.

---

## 6. UI Overview

### Recommended Next Panel

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ★ RECOMMENDED NEXT                                              [60]    │
│                                                                         │
│ #2e3fe060  claude-headspace  ████ Input needed                         │
│ "Awaiting input for 3 minutes"                                         │
│                                                                         │
│ Click to focus iTerm window                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Sort Controls (Desktop)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ SORT:  [By Project]  [By Priority]                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Sort Controls (Mobile)

```
┌──────────────────────┐
│ Sort: [By Project ▼] │
└──────────────────────┘
```

### By Priority View (Flat List)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ★ RECOMMENDED NEXT - #2e3fe060 - Input needed                    [60]   │
├─────────────────────────────────────────────────────────────────────────┤
│ SORT:  [By Project]  (By Priority)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ #2e3fe060  claude-headspace     ████ Input needed        up 2h 15m │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ #8a4bc123  raglue               ████ Processing...       up 45m    │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ #f91de456  icu-solarcam         ████ Idle                up 3h 20m │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Connection Indicator States

```
Connected:      ● SSE live
Reconnecting:   ○ Reconnecting...
Offline:        ✗ Offline
```

### Toast Notification (Error Example)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ⚠ Could not focus terminal                                        [✗]  │
│ Grant iTerm automation permission in System Preferences                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Part 1 Integration Points

This section documents specific connections to Part 1 (`e1-s8-dashboard-ui-prd.md`).

| Part 1 Element | Part 2 Action |
|----------------|---------------|
| **FR7** - Hooks/polling indicator (placeholder) | Replace with live SSE connection indicator (FR18-FR20) |
| **FR20** - Headspace button (placeholder) | Wire to focus API (FR21-FR25) |
| **FR6** - Status count badges | Update via SSE on `agent_state_changed` (FR15) |
| **FR10** - Traffic light indicators | Update via SSE on `agent_state_changed` (FR15) |
| **FR15** - Agent status badge | Update via SSE on `agent_activity` (FR14) |
| **FR17** - Agent state bars | Update via SSE on `agent_state_changed` (FR14) |
| **FR18** - Agent command summary | Update via SSE on `turn_created` (FR14) |
| **Project group structure** | Used by "By Project" sort (FR9) |
| **Agent card structure** | Used in both sort views, receives SSE updates |

---

## 8. Tech Context (Implementation Guidance)

This section provides technical context for implementers. These are not requirements but guidance.

**SSE Integration:**
- Sprint 7 provides SSE endpoint at `/api/events`
- Event format: `event: {type}\ndata: {json}\n\n`
- Use browser's native EventSource API or HTMX `hx-sse` extension

**Focus API:**
- Sprint 12 provides endpoint: POST `/api/focus/<agent_id>`
- Response: `{"status": "ok"}` or `{"status": "error", "message": "..."}`

**Sort Preference Storage:**
- LocalStorage key suggestion: `claude_headspace_sort_mode`
- Values: `"project"` or `"priority"`

**DOM Update Strategy:**
- Target specific elements by agent ID: `#agent-{id}`, `#project-{id}`
- Use data attributes for state: `data-state="awaiting_input"`
- Recalculate derived values (counts, traffic lights) client-side after updates

**Part 1 Template Elements:**
- Header status counts: Update inner text of badge elements
- Traffic lights: Update class/colour of indicator dots
- Agent cards: Update state bar class, command summary text, status badge

---

## 9. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| **Part 1: Dashboard UI Core** | Hard | Requires `e1-s8-dashboard-ui-prd.md` complete (layout, cards, structure) |
| **Sprint 7: SSE System** | Hard | Requires `/api/events` endpoint operational |
| **Sprint 12: AppleScript Integration** | Hard | Requires `/api/focus/<agent_id>` endpoint operational |
| Sprint 3: Domain Models | Hard | Requires Agent, Command models (inherited from Part 1) |

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial draft - Dashboard Interactivity (Part 2 of 2) |
