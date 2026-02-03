## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Model & Migration

- [x] 2.1 Add `slug` field to Project model with unique constraint, non-nullable, indexed
- [x] 2.2 Add `generate_slug()` utility function (lowercase, hyphens, collapse, strip, collision handling)
- [x] 2.3 Add slug auto-generation on project creation (hook into model or route)
- [x] 2.4 Add slug regeneration on project name update
- [x] 2.5 Create Alembic migration: add slug column, backfill existing rows from name, add unique constraint

### Show Page Route

- [x] 2.6 Add `GET /projects/<slug>` route to projects blueprint (resolve slug to project, render template)
- [x] 2.7 Return 404 for non-existent slugs

### Show Page Template & JavaScript

- [x] 2.8 Create `templates/project_show.html` extending base template with:
  - Back to Projects link
  - Project metadata section (name, path, GitHub repo linked, branch, description, created date)
  - Inference status display (active/paused with timestamp and reason)
  - Control actions bar (Edit, Delete, Pause/Resume, Regenerate Description, Refetch GitHub Info)
  - Waypoint section (rendered markdown, empty state, edit link)
  - Brain reboot section (rendered markdown, date + time-ago, empty state, Regenerate + Export buttons)
  - Progress summary section (rendered markdown, empty state, Regenerate button)
- [x] 2.9 Create `static/js/project_show.js` with:
  - Load project metadata via `GET /api/projects/<id>`
  - Load waypoint via `GET /api/projects/<id>/waypoint`
  - Load brain reboot via `GET /api/projects/<id>/brain-reboot`
  - Load progress summary via `GET /api/projects/<id>/progress-summary`
  - Edit action (open modal, submit via `PUT /api/projects/<id>`, update display, handle slug change)
  - Delete action (confirmation dialog, `DELETE /api/projects/<id>`, redirect to `/projects`)
  - Pause/Resume toggle via `PUT /api/projects/<id>/settings`
  - Regenerate Description via `POST /api/projects/<id>/detect-metadata`
  - Refetch GitHub Info via `POST /api/projects/<id>/detect-metadata`
  - Regenerate brain reboot via `POST /api/projects/<id>/brain-reboot`
  - Export brain reboot via `POST /api/projects/<id>/brain-reboot/export`
  - Regenerate progress summary via `POST /api/projects/<id>/progress-summary`
  - Time-ago display for brain reboot timestamp

### Projects List Changes

- [x] 2.10 Update `templates/projects.html`: make project names clickable links to `/projects/<slug>`
- [x] 2.11 Update `templates/projects.html`: remove Edit, Delete, Pause/Resume action buttons from list rows
- [x] 2.12 Update `static/js/projects.js`: render project names as links, remove action handler code for inline buttons

### Brain Reboot Modal Link

- [x] 2.13 Update `templates/partials/_brain_reboot_modal.html`: add link to project show page `/projects/<slug>`

## 3. Testing (Phase 3)

- [x] 3.1 Create `tests/routes/test_project_show.py` with route tests:
  - GET `/projects/<slug>` returns 200 with valid slug
  - GET `/projects/<slug>` returns 404 with invalid slug
  - Slug auto-generation on project creation
  - Slug regeneration on project name update
  - Slug collision handling (numeric suffix)
- [x] 3.2 Update existing project route tests if affected by slug changes
- [x] 3.3 Run targeted tests: `pytest tests/routes/test_project_show.py tests/routes/test_projects.py`

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
