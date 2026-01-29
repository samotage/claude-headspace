# Proposal Summary: e1-s9-objective-tab

## Architecture Decisions
- Flask blueprint pattern for objective routes (objective_bp)
- Server-side rendered template extending base.html
- Vanilla JavaScript for auto-save with debounce
- RESTful API endpoints for objective CRUD
- Pagination using page/per_page query parameters

## Implementation Approach
- Create objective.py route with 3 API endpoints and 1 page route
- Use existing Objective and ObjectiveHistory models from Sprint 3
- Implement auto-save with 2-3 second debounce in JavaScript
- History tracking: set ended_at on previous record when updating
- Pagination with "Load more" pattern

## Files to Modify
**Routes:**
- `src/claude_headspace/routes/objective.py` - New blueprint with API endpoints
- `src/claude_headspace/app.py` - Register objective_bp

**Templates:**
- `templates/objective.html` - Objective tab page
- `templates/partials/_header.html` - Wire objective tab link

**JavaScript:**
- `static/js/objective.js` - Auto-save with debounce, UI logic

**Tests:**
- `tests/routes/test_objective.py` - API and route tests

## Acceptance Criteria
- Objective tab template with dark terminal aesthetic
- Objective form with text field (required) and constraints (optional)
- Auto-save with 2-3 second debounce
- Save state indicators (saving, saved, error)
- Objective history display with pagination (10 per page)
- GET /api/objective returns current objective
- POST /api/objective creates/updates with history tracking
- GET /api/objective/history returns paginated history
- Empty and error state handling

## Constraints and Gotchas
- **Objective text is required** - POST must validate non-empty text
- **History tracking on update** - Must set ended_at on previous before creating new
- **Singleton pattern** - Only one active objective at a time
- **No SSE updates** - Out of scope, multi-tab sync not required
- **Debounce timing** - 2-3 seconds to balance responsiveness vs API load

## Git Change History

### Related Files
**Models (from Sprint 3):**
- src/claude_headspace/models/objective.py - Objective model
- src/claude_headspace/models/objective_history.py - ObjectiveHistory model

**Routes (patterns to follow):**
- src/claude_headspace/routes/dashboard.py - Blueprint pattern
- src/claude_headspace/routes/health.py - API response patterns

**Templates:**
- templates/base.html - Base template to extend
- templates/dashboard.html - Page template pattern
- templates/partials/_header.html - Navigation links

**JavaScript:**
- static/js/dashboard-sse.js - JavaScript patterns
- static/js/focus-api.js - API call patterns

### OpenSpec History
- e1-s8b-dashboard-interactivity: Dashboard interactivity (just completed)
- e1-s8-dashboard-ui: Dashboard UI core
- e1-s3-domain-models: Domain models including Objective/ObjectiveHistory

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
- **Sprint 3**: Objective and ObjectiveHistory models (complete)
- **Sprint 8**: Dashboard UI with navigation (complete)

## Testing Strategy
- Test GET /api/objective with/without existing objective
- Test POST /api/objective create and update flows
- Test history tracking (ended_at set correctly)
- Test validation (empty text rejected)
- Test GET /api/objective/history pagination
- Test objective tab page renders
- Test empty states

## OpenSpec References
- proposal.md: openspec/changes/e1-s9-objective-tab/proposal.md
- tasks.md: openspec/changes/e1-s9-objective-tab/tasks.md
- spec.md: openspec/changes/e1-s9-objective-tab/specs/objective/spec.md
