# Proposal Summary: e4-s2b-project-controls-ui

## Architecture Decisions
- Follow existing vanilla JS + Jinja2 template pattern (no external dependencies)
- Add page route to existing `projects_bp` blueprint created in E4-S2a (no new blueprint needed)
- Modal forms follow the waypoint editor pattern (fixed overlay, backdrop blur, close button)
- SSE integration follows dashboard pattern for real-time updates
- Delete confirmation dialog is inline HTML (not a separate partial) since it's simpler than the form modal

## Implementation Approach
- The `/projects` page route renders a template that loads data client-side via `fetch()` to `/api/projects`
- All CRUD operations happen via JavaScript API calls — no server-side form handling
- SSE events trigger full list refresh (simple, reliable) rather than targeted DOM updates
- Modal state (add vs edit) managed via JavaScript with a shared form element

## Files to Modify
- Routes:
  - `src/claude_headspace/routes/projects.py` — add `/projects` page route (renders template, provides status_counts)
- Templates:
  - `templates/projects.html` — **NEW** projects management page
  - `templates/partials/_project_form_modal.html` — **NEW** add/edit project modal
  - `templates/partials/_header.html` — add "Projects" tab between Dashboard and Objective (desktop + mobile)
- Static:
  - `static/js/projects.js` — **NEW** projects page JavaScript (API calls, modal handling, SSE)
- Tests:
  - `tests/routes/test_projects_page.py` — **NEW** page route tests

## Acceptance Criteria
- GET /projects renders projects page with project list table
- Add Project modal creates project via API, appears in list without reload
- Edit Project modal pre-populates, updates via API without reload
- Delete confirmation shows agent count warning, deletes via API without reload
- Pause/Resume toggle updates inference status via settings API without reload
- Paused projects show visually distinct "Paused" indicator
- "Projects" tab in header navigation (desktop + mobile) with active state
- SSE events (project_changed, project_settings_changed) refresh list in real-time

## Constraints and Gotchas
- The `status_counts` context variable is needed by the header partial for the stats bar — must be provided by the page route
- Header partial uses `request.endpoint` for active tab detection — endpoint name must match pattern (e.g., `projects.projects_page`)
- Modal form shared between add/edit — JavaScript must clear/populate fields appropriately
- The existing `projects_bp` blueprint already has API routes — page route just adds a template-rendering endpoint
- Vanilla JS only — no jQuery, React, or other external dependencies
- The base.html includes `sse-client.js` and `header-sse.js` on all pages — projects page just needs to add its own SSE event handlers

## Git Change History

### Related Files
- Routes: `src/claude_headspace/routes/projects.py` (created in E4-S2a with CRUD + settings API endpoints)
- Templates: `templates/objective.html` (reference for page structure), `templates/partials/_waypoint_editor.html` (reference for modal pattern), `templates/partials/_header.html` (navigation modification target)
- Static: `static/js/objective.js` (reference for JS API call patterns), `static/js/dashboard-sse.js` (reference for SSE handling)

### OpenSpec History
- 2026-02-02: e4-s2a-project-controls-backend — Backend API, migration, inference gating (completed, merged as PR #32)

### Implementation Patterns
- Page routes render templates with server-side context for header stats bar
- JavaScript fetches API data on DOMContentLoaded
- Modal forms use fixed overlay with backdrop blur and close button
- SSE connection via shared `sse-client.js` with page-specific event handlers
- Active tab detection via `request.endpoint` in Jinja2 conditionals

## Q&A History
- No clarifications needed — PRD is clear and comprehensive with wireframes and explicit file listings

## Dependencies
- No new packages required
- Depends on E4-S2a backend API endpoints (already merged to development)

## Testing Strategy
- Route test: GET /projects returns 200 with correct template
- Route test: page route provides status_counts context
- Manual testing: full CRUD flow, pause/resume, SSE updates, navigation active state

## OpenSpec References
- proposal.md: openspec/changes/e4-s2b-project-controls-ui/proposal.md
- tasks.md: openspec/changes/e4-s2b-project-controls-ui/tasks.md
- spec.md: openspec/changes/e4-s2b-project-controls-ui/specs/project-controls-ui/spec.md
