# Proposal: e1-s8b-dashboard-interactivity

## Summary

Add interactivity layer to the Dashboard UI: SSE real-time updates, Recommended Next panel, sort controls (By Project/By Priority), and click-to-focus integration. This transforms the static dashboard from Part 1 into a live command center.

## Motivation

The static dashboard requires manual refreshes and provides no guidance on which agent to attend to first. Part 2 enables:
- Instant awareness of state changes via SSE
- Clear guidance on which agent needs attention (Recommended Next)
- One-click access to terminal windows (focus API)
- Flexible views for different workflows (sort controls)

## Impact

### Files to Create
- `templates/partials/_recommended_next.html` - Recommended Next panel partial
- `templates/partials/_sort_controls.html` - Sort controls partial
- `templates/partials/_toast.html` - Toast notification partial
- `static/js/dashboard-sse.js` - SSE event handling and DOM updates
- `static/js/focus-api.js` - Click-to-focus API integration
- `tests/routes/test_dashboard_interactivity.py` - Interactivity tests

### Files to Modify
- `templates/dashboard.html` - Add recommended next, sort controls, SSE setup
- `templates/partials/_header.html` - Update connection indicator
- `templates/partials/_agent_card.html` - Wire Headspace button, add data attributes
- `templates/partials/_project_group.html` - Add data attributes for SSE targeting
- `src/claude_headspace/routes/dashboard.py` - Add priority sorting logic, recommended next calculation
- `static/css/src/input.css` - Toast and highlight animations

### Database Changes
None - uses existing models and SSE infrastructure from Sprint 7.

## Definition of Done

- [ ] Recommended Next panel displays highest priority agent
- [ ] Clicking Recommended Next triggers focus API
- [ ] Sort controls toggle between By Project and By Priority views
- [ ] Sort preference persists via localStorage
- [ ] SSE connection established on page load
- [ ] State changes update DOM within 500ms
- [ ] Connection indicator shows SSE live/reconnecting/offline
- [ ] Headspace button triggers focus API with feedback
- [ ] Toast notifications display on focus errors
- [ ] Graceful degradation when SSE unavailable
- [ ] All tests passing

## Risks

- **Sprint 12 dependency**: Focus API may not exist yet. Mitigated by graceful error handling.
- **SSE reliability**: Network issues could cause stale data. Mitigated by reconnection logic.
- **DOM update performance**: Many updates could cause lag. Mitigated by targeted element updates.

## Alternatives Considered

1. **WebSocket instead of SSE**: More complex, bidirectional not needed. Rejected.
2. **Polling instead of SSE**: Higher latency, more server load. Rejected - Sprint 7 already provides SSE.
3. **React/Vue for reactivity**: Adds build complexity. Rejected - vanilla JS sufficient for this scope.
