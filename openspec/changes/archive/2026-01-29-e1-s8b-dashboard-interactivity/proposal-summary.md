# Proposal Summary: e1-s8b-dashboard-interactivity

## Architecture Decisions
- Vanilla JavaScript for SSE handling and DOM updates (no framework needed)
- Browser native EventSource API for SSE connection
- LocalStorage for sort preference persistence
- Targeted DOM updates by element ID/data attributes
- Single SSE connection per browser tab (shared across components)

## Implementation Approach
- Add SSE client JavaScript that connects on page load
- Implement event handlers for each event type (state_changed, turn_created, activity)
- Update DOM elements by targeting data attributes
- Recalculate derived values (counts, traffic lights) client-side
- Add Recommended Next panel with priority calculation
- Add sort controls with By Project (default) and By Priority views
- Wire Headspace buttons to focus API with feedback

## Files to Modify
**Routes:**
- `src/claude_headspace/routes/dashboard.py` - Add recommended next calculation, priority sorting

**Templates:**
- `templates/dashboard.html` - Add recommended next, sort controls, SSE script
- `templates/partials/_header.html` - Update connection indicator
- `templates/partials/_agent_card.html` - Wire Headspace button, add data-agent-id
- `templates/partials/_project_group.html` - Add data-project-id for targeting

**New Templates:**
- `templates/partials/_recommended_next.html` - Recommended Next panel
- `templates/partials/_sort_controls.html` - Sort toggle buttons
- `templates/partials/_toast.html` - Toast notification component

**JavaScript:**
- `static/js/dashboard-sse.js` - SSE connection and event handling
- `static/js/focus-api.js` - Click-to-focus with feedback

**Tests:**
- `tests/routes/test_dashboard_interactivity.py` - Interactivity tests

## Acceptance Criteria
- Recommended Next panel displays highest priority agent
- Clicking Recommended Next triggers focus API
- Sort controls toggle between By Project and By Priority
- Sort preference persists via localStorage
- SSE connection established on page load
- DOM updates complete within 500ms of event receipt
- Connection indicator shows SSE live/reconnecting/offline
- Headspace button triggers focus API
- Toast notifications on focus errors
- Graceful degradation when SSE unavailable

## Constraints and Gotchas
- **Focus API dependency**: Sprint 12 (AppleScript Integration) may not exist yet. Focus API calls will fail gracefully with error toast until implemented.
- **SSE endpoint**: Uses existing /api/events from Sprint 7
- **Event format**: Events are `event: {type}\ndata: {json}\n\n`
- **Reconnection**: Progressive delays 1s, 2s, 4s, 8s, max 30s
- **Sort in By Priority**: Flat list loses project grouping context
- **DOM targeting**: Need data-agent-id and data-project-id attributes

## Git Change History

### Related Files
**Routes:**
- src/claude_headspace/routes/dashboard.py - Dashboard route (just added in Part 1)
- src/claude_headspace/routes/sse.py - SSE endpoint (Sprint 7)

**Templates:**
- templates/dashboard.html - Main dashboard (Part 1)
- templates/partials/_header.html - Header (Part 1)
- templates/partials/_agent_card.html - Agent card (Part 1)
- templates/partials/_project_group.html - Project group (Part 1)

**JavaScript:**
- static/js/sse-client.js - SSE client (Sprint 7)

### OpenSpec History
- e1-s8-dashboard-ui: Dashboard UI Core (just completed)
- e1-s7-sse-system: SSE real-time transport
- e1-s6-state-machine: State transitions
- e1-s3-domain-models: Agent, Command models

### Implementation Patterns
1. Add JavaScript files for client-side logic
2. Add template partials for components
3. Wire to existing routes/endpoints
4. Add tests for new functionality

## Q&A History
- No clarifications needed
- Decision: Focus API will fail gracefully until Sprint 12 is implemented

## Dependencies
- **No new pip packages required**
- **Sprint 7**: SSE endpoint at /api/events (complete)
- **Sprint 12**: Focus API at /api/focus/<agent_id> (pending - will fail gracefully)
- **Part 1**: Dashboard UI Core (just completed)

## Testing Strategy
- Test recommended next calculation logic
- Test sort view toggle
- Test localStorage persistence
- Test SSE event handlers update DOM
- Test reconnection behavior
- Test focus API error handling
- Test toast display and auto-dismiss

## OpenSpec References
- proposal.md: openspec/changes/e1-s8b-dashboard-interactivity/proposal.md
- tasks.md: openspec/changes/e1-s8b-dashboard-interactivity/tasks.md
- spec.md: openspec/changes/e1-s8b-dashboard-interactivity/specs/dashboard/spec.md
