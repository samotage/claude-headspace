# Proposal Summary: e1-s10-logging-tab

## Architecture Decisions
- Flask blueprint pattern for logging routes (logging_bp)
- Server-side filtering and pagination for performance with large datasets
- SSE integration for real-time event updates
- RESTful API endpoints for events CRUD
- Vanilla JavaScript for filter, pagination, and expand/collapse logic

## Implementation Approach
- Create logging.py route with 2 API endpoints and 1 page route
- Use existing Event model from Sprint 5 with composite indexes
- Leverage SSE infrastructure from Sprint 7 for real-time updates
- Follow dashboard patterns from Sprint 8 for consistent UI
- Server-side filtering to handle 10,000+ events efficiently

## Files to Modify
**Routes:**
- `src/claude_headspace/routes/logging.py` - New blueprint with API endpoints
- `src/claude_headspace/app.py` - Register logging_bp

**Templates:**
- `templates/logging.html` - Logging tab page
- `templates/partials/_header.html` - Wire logging tab link

**JavaScript:**
- `static/js/logging.js` - Filter, pagination, SSE, expand/collapse logic

**Tests:**
- `tests/routes/test_logging.py` - API and route tests

## Acceptance Criteria
- Logging tab template with event table (columns: Timestamp, Project, Agent, Event Type, Details)
- Filter dropdowns for project, agent, and event type
- Server-side filtering via API query parameters
- Server-side pagination (50 per page default)
- Pagination controls (previous/next, page indicator)
- Real-time updates via SSE for new events
- Expandable event rows showing full JSON payload
- GET /api/events endpoint with filtering and pagination
- GET /api/events/filters endpoint for dropdown population
- Empty and error state handling

## Constraints and Gotchas
- **Performance**: Must use existing database indexes (project_id, agent_id, event_type, timestamp)
- **Pagination reset**: Changing filters must reset pagination to page 1
- **Single expansion**: Only one event row can be expanded at a time
- **SSE filter matching**: New events via SSE must match current filters to be displayed
- **Scroll preservation**: Real-time updates must not disrupt scroll position
- **Default 50 per page**: Per PRD specification

## Git Change History

### Related Files
**Models (from Sprint 5):**
- src/claude_headspace/models/event.py - Event model with EventType constants

**Routes (patterns to follow):**
- src/claude_headspace/routes/dashboard.py - Blueprint pattern
- src/claude_headspace/routes/objective.py - API response patterns (just completed)

**Templates:**
- templates/base.html - Base template to extend
- templates/dashboard.html - Page template pattern
- templates/objective.html - Recent tab template pattern
- templates/partials/_header.html - Navigation links

**JavaScript:**
- static/js/dashboard-sse.js - SSE subscription patterns
- static/js/objective.js - API call patterns
- static/js/sse-client.js - SSE client (Sprint 7)

### OpenSpec History
- e1-s9-objective-tab: Objective Tab (just completed)
- e1-s8b-dashboard-interactivity: Dashboard interactivity
- e1-s8-dashboard-ui: Dashboard UI core
- e1-s7-sse-system: SSE infrastructure
- e1-s5-event-system: Event model and logging

### Implementation Patterns
1. Create Flask blueprint with page route and API routes
2. Register blueprint in app.py
3. Create template extending base.html
4. Create JavaScript for client-side logic
5. Add tests for routes and API endpoints

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required**
- **Sprint 5**: Event model with indexes (complete)
- **Sprint 7**: SSE infrastructure (complete)
- **Sprint 8**: Dashboard UI with navigation (complete)

## Testing Strategy
- Test GET /api/events with/without filters
- Test GET /api/events pagination
- Test GET /api/events combined filters
- Test GET /api/events/filters returns available options
- Test logging tab page renders
- Test empty states
- Test event row expansion logic

## OpenSpec References
- proposal.md: openspec/changes/e1-s10-logging-tab/proposal.md
- tasks.md: openspec/changes/e1-s10-logging-tab/tasks.md
- spec.md: openspec/changes/e1-s10-logging-tab/specs/logging/spec.md
