# Tasks: e1-s8b-dashboard-interactivity

## Phase 1: Setup

- [ ] Review Part 1 templates for integration points
- [ ] Review Sprint 7 SSE endpoint and event format
- [ ] Plan DOM structure for SSE targeting

## Phase 2: Implementation

### Recommended Next Panel (FR1-FR6)
- [ ] Create _recommended_next.html partial
- [ ] Implement priority calculation logic in dashboard route
- [ ] Display highest priority agent (AWAITING_INPUT first, then most recent)
- [ ] Show session ID, project name, state indicator, priority score
- [ ] Show rationale text (e.g., "Awaiting input for 3m")
- [ ] Handle empty state ("No agents to recommend")
- [ ] Add click handler for focus API trigger
- [ ] Add data attributes for SSE updates

### Sort Controls (FR7-FR12)
- [ ] Create _sort_controls.html partial
- [ ] Implement "By Project" view (Part 1 default layout)
- [ ] Implement "By Priority" view (flat ranked list)
- [ ] Add sort toggle UI (desktop: buttons, mobile: dropdown)
- [ ] Implement localStorage persistence for sort preference
- [ ] Add CSS transitions for smooth view switches

### SSE Real-time Updates (FR13-FR17)
- [ ] Create dashboard-sse.js for SSE handling
- [ ] Establish EventSource connection on page load
- [ ] Handle `agent_state_changed` events:
  - Update agent card state bar
  - Recalculate header status counts
  - Recalculate project traffic lights
  - Update recommended next panel
- [ ] Handle `turn_created` events (update task summary)
- [ ] Handle `agent_activity` events (update status badge, uptime)
- [ ] Handle `session_ended` events (mark agent inactive)
- [ ] Implement automatic reconnection with progressive delays
- [ ] Ensure dashboard remains usable during reconnection

### Connection Status Indicator (FR18-FR20)
- [ ] Update _header.html connection indicator section
- [ ] Implement connected state: "● SSE live" (green)
- [ ] Implement reconnecting state: "○ Reconnecting..." (grey)
- [ ] Implement offline state: "✗ Offline" (red)
- [ ] Update indicator on connection state changes

### Click-to-Focus Integration (FR21-FR25)
- [ ] Create focus-api.js for focus handling
- [ ] Wire Headspace button to POST `/api/focus/<agent_id>`
- [ ] Implement success feedback (card highlight animation)
- [ ] Create _toast.html partial for notifications
- [ ] Implement toast for permission errors
- [ ] Implement toast for inactive agent errors
- [ ] Implement toast for unknown errors
- [ ] Wire recommended next panel click to focus API
- [ ] Add 5-second auto-dismiss to toasts

### By Priority View Layout
- [ ] Create flat agent list layout for priority view
- [ ] Order by: AWAITING_INPUT → COMMANDED/PROCESSING → IDLE/COMPLETE
- [ ] Within each group, order by last_seen_at descending
- [ ] Include project name on cards in priority view
- [ ] Ensure responsive layout for priority view

## Phase 3: Testing

- [ ] Test recommended next displays correct agent
- [ ] Test recommended next updates on state changes
- [ ] Test sort toggle switches views
- [ ] Test sort preference persists in localStorage
- [ ] Test SSE connection establishes on load
- [ ] Test DOM updates within latency requirements
- [ ] Test reconnection behavior on disconnect
- [ ] Test connection indicator state changes
- [ ] Test Headspace button triggers focus API
- [ ] Test focus success shows highlight
- [ ] Test focus failure shows toast
- [ ] Test graceful degradation without SSE

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No console errors
- [ ] SSE latency < 500ms
- [ ] Sort transition < 200ms
- [ ] Works at all breakpoints
