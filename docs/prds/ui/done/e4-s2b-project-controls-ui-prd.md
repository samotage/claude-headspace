---
validation:
  status: valid
  validated_at: '2026-02-02T13:15:11+11:00'
---

## Product Requirements Document (PRD) — Project Controls UI

**Project:** Claude Headspace
**Scope:** Projects management page, add/edit/delete modals, header navigation, inference pause/resume UI controls
**Sprint:** E4-S2b
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft
**Depends on:** E4-S2a (Project Controls Backend)

---

## Executive Summary

This PRD defines the UI layer for the project controls system. It builds on top of the backend API endpoints delivered in E4-S2a to provide a dedicated `/projects` management page where users can register, edit, and delete projects, and toggle inference pause/resume — all from the browser.

The projects page follows the existing dashboard patterns: vanilla JavaScript, Jinja2 templates, modal forms (following the waypoint editor pattern), and real-time updates via SSE. A "Projects" tab is added to the header navigation between Dashboard and Objective.

---

## 1. Context & Purpose

### 1.1 Context

E4-S2a delivers the backend API for project CRUD, settings management, auto-discovery removal, and inference gating. Without a UI, users would need to use `curl` or similar tools to manage projects — impractical for day-to-day use.

This PRD provides the browser-based interface that makes project management accessible and intuitive, consistent with the existing dashboard experience.

### 1.2 Target User

Developers using the Claude Headspace dashboard who need to register new projects, remove stale ones, and control inference costs per project.

### 1.3 Success Moment

The user opens `/projects`, sees their registered projects listed with agent counts and inference status. They click "Add Project" to register a new codebase they're starting work on. They pause inference on a project they're not actively prioritising. The UI updates in real-time as changes are made.

---

## 2. Scope

### 2.1 In Scope

- **Projects management page:** Dedicated `/projects` page with project list table
- **Add project modal:** Form to register a new project (name, path, github_repo, description)
- **Edit project modal:** Pre-populated form to update project metadata
- **Delete confirmation dialog:** Warning dialog showing cascade impact (agent count)
- **Pause/resume toggle:** Inline control to toggle inference pause from the projects list
- **Paused indicator:** Visual indicator on projects with inference paused
- **Header navigation:** "Projects" tab added between Dashboard and Objective
- **Real-time updates:** SSE listener to update the projects list when changes occur
- **Tests:** Route tests for the `/projects` page endpoint

### 2.2 Out of Scope

- Backend API endpoints (delivered in E4-S2a)
- Inference gating logic (delivered in E4-S2a)
- Database migration (delivered in E4-S2a)
- Auto-discovery removal (delivered in E4-S2a)
- Project archiving / soft delete
- Bulk project operations
- Dashboard project cards showing paused indicator (future enhancement)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Navigate to `/projects` — see a list of all registered projects with name, path, agent count, and inference status
2. Click "Add Project" — modal opens with form fields (name, path, github_repo, description)
3. Submit a valid project — project created, appears in list immediately without page reload
4. Submit a duplicate path — inline error message displayed, no duplicate created
5. Click Edit on a project — modal opens pre-populated with current values
6. Update project metadata — changes saved, list refreshed without page reload
7. Click Delete on a project — confirmation dialog appears with agent count warning
8. Confirm delete — project removed from list without page reload
9. Click pause toggle on a project — inference status updates immediately
10. Click resume toggle — inference status updates immediately
11. Paused indicator is visible and distinct on paused projects
12. "Projects" tab visible in header navigation between Dashboard and Objective
13. Projects tab shows active styling when on `/projects` page
14. SSE events update the project list in real-time (e.g., if another tab or API call creates a project)

### 3.2 Non-Functional Success Criteria

1. Projects page loads within 500ms
2. Modal forms follow the established waypoint editor pattern for visual consistency
3. All UI interactions work without external JavaScript dependencies (vanilla JS only)

---

## 4. Functional Requirements (FRs)

### Projects Management Page

**FR1:** The system shall provide a `/projects` page accessible via a "Projects" tab in the header navigation, positioned between Dashboard and Objective.

**FR2:** The projects page shall display a table of all registered projects showing: name, path, active agent count, inference status (active/paused), and an actions menu (edit, delete, pause/resume).

**FR3:** The projects page shall provide an "Add Project" button that opens a modal form with fields: name (required), path (required), github_repo (optional), description (optional).

**FR4:** The add project modal shall validate that name and path are non-empty before submission and display server-side validation errors (e.g., duplicate path) inline.

**FR5:** Each project row shall have an actions menu (or action buttons) providing: Edit, Delete, and Pause/Resume inference.

**FR6:** The Edit action shall open a modal form pre-populated with the project's current values, allowing updates to name, path, github_repo, and description.

**FR7:** The Delete action shall show a confirmation dialog stating the project name and warning that all agents will be deleted. The dialog shall require explicit confirmation before proceeding.

**FR8:** The Pause/Resume action shall toggle `inference_paused` via the settings API and update the project's status indicator in the list without a full page reload.

**FR9:** The projects page shall display a paused indicator (e.g., pause icon, "Paused" label) on projects with `inference_paused = true`.

### Header Navigation

**FR10:** The header navigation (`_header.html`) shall include a "Projects" tab link positioned between Dashboard and Objective, in both desktop and mobile navigation.

**FR11:** The Projects tab shall use the active state styling when the user is on the `/projects` page, consistent with other navigation tabs.

### Real-Time Updates

**FR12:** The projects page shall listen for `project_changed` and `project_settings_changed` SSE events and update the project list in real-time without requiring a page reload.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The projects page shall use vanilla JavaScript (no external dependencies) consistent with the existing dashboard UI pattern.

**NFR2:** Modal forms shall follow the pattern established by the waypoint editor (E2-S2) for consistency.

**NFR3:** All new routes shall have route tests following the existing test architecture.

---

## 6. UI Overview

### Projects Page Layout

```
+-----------------------------------------------------------------------+
|  CLAUDE >_headspace    [Dashboard] [Projects] [Objective] [Logging]...  |
+-----------------------------------------------------------------------+
|                                                                         |
|  Projects                                            [+ Add Project]    |
|  -------------------------------------------------------------------   |
|                                                                         |
|  +-------------------------------------------------------------------+ |
|  | Name              | Path                 | Agents | Status    | .. | |
|  +-------------------------------------------------------------------+ |
|  | claude-headspace  | ~/dev/.../headspace  | 3      | Active    | :  | |
|  | my-webapp         | ~/dev/my-webapp      | 1      | Paused    | :  | |
|  | api-server        | ~/dev/api-server     | 0      | Active    | :  | |
|  +-------------------------------------------------------------------+ |
|                                                                         |
|  : menu -> Edit | Delete | Pause/Resume                                |
|                                                                         |
+-----------------------------------------------------------------------+
```

### Add/Edit Project Modal

```
+-------------------------------------------+
|  Add Project                         [x]  |
+-------------------------------------------+
|                                           |
|  Name *        [________________________] |
|  Path *        [________________________] |
|  GitHub Repo   [________________________] |
|  Description   [________________________] |
|                [________________________] |
|                                           |
|              [Cancel]  [Save Project]     |
+-------------------------------------------+
```

### Delete Confirmation Dialog

```
+-------------------------------------------+
|  Delete Project                      [x]  |
+-------------------------------------------+
|                                           |
|  Are you sure you want to delete          |
|  "claude-headspace"?                      |
|                                           |
|  This will also delete 3 agents and       |
|  all their tasks and turns.               |
|                                           |
|              [Cancel]  [Delete]           |
+-------------------------------------------+
```

---

## 7. Technical Context (for implementers)

### Page Route

The `/projects` page route should be added to the `projects_bp` blueprint created in E4-S2a. It renders the `projects.html` template and does not need to pre-load project data — the page fetches data via the API on load using JavaScript.

### Modal Forms

Follow the waypoint editor pattern (`templates/partials/_waypoint_modal.html`) for add/edit modals:
- Modal HTML in a partial template (`_project_form_modal.html`)
- Included in the main `projects.html` template
- JavaScript handles open/close, form submission via `fetch()`, and error display

### SSE Integration

The projects page should connect to the existing SSE endpoint (`/sse?types=project_changed,project_settings_changed`) and update the project table when events arrive. Follow the pattern used by the dashboard for SSE connection management.

### Existing Patterns to Follow

- **Modal forms:** Follow the waypoint editor pattern (`templates/partials/_waypoint_modal.html`)
- **Page template:** Follow the structure of `templates/logging.html` or `templates/objective.html` for a full-page layout
- **Active tab detection:** Follow the pattern in `_header.html` for highlighting the active navigation tab
- **Vanilla JS:** Use `fetch()` for API calls, DOM manipulation for updates — no external libraries

---

## 8. Files to Create

| File | Purpose |
|---|---|
| `templates/projects.html` | Projects management page |
| `templates/partials/_project_form_modal.html` | Add/edit project modal |
| `tests/routes/test_projects_page.py` | Page route tests |

## 9. Files to Modify

| File | Change |
|---|---|
| `src/claude_headspace/routes/projects.py` | Add `/projects` page route (blueprint created in E4-S2a) |
| `templates/partials/_header.html` | Add "Projects" tab between Dashboard and Objective (desktop + mobile) |

---

## 10. Risks & Mitigation

### Risk 1: Users Forget Projects Are Paused

**Risk:** Inference is paused for a project, summaries stop generating, but the user forgets and wonders why summaries are stale.

**Mitigation:**
- Visible "Paused" indicator on the projects list
- SSE event on pause/resume ensures the UI updates immediately
- `inference_paused_at` timestamp could be displayed to show how long inference has been paused

### Risk 2: Cascade Delete Removes Valuable History

**Risk:** Deleting a project removes all agents, tasks, turns, and events — potentially losing useful historical data.

**Mitigation:**
- Confirmation dialog explicitly states what will be deleted (agent count)
- This is the intended behavior — orphaned agents serve no purpose without a project
- Future sprint could add project archiving (out of scope for this PRD)

---

## 11. Acceptance Criteria

### Projects Page

- [ ] Navigate to `/projects` — see list of all registered projects
- [ ] Projects table shows name, path, agent count, inference status, actions
- [ ] Click "Add Project" — modal opens with form (name, path, github_repo, description)
- [ ] Submit valid project — project created, appears in list without reload
- [ ] Submit duplicate path — inline error message, no duplicate created
- [ ] Click Edit on project — modal opens with current values
- [ ] Update project — changes saved, list refreshed without reload
- [ ] Click Delete on project — confirmation dialog appears with agent count warning
- [ ] Confirm delete — project removed from list without reload

### Inference Controls (UI)

- [ ] Click pause toggle — project shows "Paused" status immediately
- [ ] Click resume toggle — project shows "Active" status immediately
- [ ] Paused indicator is visually distinct

### Navigation

- [ ] "Projects" tab visible in header between Dashboard and Objective
- [ ] Tab shows active state when on `/projects` page
- [ ] Tab works in both desktop and mobile navigation

### Real-Time Updates

- [ ] Project created via another tab/API — list updates via SSE
- [ ] Settings changed via another tab/API — status updates via SSE
