---
validation:
  status: valid
  validated_at: '2026-02-04T09:38:22+11:00'
---

## Product Requirements Document (PRD) — Project Show Page (Core)

**Project:** Claude Headspace
**Scope:** Project show page with slug-based routing, metadata display, control actions, waypoint, brain reboot, progress summary, and navigation changes
**Sprint:** E5-S2
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft
**Depends on:** E4-S2a (Project Controls Backend), E4-S2b (Project Controls UI)

---

## Executive Summary

Claude Headspace currently has a projects list page for CRUD management but no dedicated page to view a single project's full detail. Project information is scattered across the dashboard (Kanban columns), waypoint editor (modal), brain reboot (slider modal), and activity page — with no unified view.

This PRD introduces a Project Show page at `/projects/<slug>` that serves as the canonical detail view for a project. It consolidates project metadata, control actions (edit, delete, pause/resume, regenerate description, refetch GitHub info), waypoint content, brain reboot output, and progress summary into a single page. The projects list is simplified to a navigation hub — clicking a project name navigates to its show page, and inline action buttons (edit, delete, pause) are removed from the list.

This is Part 1 of 2. Part 2 (E5-S3) adds the accordion object tree (agents, tasks, turns) and activity metrics.

---

## 1. Context & Purpose

### 1.1 Context

The E4-S2b sprint delivered a projects list page with modal-based CRUD and inline pause/resume controls. While functional for management, it provides no way to see a project's full state — its waypoint, brain reboot, progress summary, or associated agents and metrics. Users must navigate between multiple pages and modals to build a complete picture of a project.

The dashboard's project columns show a subset of this data (agent cards, waypoint preview, brain reboot button) but in a constrained Kanban layout optimised for cross-project monitoring, not deep single-project exploration.

### 1.2 Target User

Developers using Claude Headspace who want to understand the full state of a specific project — its current waypoint/roadmap, recent brain reboot, progress summary, and configuration — from a single page.

### 1.3 Success Moment

The user clicks a project name on the projects list and lands on a dedicated page showing the project's metadata, current waypoint, last brain reboot with "generated 2 hours ago" timestamp, and progress summary. They click "Regenerate" to get a fresh brain reboot, then toggle inference pause — all without leaving the page or opening modals.

---

## 2. Scope

### 2.1 In Scope

- **Slug-based routing:** URL uses a slug derived from the project name (e.g., `/projects/claude-headspace`)
- **Project model change:** Add `slug` field to Project model with unique constraint and database migration
- **Slug lifecycle:** Slug updates when project name changes; generated automatically from name
- **Project show page:** Dedicated page at `/projects/<slug>` rendering project detail
- **Metadata display:** Project name, path, GitHub repo (linked), current branch, description, creation date
- **Control actions on show page:**
  - Edit project metadata (name, path, github_repo, description)
  - Delete project (with confirmation)
  - Pause/Resume inference
  - Regenerate description (triggers LLM-based description generation)
  - Refetch GitHub info (triggers git metadata detection)
- **Waypoint section:** Display current waypoint content with link to edit
- **Brain reboot section:** Display last generated brain reboot with generation date and time-ago in words, plus regenerate and export controls
- **Progress summary section:** Display current progress summary with regenerate control
- **Projects list changes:**
  - Project name becomes a clickable link to the show page
  - Remove Edit button from list (edit is on show page)
  - Remove Delete button from list (delete is on show page)
  - Remove Pause/Resume toggle from list (pause is on show page)
- **Brain reboot modal link:** Add a link to the project show page from the brain reboot slider modal
- **Route tests:** Tests for the new show page route

### 2.2 Out of Scope

- Accordion object tree for agents/tasks/turns (E5-S3)
- Activity metrics display (E5-S3)
- Archive history display (E5-S3)
- Inference metrics display (E5-S3)
- SSE real-time updates on the show page (E5-S3)
- New backend API endpoints beyond slug lookup (existing APIs cover data needs)
- Editing waypoint content inline on the show page (uses existing editor modal or link)
- Agent control actions (focus, dismiss, respond) from the show page
- Mobile-first responsive design (follow existing patterns)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Navigate to `/projects/claude-headspace` — see the project's full metadata, waypoint, brain reboot, and progress summary
2. Click a project name on the `/projects` list — navigates to `/projects/<slug>`
3. The projects list no longer shows Edit, Delete, or Pause/Resume action buttons
4. Edit project metadata from the show page — changes reflect immediately
5. When project name is edited, the slug updates and the page URL changes to match
6. Delete project from the show page — confirmation dialog shown, redirects to `/projects` list after deletion
7. Pause/Resume inference from the show page — status indicator updates immediately
8. Click "Regenerate Description" — description field updates with LLM-generated content
9. Click "Refetch GitHub Info" — GitHub repo and branch fields update from git metadata
10. Waypoint section displays current waypoint content (rendered markdown)
11. Brain reboot section displays last generated content with date and time-ago (e.g., "Generated 2 hours ago")
12. Click "Regenerate" on brain reboot — new brain reboot generated and displayed
13. Click "Export" on brain reboot — exported to project filesystem
14. Progress summary section displays current summary with regenerate option
15. Brain reboot slider modal includes a link to the project show page
16. Navigating to a slug that doesn't exist shows a 404 page or redirects to projects list

### 3.2 Non-Functional Success Criteria

1. Show page loads within 500ms (metadata + waypoint + cached brain reboot)
2. Control actions follow existing UI patterns (modals, confirmation dialogs) for consistency
3. All new routes have route tests

---

## 4. Functional Requirements (FRs)

### Slug Model & Routing

**FR1:** The Project model shall have a `slug` field that is unique, non-nullable, and indexed. The slug is derived from the project name using URL-safe transformation (lowercase, hyphens for spaces/special characters).

**FR2:** When a project is created, a slug shall be automatically generated from the project name. If the generated slug conflicts with an existing slug, a numeric suffix shall be appended (e.g., `my-project-2`).

**FR3:** When a project name is updated, the slug shall be regenerated to match the new name. The old slug is not preserved.

**FR4:** A database migration shall add the `slug` column to the `project` table, populating existing rows with slugs derived from their current names.

**FR5:** The project show page shall be accessible at `/projects/<slug>` where `<slug>` matches a project's slug field.

**FR6:** If the slug does not match any project, the system shall return a 404 response.

### Project Show Page

**FR7:** The project show page shall display the project's metadata: name, path, GitHub repository (as a clickable link if present), current branch, description (rendered as markdown), and creation date.

**FR8:** The project show page shall display the project's inference status: whether inference is active or paused, and if paused, the paused-at timestamp and reason.

**FR9:** The project show page shall provide a control area with the following actions:
- Edit (opens edit form for name, path, github_repo, description)
- Delete (with confirmation dialog showing cascade warning)
- Pause/Resume inference toggle
- Regenerate Description button
- Refetch GitHub Info button

**FR10:** The Edit action shall allow updating project metadata. When the name changes, the page URL shall update to reflect the new slug.

**FR11:** The Delete action shall show a confirmation dialog warning about cascade deletion (agent count). On confirmation, the project is deleted and the user is redirected to `/projects`.

**FR12:** The Regenerate Description action shall trigger the existing metadata detection endpoint to generate an LLM-based description and update the display without a full page reload.

**FR13:** The Refetch GitHub Info action shall trigger the existing metadata detection endpoint to re-read git remote URL and branch, updating the display without a full page reload.

### Waypoint Section

**FR14:** The project show page shall include a Waypoint section that displays the current waypoint content rendered as markdown.

**FR15:** If no waypoint exists for the project, the section shall display an empty state with guidance.

**FR16:** The waypoint section shall include a link or button to edit the waypoint (opening the existing waypoint editor modal or navigating to edit).

### Brain Reboot Section

**FR17:** The project show page shall include a Brain Reboot section that displays the last generated brain reboot content rendered as markdown.

**FR18:** The brain reboot section shall display the generation timestamp in two formats: the absolute date/time and a relative time-ago in words (e.g., "Generated 2 hours ago").

**FR19:** If no brain reboot has been generated, the section shall display an empty state with a "Generate" button.

**FR20:** The brain reboot section shall provide a "Regenerate" button to trigger a fresh brain reboot generation. While generating, a loading indicator shall be shown.

**FR21:** The brain reboot section shall provide an "Export" button to export the brain reboot to the project's filesystem.

### Progress Summary Section

**FR22:** The project show page shall include a Progress Summary section that displays the current progress summary rendered as markdown.

**FR23:** If no progress summary exists, the section shall display an empty state with a "Generate" button.

**FR24:** The progress summary section shall provide a "Regenerate" button to trigger a fresh progress summary generation.

### Projects List Changes

**FR25:** On the projects list page (`/projects`), each project name shall be a clickable link that navigates to `/projects/<slug>`.

**FR26:** The projects list shall no longer display Edit, Delete, or Pause/Resume action buttons or menus per project row. These actions are now exclusively on the project show page.

**FR27:** The projects list shall retain the "Add Project" button for creating new projects.

### Brain Reboot Modal Link

**FR28:** The brain reboot slider modal (triggered from the dashboard) shall include a link to the project show page (`/projects/<slug>`) allowing the user to navigate to the full project detail view.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The project show page shall use vanilla JavaScript (no external dependencies) consistent with the existing UI pattern.

**NFR2:** The show page layout shall follow the established page patterns (base template, header navigation, content area) for visual consistency.

**NFR3:** All new routes shall have route tests following the existing test architecture.

**NFR4:** The slug generation shall handle Unicode characters, special characters, and edge cases (empty string, all-special-characters) gracefully.

---

## 6. UI Overview

### Project Show Page Layout

```
+-----------------------------------------------------------------------+
|  CLAUDE >_headspace    [Dashboard] [Projects] [Activity] [Objective]...|
+-----------------------------------------------------------------------+
|                                                                        |
|  < Back to Projects                                                    |
|                                                                        |
|  claude-headspace                                                      |
|  ~/dev/otagelabs/claude_headspace                                      |
|  GitHub: otagelabs/claude_headspace  |  Branch: development            |
|  Created: 2 Jan 2026                                                   |
|                                                                        |
|  Description:                                                          |
|  Kanban-style web dashboard for tracking Claude Code sessions          |
|  across multiple projects...                                           |
|                                                                        |
|  +--------------------------------------------------------------+     |
|  | [Edit] [Delete] [Pause Inference] [Regen Desc] [Refetch Git] |     |
|  +--------------------------------------------------------------+     |
|                                                                        |
|  Inference: Active                                                     |
|  (or: Paused since 3 Feb 2026 — "Cost control")                       |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  Waypoint                                                    [Edit]    |
|  ------------------------------------------------------------------   |
|  [Rendered markdown content of waypoint.md]                            |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  Brain Reboot                          Generated 2 hours ago           |
|  ------------------------------------------------------------------   |
|  [Rendered markdown content of last brain reboot]                      |
|                                                                        |
|  [Regenerate]  [Export]                                                |
|                                                                        |
|  ================================================================      |
|                                                                        |
|  Progress Summary                                        [Regenerate] |
|  ------------------------------------------------------------------   |
|  [Rendered markdown content of progress summary]                       |
|                                                                        |
+-----------------------------------------------------------------------+
```

### Simplified Projects List

```
+-----------------------------------------------------------------------+
|  Projects                                            [+ Add Project]   |
|  -------------------------------------------------------------------  |
|                                                                        |
|  +------------------------------------------------------------------+ |
|  | Name                | Path                 | Agents | Status     | |
|  +------------------------------------------------------------------+ |
|  | claude-headspace    | ~/dev/.../headspace  | 3      | Active     | |
|  | my-webapp           | ~/dev/my-webapp      | 1      | Paused     | |
|  | api-server          | ~/dev/api-server     | 0      | Active     | |
|  +------------------------------------------------------------------+ |
|                                                                        |
|  (project names are clickable links to /projects/<slug>)               |
|  (no Edit/Delete/Pause action buttons in list)                         |
+-----------------------------------------------------------------------+
```

---

## 7. Technical Context (for implementers)

### Slug Generation

Use a standard slugify approach: lowercase, replace spaces and special characters with hyphens, collapse multiple hyphens, strip leading/trailing hyphens. Python's `re` module or a lightweight utility function is sufficient — no external slugify library needed.

### Migration

Add `slug` column to `project` table. Backfill existing rows by generating slugs from current `name` values. Handle potential conflicts during backfill with numeric suffixes.

### Page Route

Add `GET /projects/<slug>` to `projects_bp` blueprint. Resolve slug to project via DB query. Render a new `project_show.html` template with project data. The page fetches additional data (waypoint, brain reboot, progress summary) via existing API endpoints using JavaScript after initial page load.

### Existing API Endpoints Used

| Endpoint | Purpose on Show Page |
|----------|---------------------|
| `GET /api/projects/<id>` | Project metadata + agents |
| `PUT /api/projects/<id>` | Edit metadata |
| `DELETE /api/projects/<id>` | Delete project |
| `GET/PUT /api/projects/<id>/settings` | Pause/resume |
| `POST /api/projects/<id>/detect-metadata` | Regenerate description, refetch git |
| `GET /api/projects/<id>/waypoint` | Load waypoint content |
| `GET /api/projects/<id>/brain-reboot` | Load last brain reboot |
| `POST /api/projects/<id>/brain-reboot` | Generate brain reboot |
| `POST /api/projects/<id>/brain-reboot/export` | Export brain reboot |
| `GET /api/projects/<id>/progress-summary` | Load progress summary |
| `POST /api/projects/<id>/progress-summary` | Generate progress summary |

### Patterns to Follow

- **Page template:** Follow `templates/projects.html` or `templates/activity.html` structure
- **Control actions:** Follow the modal/dialog patterns from `_project_form_modal.html`
- **Markdown rendering:** Follow the brain reboot modal's prose rendering pattern
- **Time-ago display:** Calculate relative time in JavaScript (e.g., "2 hours ago", "3 days ago")

### Files to Create

| File | Purpose |
|------|---------|
| `templates/project_show.html` | Project show page template |
| `static/js/project_show.js` | Show page JavaScript (data loading, controls) |
| `migrations/versions/xxxx_add_project_slug.py` | Add slug column migration |
| `tests/routes/test_project_show.py` | Route tests for show page |

### Files to Modify

| File | Change |
|------|--------|
| `src/claude_headspace/models/project.py` | Add `slug` field |
| `src/claude_headspace/routes/projects.py` | Add show page route, slug resolution |
| `templates/projects.html` | Make project names clickable links, remove action buttons |
| `static/js/projects.js` | Update to render links, remove action handlers |
| `templates/partials/_brain_reboot_modal.html` | Add link to project show page |
| `templates/partials/_project_form_modal.html` | May need slug update handling on name change |

---

## 8. Risks & Mitigation

### Risk 1: Slug Collisions

**Risk:** Two projects could generate the same slug (e.g., "My Project" and "my-project").

**Mitigation:** Unique constraint on slug column. Slug generation appends numeric suffix on collision.

### Risk 2: Bookmarked URLs Break on Rename

**Risk:** Users bookmark a project show URL, then rename the project. The old URL returns 404.

**Mitigation:** Accepted trade-off per workshop decision. Slugs update with name. Users can re-navigate from the projects list.

### Risk 3: Large Waypoint/Brain Reboot Content

**Risk:** Markdown content could be very long, making the page unwieldy.

**Mitigation:** Consider max-height with scroll or truncation with "show more" for very long content sections. Implementation detail, but the requirement is that content is displayed.

---

## 9. Acceptance Criteria

### Slug & Routing

- [ ] Project model has a `slug` field (unique, non-nullable, indexed)
- [ ] Creating a project auto-generates a slug from the name
- [ ] Editing a project name updates the slug
- [ ] Navigate to `/projects/<slug>` — shows project detail
- [ ] Navigate to non-existent slug — returns 404

### Project Show Page

- [ ] Page displays project metadata: name, path, GitHub repo (linked), branch, description, created date
- [ ] Page displays inference status (active/paused with timestamp and reason if paused)
- [ ] Edit action opens form, saves changes, updates display
- [ ] Delete action shows confirmation, deletes, redirects to `/projects`
- [ ] Pause/Resume toggles inference status immediately
- [ ] Regenerate Description updates description field
- [ ] Refetch GitHub Info updates repo and branch fields

### Content Sections

- [ ] Waypoint section shows rendered markdown content
- [ ] Waypoint section shows empty state when no waypoint exists
- [ ] Waypoint section has edit link/button
- [ ] Brain reboot shows last generated content with date and time-ago
- [ ] Brain reboot shows empty state with Generate button when none exists
- [ ] Regenerate brain reboot works and updates display
- [ ] Export brain reboot works
- [ ] Progress summary shows rendered content with regenerate option

### Navigation Changes

- [ ] Projects list: project names are clickable links to `/projects/<slug>`
- [ ] Projects list: no Edit, Delete, or Pause/Resume action buttons
- [ ] Projects list: Add Project button still works
- [ ] Brain reboot modal: includes link to project show page
