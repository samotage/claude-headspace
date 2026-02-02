## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Projects Page Route

- [x] 2.1.1 Add `/projects` page route to `routes/projects.py` blueprint — renders `projects.html` template with status_counts context for header stats bar

### 2.2 Projects Page Template

- [x] 2.2.1 Create `templates/projects.html` extending `base.html` with:
  - Header partial include
  - Project list table (name, path, agent count, inference status, actions)
  - "Add Project" button
  - Empty state message when no projects registered
  - Include project form modal partial
  - Include delete confirmation dialog
  - Script tag for `projects.js`

### 2.3 Project Form Modal

- [x] 2.3.1 Create `templates/partials/_project_form_modal.html` with:
  - Modal overlay and content container following waypoint editor pattern
  - Form fields: name (required), path (required), github_repo (optional), description (optional textarea)
  - Cancel and Save buttons
  - Inline error display area
  - Dynamic title ("Add Project" vs "Edit Project")

### 2.4 Header Navigation

- [x] 2.4.1 Modify `templates/partials/_header.html`:
  - Add "Projects" tab link between Dashboard and Objective in desktop nav
  - Add "Projects" mobile menu item between Dashboard and Objective in mobile nav
  - Active state detection using `request.endpoint == 'projects.projects_page'`

### 2.5 Projects JavaScript

- [x] 2.5.1 Create `static/js/projects.js` with:
  - `loadProjects()` — fetch GET /api/projects and render table rows
  - `openAddModal()` — open modal in add mode (empty fields)
  - `openEditModal(projectId)` — fetch project detail and open modal in edit mode (pre-populated)
  - `submitProject()` — POST or PUT depending on mode, handle validation errors inline
  - `openDeleteDialog(projectId, projectName, agentCount)` — show confirmation dialog
  - `confirmDelete(projectId)` — DELETE project and refresh list
  - `togglePause(projectId, currentState)` — PUT settings API to toggle inference_paused
  - SSE listener for `project_changed` and `project_settings_changed` events to auto-refresh list
  - Initial `loadProjects()` call on DOMContentLoaded

### 2.6 Delete Confirmation Dialog

- [x] 2.6.1 Add delete confirmation dialog HTML in `projects.html`:
  - Modal with project name and agent count warning
  - Cancel and Delete buttons
  - Dynamic content updated by JavaScript

## 3. Testing (Phase 3)

### 3.1 Projects Page Route Tests

- [x] 3.1.1 Create `tests/routes/test_projects_page.py` with:
  - Test GET /projects returns 200 with projects.html template
  - Test page route includes status_counts context
  - Test page route is accessible (not 404)

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
