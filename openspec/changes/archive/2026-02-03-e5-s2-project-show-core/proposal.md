## Why

Claude Headspace has a projects list page for CRUD management but no dedicated page to view a single project's full detail. Project information is scattered across the dashboard, waypoint editor, brain reboot modal, and activity page. Users cannot see a project's complete state — metadata, waypoint, brain reboot, and progress summary — from a single page.

This change introduces a Project Show page at `/projects/<slug>` that consolidates all project detail into one view, and simplifies the projects list into a navigation hub.

## What Changes

- Add `slug` field to Project model (unique, non-nullable, indexed) with auto-generation from project name
- Add database migration to add slug column and backfill existing projects
- Add `GET /projects/<slug>` route for the project show page
- Create `project_show.html` template with metadata, controls, waypoint, brain reboot, and progress summary sections
- Create `project_show.js` for data loading and control actions (edit, delete, pause/resume, regenerate, export)
- Simplify projects list: project names become clickable links, remove inline action buttons (edit, delete, pause)
- Add link to project show page from brain reboot slider modal

## Impact

- Affected specs: project (model), projects (routes/UI)
- Affected code:
  - `src/claude_headspace/models/project.py` — add slug field, slug generation logic
  - `src/claude_headspace/routes/projects.py` — add show page route, slug resolution
  - `templates/projects.html` — simplify to navigation hub
  - `static/js/projects.js` — update rendering, remove action handlers
  - `templates/partials/_brain_reboot_modal.html` — add show page link
  - `templates/partials/_project_form_modal.html` — handle slug update on name change
- New files:
  - `templates/project_show.html` — show page template
  - `static/js/project_show.js` — show page JavaScript
  - `migrations/versions/xxxx_add_project_slug.py` — slug migration
  - `tests/routes/test_project_show.py` — route tests
- Prior changes: builds on `e4-s2b-project-controls-ui` (project controls backend + UI)
