# Proposal Summary: e8-s15-persona-list-crud

## Architecture Decisions
- Extends existing `personas_bp` blueprint with page route + 5 API endpoints (no new blueprint needed)
- Uses existing `POST /api/personas/register` endpoint for creation (no duplication)
- No model changes or migrations -- existing Persona and Role models have all required fields
- Follows established page pattern: Jinja2 template extends `base.html`, includes `_header.html`, JavaScript module handles all dynamic behavior
- Follows established modal pattern: `_persona_form_modal.html` mirrors `_project_form_modal.html` (fixed position, backdrop blur, z-200)
- API endpoints follow REST conventions: GET list, GET detail, PUT update, DELETE remove
- Agent count computed via `len(persona.agents)` -- no additional queries needed due to SQLAlchemy relationship

## Implementation Approach
- Add 6 endpoints to `routes/personas.py`: page route + list + detail + update + delete + roles
- Create `templates/personas.html` following `templates/projects.html` structure (section with table, empty state, loading state)
- Create `templates/partials/_persona_form_modal.html` following `_project_form_modal.html` structure
- Create `static/js/personas.js` as `PersonasPage` module following `ProjectsPage` pattern (fetch, render, modal open/close/submit)
- Modify `_header.html` to add "personas" tab in desktop nav and mobile drawer
- Role dropdown in create modal: fetches from `GET /api/roles`, appends "Create new role..." option
- Inline new role input: shown/hidden via JS when "Create new role..." is selected
- Confirmation dialogs use existing `confirm-dialog.js` pattern
- Toast notifications use existing `showToast()` utility from `utils.js`

## Files to Modify
- **Routes:** `src/claude_headspace/routes/personas.py` -- add page route + 5 API endpoints
- **Templates:** `templates/personas.html` (NEW) -- persona list page
- **Templates:** `templates/partials/_persona_form_modal.html` (NEW) -- create/edit modal
- **Templates:** `templates/partials/_header.html` -- add Personas tab to desktop + mobile nav
- **Static JS:** `static/js/personas.js` (NEW) -- PersonasPage module
- **Tests:** `tests/routes/test_personas.py` -- extend with tests for all new endpoints

## Acceptance Criteria
- Personas tab visible in main navigation (desktop and mobile)
- Personas tab highlights as active on `/personas`
- List page displays all personas with name, role, status badge, agent count, created date
- Empty state shown when no personas exist
- Create modal: name (required), role dropdown with "create new" option, description (optional)
- Edit modal: pre-populated fields, role read-only, status toggle
- Archive persona with confirmation dialog
- Delete persona blocked when agents are linked (409 with agent list)
- Delete persona succeeds with confirmation when no agents linked
- Toast notifications for all CRUD success/failure
- List updates without page reload after mutations
- API endpoints return correct HTTP status codes (200, 201, 400, 404, 409)

## Constraints and Gotchas
- **Existing blueprint:** `personas_bp` already exists with `register` and `validate` endpoints. New endpoints are added to the same blueprint -- no app.py registration changes needed.
- **Slug auto-generation:** Persona slugs are auto-generated via `after_insert` event (`{role_name}-{persona_name}-{id}`). The create flow relies on the existing `register_persona()` service function.
- **Role name is lowercased:** The `register_persona()` service lowercases role names on storage. The role dropdown must display the lowercased name.
- **Delete vs archive semantics:** Archive is a status update (`PUT` with `status: "archived"`), not a separate endpoint. Delete is permanent removal (`DELETE`). Both require confirmation.
- **Agent count includes ended agents:** `persona.agents` relationship includes all linked agents (active and ended). Consider whether to filter to active-only for the count display.
- **Nav tab position:** PRD says "after Help", which means it goes at the end of the nav tabs. Must add to both desktop `tab-btn-group` and mobile `mobile-menu-items`.
- **CSRF token:** All mutating API calls must include CSRF token in headers (existing pattern: `X-CSRF-Token` header from meta tag).
- **Toast function:** Verify `showToast()` exists in `utils.js` or implement if not present. Projects page may use inline toast pattern instead.

## Git Change History

### Related Files
- Routes: `src/claude_headspace/routes/personas.py`
- Models: `src/claude_headspace/models/persona.py`, `src/claude_headspace/models/role.py`
- Services: `src/claude_headspace/services/persona_registration.py`
- Templates: `templates/partials/_header.html`, `templates/projects.html` (pattern reference)
- Static: `static/js/projects.js` (pattern reference)
- Tests: `tests/routes/test_personas.py`, `tests/services/test_persona_registration.py`

### OpenSpec History
- `e8-s1-role-persona-models` (2026-02-20) -- Role and Persona database models
- `e8-s5-persona-filesystem-assets` (2026-02-21) -- filesystem asset creation
- `e8-s6-persona-registration` (2026-02-21) -- registration service + CLI
- `e8-s7-persona-aware-agent-creation` (2026-02-21) -- agent creation with persona
- `e8-s8-session-correlator-persona` (2026-02-21) -- session correlation with persona
- `e8-s10-card-persona-identity` (2026-02-21) -- persona display on agent cards
- `e8-s11-agent-info-persona-display` (2026-02-21) -- persona display in info panel

### Implementation Patterns
- Page route: renders Jinja2 template with `status_counts` context (same as projects page)
- API pattern: Flask route -> query model -> serialize to dict -> return jsonify()
- List serialization: query all, serialize with `[{...} for p in personas]`
- Modal pattern: HTML partial included via `{% include %}`, JS opens/closes/submits
- Table rendering: JS fetches API on page load, builds table rows via DOM manipulation
- Error handling: try/except in routes, return `jsonify({"error": ...})` with appropriate status
- Confirmation: uses existing confirm dialog pattern (e.g., `ConfirmDialog.show()`)

## Q&A History
- No clarifications needed -- PRD is comprehensive with clear requirements and UI specifications

## Dependencies
- No new packages
- Depends on existing E8 sprints S1-S11 (persona models, registration service, agent card display)
- Uses Persona model (name, slug, status, description, role_id, created_at)
- Uses Role model (id, name, description, created_at)
- Uses `register_persona()` service function for creation
- Uses existing `confirm-dialog.js` for confirmation dialogs
- Uses existing `utils.js` for toast notifications and CSRF helpers

## Testing Strategy
- Route tests for all 6 new endpoints (page, list, detail, update, delete, roles)
- Validation tests: empty name, missing fields, non-existent slugs
- Constraint tests: delete blocked when agents linked (409)
- Regression: existing register and validate endpoints still work
- Visual verification: Playwright screenshots of list page and modal

## OpenSpec References
- proposal.md: openspec/changes/e8-s15-persona-list-crud/proposal.md
- tasks.md: openspec/changes/e8-s15-persona-list-crud/tasks.md
- spec.md: openspec/changes/e8-s15-persona-list-crud/specs/persona-list-crud/spec.md
