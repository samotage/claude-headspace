# Tasks: e1-s10-logging-tab

## Phase 1: Setup

- [ ] Review existing Event model from Sprint 5
- [ ] Review SSE infrastructure from Sprint 7
- [ ] Review dashboard patterns from Sprint 8
- [ ] Plan API response formats

## Phase 2: Implementation

### API Endpoints (FR25-FR28)
- [ ] Create logging.py blueprint with logging_bp
- [ ] Implement GET /api/events endpoint
  - Accept query params: project_id, agent_id, event_type, page, per_page
  - Return paginated events with resolved project name and agent identifier
  - Include total count, current page, total pages, has_next/has_previous
  - Order by timestamp descending
- [ ] Implement GET /api/events/filters endpoint
  - Return available projects, agents, and event types for dropdowns
  - Only include items that have events

### Template (FR1-FR6)
- [ ] Create logging.html extending base template
- [ ] Add filter bar with three dropdowns and Clear Filters button
- [ ] Add event table with columns: Timestamp, Project, Agent, Event Type, Details
- [ ] Add pagination controls (previous/next, page indicator)
- [ ] Add empty state messages
- [ ] Apply dark terminal aesthetic (Tailwind classes)

### Filtering (FR7-FR12)
- [ ] Implement project filter dropdown
- [ ] Implement agent filter dropdown
- [ ] Implement event type filter dropdown
- [ ] Implement combined filter support
- [ ] Implement Clear Filters functionality
- [ ] Reset pagination to page 1 on filter change

### Pagination (FR13-FR16)
- [ ] Implement server-side pagination (50 per page)
- [ ] Implement previous/next navigation
- [ ] Display page indicator (e.g., "Page 2 of 15")
- [ ] Disable previous on page 1, next on last page

### Real-Time Updates (FR17-FR20)
- [ ] Subscribe to SSE for new event notifications
- [ ] Prepend new events matching current filters to list
- [ ] Add visual highlight for new event rows
- [ ] Maintain scroll position when new events arrive

### Event Details (FR21-FR24)
- [ ] Implement expandable event rows
- [ ] Display formatted JSON payload in expanded view
- [ ] Collapse row on second click
- [ ] Only allow one expanded row at a time

### Error Handling
- [ ] Display user-friendly error messages
- [ ] Handle SSE connection loss with reconnection

### Integration
- [ ] Register logging_bp in app.py
- [ ] Wire logging tab link in header navigation
- [ ] Add logging route for tab page

## Phase 3: Testing

- [ ] Test GET /api/events returns paginated events
- [ ] Test GET /api/events with filters
- [ ] Test GET /api/events with combined filters
- [ ] Test GET /api/events pagination
- [ ] Test GET /api/events/filters returns available options
- [ ] Test logging tab page renders
- [ ] Test empty states display correctly
- [ ] Test event row expansion

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Query performance acceptable (<500ms with indexed queries)
- [ ] SSE updates working
- [ ] UI matches dark terminal aesthetic
- [ ] No console errors
