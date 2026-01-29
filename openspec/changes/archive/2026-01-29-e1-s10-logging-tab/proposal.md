# Proposal: e1-s10-logging-tab

## Summary

Add Logging Tab UI for viewing, filtering, and monitoring system events in real-time. Provides audit trail visibility into agent activity, state transitions, hook events, and objective changes.

## Motivation

Claude Headspace's event-driven architecture logs all significant system activities but users have no way to view these events. The logging tab provides:
- Verification that the system is working (are events being logged?)
- Debugging capabilities (why did this agent transition to this state?)
- Agent activity history (what happened during this session?)
- Hook validation (are hooks firing as expected?)

## Impact

### Files to Create
- `src/claude_headspace/routes/logging.py` - Logging API blueprint
- `templates/logging.html` - Logging tab template
- `static/js/logging.js` - Filter, pagination, SSE, and expand/collapse logic
- `tests/routes/test_logging.py` - API and route tests

### Files to Modify
- `src/claude_headspace/app.py` - Register logging blueprint
- `templates/partials/_header.html` - Wire logging tab link

### Database Changes
None - uses existing Event model from Sprint 5.

## Definition of Done

- [ ] Logging tab template with event table (columns: Timestamp, Project, Agent, Event Type, Details)
- [ ] Filter dropdowns for project, agent, and event type
- [ ] Server-side filtering via API query parameters
- [ ] Server-side pagination (50 per page default)
- [ ] Pagination controls (previous/next, page indicator)
- [ ] Real-time updates via SSE for new events
- [ ] Expandable event rows showing full JSON payload
- [ ] GET /api/events endpoint with filtering and pagination
- [ ] GET /api/events/filters endpoint for dropdown population
- [ ] Empty state handling
- [ ] Error state handling
- [ ] All tests passing

## Risks

- **Performance**: Large event datasets (10,000+) require efficient indexing. Event model already has composite indexes from Sprint 5.
- **SSE Integration**: Requires SSE infrastructure from Sprint 7. If not working, fall back to polling.

## Alternatives Considered

1. **Client-side filtering**: Rejected - would require loading all events, causing performance issues with large datasets.
2. **Date range filter**: Out of scope for this sprint - can be added later.
3. **Full-text search**: Out of scope - adds complexity without immediate need.
