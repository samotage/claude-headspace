## Why

The persona backend (models, registration, filesystem assets, CLI) was built across Epic 8 Sprints 1-14, but no management UI exists. Users can only interact with personas via `flask persona register` CLI commands or raw API calls, making the feature invisible from the dashboard. This sprint delivers a Personas tab with list page and full CRUD (create, edit, archive, delete) so users can discover and manage personas entirely from the browser.

## What Changes

- Navigation: "Personas" tab added to main nav bar (both desktop `tab-btn-group` and mobile drawer), positioned after "Help"
- New page route: `/personas` renders `personas.html` template (extends `base.html`, includes `_header.html`)
- New template: `templates/personas.html` with table (Name, Role, Status, Agents, Created), empty state, and "New Persona" button
- New template partial: `templates/partials/_persona_form_modal.html` for create/edit modal (follows `_project_form_modal.html` pattern)
- New JavaScript module: `static/js/personas.js` for list loading, modal CRUD, toast notifications, inline validation
- Extended route: `src/claude_headspace/routes/personas.py` gains 5 new endpoints:
  - `GET /personas` (page route)
  - `GET /api/personas` (list all with role name, status, agent count)
  - `GET /api/personas/<slug>` (single persona detail)
  - `PUT /api/personas/<slug>` (update name, description, status)
  - `DELETE /api/personas/<slug>` (delete if no linked agents)
  - `GET /api/roles` (list all roles)
- No model changes required (existing Persona and Role models have all needed fields)
- No migration required

## Impact

- Affected specs: persona-list-crud (new capability)
- Affected code:
  - MODIFIED: `src/claude_headspace/routes/personas.py` -- add page route + 5 API endpoints
  - NEW: `templates/personas.html` -- persona list page
  - NEW: `templates/partials/_persona_form_modal.html` -- create/edit modal
  - NEW: `static/js/personas.js` -- persona list + CRUD JavaScript
  - MODIFIED: `templates/partials/_header.html` -- add Personas tab to desktop and mobile nav
- Affected tests:
  - MODIFIED: `tests/routes/test_personas.py` -- add tests for new endpoints
  - NEW: tests for list, get, update, delete endpoints + page route

## Definition of Done

- [ ] Personas tab visible in main navigation (desktop and mobile)
- [ ] Personas tab highlights as active on `/personas` page
- [ ] `/personas` page displays table of all personas with name, role, status, agent count, created date
- [ ] Empty state shown when no personas exist
- [ ] Create persona modal: name (required), role dropdown with "create new" option, description (optional)
- [ ] Edit persona modal: pre-populated fields, role read-only, status toggle
- [ ] Archive persona with confirmation dialog
- [ ] Delete persona blocked when agents are linked, with error message
- [ ] Delete persona succeeds with confirmation when no agents linked
- [ ] Toast notifications for all CRUD success/failure
- [ ] List updates without page reload after create/edit/archive/delete
- [ ] API endpoints return correct HTTP status codes (200, 201, 400, 404, 409)
- [ ] All tests passing
