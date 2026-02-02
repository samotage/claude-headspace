## Why

E4-S2a delivered the backend API for project CRUD, settings, auto-discovery removal, and inference gating. Without a UI, users must use curl or similar tools to manage projects. This change adds a browser-based projects management page with add/edit/delete modals, inference pause/resume controls, header navigation, and real-time SSE updates.

## What Changes

- New page: `/projects` management page with project list table, add/edit modals, delete confirmation, pause/resume toggle
- New template: `templates/projects.html` (page) and `templates/partials/_project_form_modal.html` (modal)
- New JS: `static/js/projects.js` for API interactions, SSE, and modal handling
- Modify: `templates/partials/_header.html` to add "Projects" tab between Dashboard and Objective (desktop + mobile)
- Modify: `src/claude_headspace/routes/projects.py` to add `/projects` page route
- New test: `tests/routes/test_projects_page.py` for page route tests

## Impact

- Affected specs: project-controls-ui (new capability)
- Affected code:
  - `templates/projects.html` — **NEW** projects management page template
  - `templates/partials/_project_form_modal.html` — **NEW** add/edit project modal partial
  - `static/js/projects.js` — **NEW** projects page JavaScript
  - `templates/partials/_header.html` — add "Projects" tab to navigation (desktop + mobile)
  - `src/claude_headspace/routes/projects.py` — add `/projects` page route to existing blueprint
  - `tests/routes/test_projects_page.py` — **NEW** page route tests
