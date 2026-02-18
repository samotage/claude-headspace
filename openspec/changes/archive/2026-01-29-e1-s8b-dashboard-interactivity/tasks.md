# Commands: e1-s8b-dashboard-interactivity

## Phase 1: Setup

- [x] Review Part 1 templates for integration points
- [x] Review Sprint 7 SSE endpoint and event format
- [x] Plan DOM structure for SSE targeting

## Phase 2: Implementation

### Recommended Next Panel (FR1-FR6)
- [x] Create _recommended_next.html partial
- [x] Implement priority calculation logic in dashboard route
- [x] Display highest priority agent (AWAITING_INPUT first, then most recent)
- [x] Show session ID, project name, state indicator, priority score
- [x] Show rationale text (e.g., "Awaiting input for 3m")
- [x] Handle empty state ("No agents to recommend")
- [x] Add click handler for focus API trigger
- [x] Add data attributes for SSE updates

### Sort Controls (FR7-FR12)
- [x] Create _sort_controls.html partial
- [x] Implement "By Project" view (Part 1 default layout)
- [x] Implement "By Priority" view (flat ranked list)
- [x] Add sort toggle UI (desktop: buttons, mobile: dropdown)
- [x] Implement localStorage persistence for sort preference
- [x] Add CSS transitions for smooth view switches

### SSE Real-time Updates (FR13-FR17)
- [x] Create dashboard-sse.js for SSE handling
- [x] Establish EventSource connection on page load
- [x] Handle `agent_state_changed` events:
  - Update agent card state bar
  - Recalculate header status counts
  - Recalculate project traffic lights
  - Update recommended next panel
- [x] Handle `turn_created` events (update command summary)
- [x] Handle `agent_activity` events (update status badge, uptime)
- [x] Handle `session_ended` events (mark agent inactive)
- [x] Implement automatic reconnection with progressive delays
- [x] Ensure dashboard remains usable during reconnection

### Connection Status Indicator (FR18-FR20)
- [x] Update _header.html connection indicator section
- [x] Implement connected state: "● SSE live" (green)
- [x] Implement reconnecting state: "○ Reconnecting..." (grey)
- [x] Implement offline state: "✗ Offline" (red)
- [x] Update indicator on connection state changes

### Click-to-Focus Integration (FR21-FR25)
- [x] Create focus-api.js for focus handling
- [x] Wire Headspace button to POST `/api/focus/<agent_id>`
- [x] Implement success feedback (card highlight animation)
- [x] Create _toast.html partial for notifications
- [x] Implement toast for permission errors
- [x] Implement toast for inactive agent errors
- [x] Implement toast for unknown errors
- [x] Wire recommended next panel click to focus API
- [x] Add 5-second auto-dismiss to toasts

### By Priority View Layout
- [x] Create flat agent list layout for priority view
- [x] Order by: AWAITING_INPUT → COMMANDED/PROCESSING → IDLE/COMPLETE
- [x] Within each group, order by last_seen_at descending
- [x] Include project name on cards in priority view
- [x] Ensure responsive layout for priority view

## Phase 3: Testing

- [x] Test recommended next displays correct agent
- [x] Test recommended next updates on state changes
- [x] Test sort toggle switches views
- [x] Test sort preference persists in localStorage
- [x] Test SSE connection establishes on load
- [x] Test DOM updates within latency requirements
- [x] Test reconnection behavior on disconnect
- [x] Test connection indicator state changes
- [x] Test Headspace button triggers focus API
- [x] Test focus success shows highlight
- [x] Test focus failure shows toast
- [x] Test graceful degradation without SSE

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No console errors
- [ ] SSE latency < 500ms
- [ ] Sort transition < 200ms
- [ ] Works at all breakpoints
