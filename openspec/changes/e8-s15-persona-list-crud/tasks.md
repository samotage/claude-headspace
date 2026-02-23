## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend (Routes + API)

- [ ] 2.1 Add page route `GET /personas` to `personas_bp` in `routes/personas.py` -- renders `personas.html` template with `status_counts` context (follows `projects_page()` pattern)
- [ ] 2.2 Add `GET /api/personas` endpoint -- returns JSON list of all personas with role name, status, linked agent count, created_at; ordered by `created_at` desc
- [ ] 2.3 Add `GET /api/personas/<slug>` endpoint -- returns single persona detail by slug (name, role, description, status, agent count, created_at); 404 if not found
- [ ] 2.4 Add `PUT /api/personas/<slug>` endpoint -- accepts JSON updates to name, description, status; validates required fields; 400 on validation error, 404 if not found
- [ ] 2.5 Add `DELETE /api/personas/<slug>` endpoint -- deletes persona only if no linked agents; returns 409 with agent list if agents linked; 404 if not found
- [ ] 2.6 Add `GET /api/roles` endpoint -- returns JSON list of all roles (id, name, description, created_at)

### Frontend (Templates + JavaScript)

- [ ] 2.7 Create `templates/personas.html` -- extends `base.html`, includes `_header.html`, table with columns (Name, Role, Status, Agents, Created), empty state, "New Persona" button, loading state
- [ ] 2.8 Create `templates/partials/_persona_form_modal.html` -- follows `_project_form_modal.html` pattern (fixed position, backdrop blur, header/body/footer); fields: Name (text, required), Role (dropdown + inline create), Description (textarea), Status toggle (edit only)
- [ ] 2.9 Modify `templates/partials/_header.html` -- add "personas" tab link after "help" in desktop `tab-btn-group` and mobile drawer `mobile-menu-items`
- [ ] 2.10 Create `static/js/personas.js` -- `PersonasPage` module:
  - Load and render persona list from `GET /api/personas`
  - Open create modal (fetch roles for dropdown, "Create new role..." option)
  - Open edit modal (pre-populate from persona data, role read-only)
  - Submit create via `POST /api/personas/register` (existing endpoint)
  - Submit edit via `PUT /api/personas/<slug>`
  - Archive action via `PUT /api/personas/<slug>` with `status: "archived"` + confirmation dialog
  - Delete action via `DELETE /api/personas/<slug>` + confirmation dialog
  - Inline form validation (empty name, empty role)
  - Toast notifications for success/failure
  - List refresh after each mutation

## 3. Testing (Phase 3)

- [ ] 3.1 Route tests: `GET /personas` page returns 200
- [ ] 3.2 Route tests: `GET /api/personas` returns persona list with correct fields
- [ ] 3.3 Route tests: `GET /api/personas/<slug>` returns persona detail; 404 for missing
- [ ] 3.4 Route tests: `PUT /api/personas/<slug>` updates persona; 400 for invalid; 404 for missing
- [ ] 3.5 Route tests: `DELETE /api/personas/<slug>` deletes when no agents; 409 when agents linked; 404 for missing
- [ ] 3.6 Route tests: `GET /api/roles` returns role list
- [ ] 3.7 Regression: existing persona register and validate endpoints still work

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Visual verification -- Playwright screenshot of personas list page
- [ ] 4.4 Visual verification -- Playwright screenshot of create/edit modal
