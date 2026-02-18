# Commands: e1-s10-logging-tab

## Phase 1: Setup

- [x] Review existing Event model from Sprint 5
- [x] Review SSE infrastructure from Sprint 7
- [x] Review dashboard patterns from Sprint 8
- [x] Plan API response formats

## Phase 2: Implementation

### API Endpoints (FR25-FR28)
- [x] Create logging.py blueprint with logging_bp
- [x] Implement GET /api/events endpoint
  - Accept query params: project_id, agent_id, event_type, page, per_page
  - Return paginated events with resolved project name and agent identifier
  - Include total count, current page, total pages, has_next/has_previous
  - Order by timestamp descending
- [x] Implement GET /api/events/filters endpoint
  - Return available projects, agents, and event types for dropdowns
  - Only include items that have events

### Template (FR1-FR6)
- [x] Create logging.html extending base template
- [x] Add filter bar with three dropdowns and Clear Filters button
- [x] Add event table with columns: Timestamp, Project, Agent, Event Type, Details
- [x] Add pagination controls (previous/next, page indicator)
- [x] Add empty state messages
- [x] Apply dark terminal aesthetic (Tailwind classes)

### Filtering (FR7-FR12)
- [x] Implement project filter dropdown
- [x] Implement agent filter dropdown
- [x] Implement event type filter dropdown
- [x] Implement combined filter support
- [x] Implement Clear Filters functionality
- [x] Reset pagination to page 1 on filter change

### Pagination (FR13-FR16)
- [x] Implement server-side pagination (50 per page)
- [x] Implement previous/next navigation
- [x] Display page indicator (e.g., "Page 2 of 15")
- [x] Disable previous on page 1, next on last page

### Real-Time Updates (FR17-FR20)
- [x] Subscribe to SSE for new event notifications
- [x] Prepend new events matching current filters to list
- [x] Add visual highlight for new event rows
- [x] Maintain scroll position when new events arrive

### Event Details (FR21-FR24)
- [x] Implement expandable event rows
- [x] Display formatted JSON payload in expanded view
- [x] Collapse row on second click
- [x] Only allow one expanded row at a time

### Error Handling
- [x] Display user-friendly error messages
- [x] Handle SSE connection loss with reconnection

### Integration
- [x] Register logging_bp in app.py
- [x] Wire logging tab link in header navigation
- [x] Add logging route for tab page

## Phase 3: Testing

- [x] Test GET /api/events returns paginated events
- [x] Test GET /api/events with filters
- [x] Test GET /api/events with combined filters
- [x] Test GET /api/events pagination
- [x] Test GET /api/events/filters returns available options
- [x] Test logging tab page renders
- [x] Test empty states display correctly
- [x] Test event row expansion

## Phase 4: Final Verification

- [x] All tests passing
- [x] Query performance acceptable (<500ms with indexed queries)
- [x] SSE updates working
- [x] UI matches dark terminal aesthetic
- [x] No console errors
