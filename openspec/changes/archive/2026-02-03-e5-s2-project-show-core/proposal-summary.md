# Proposal Summary: e5-s2-project-show-core

## Architecture Decisions
- Slug-based routing using `GET /projects/<slug>` — slug is a new field on the Project model
- Slug generation uses Python `re` module (no external library): lowercase, hyphens, collision handling with numeric suffix
- Show page fetches additional data (waypoint, brain reboot, progress summary) via existing API endpoints using JavaScript after initial page load — no new backend API endpoints needed
- Projects list simplified to navigation hub: project names become links, action buttons removed
- Follow existing page patterns (base template, header navigation, vanilla JS)

## Implementation Approach
- Add `slug` column to Project model with unique constraint, auto-generation on create, regeneration on name update
- Create Alembic migration with backfill of existing projects
- New `GET /projects/<slug>` route resolves slug to project, renders `project_show.html`
- `project_show.js` loads data from existing endpoints and handles all control actions client-side
- Reuse existing project form modal for edit action on show page
- Time-ago display for brain reboot timestamp calculated in JavaScript

## Files to Modify
- **Model:** `src/claude_headspace/models/project.py` — add `slug` field, slug generation utility
- **Routes:** `src/claude_headspace/routes/projects.py` — add show page route, slug auto-generation on create/update
- **Templates:**
  - `templates/projects.html` — make names clickable links, remove action buttons
  - `templates/partials/_brain_reboot_modal.html` — add link to project show page
  - `templates/partials/_project_form_modal.html` — may need slug update handling
- **JavaScript:** `static/js/projects.js` — update rendering, remove inline action handlers
- **New files:**
  - `templates/project_show.html` — show page template
  - `static/js/project_show.js` — show page JavaScript
  - `migrations/versions/xxxx_add_project_slug.py` — migration
  - `tests/routes/test_project_show.py` — route tests

## Acceptance Criteria
- Navigate to `/projects/claude-headspace` — see full metadata, waypoint, brain reboot, progress summary
- Click project name on list — navigates to `/projects/<slug>`
- Projects list has no Edit/Delete/Pause action buttons
- Edit metadata from show page — changes reflect immediately, URL updates on name change
- Delete from show page — confirmation, redirect to `/projects`
- Pause/Resume inference from show page — status updates immediately
- Regenerate Description / Refetch GitHub Info — fields update without page reload
- Waypoint section: rendered markdown, empty state, edit link
- Brain reboot section: rendered markdown, date + time-ago, Regenerate + Export buttons
- Progress summary section: rendered markdown, Regenerate button
- Brain reboot modal includes link to project show page
- Non-existent slug returns 404

## Constraints and Gotchas
- Slug must handle Unicode and special characters gracefully
- Slug collision handling: append numeric suffix (e.g., `my-project-2`)
- Old slugs are NOT preserved when project name changes (bookmarked URLs may break — accepted trade-off)
- Show page template must pass project ID to JavaScript for API calls (slug is for routing only, API endpoints use integer IDs)
- Brain reboot modal needs to know the project slug to generate the link — may need to pass slug via JavaScript context
- Large waypoint/brain reboot content: consider max-height with scroll for long content sections
- Tailwind CSS: use existing utility classes and `prose` class for markdown rendering
- This is Part 1 of 2: do NOT implement accordion object tree, activity metrics, SSE updates, or archive history (those are E5-S3)

## Git Change History

### Related Files
- Models: `src/claude_headspace/models/project.py`
- Routes: `src/claude_headspace/routes/projects.py`
- Templates: `templates/projects.html`, `templates/partials/_brain_reboot_modal.html`, `templates/partials/_project_form_modal.html`
- JavaScript: `static/js/projects.js`
- Tests: `tests/routes/test_projects.py`

### OpenSpec History
- `e4-s2b-project-controls-ui` (archived 2026-02-02) — project controls backend + UI, direct predecessor
- `e2-s1-config-ui` (archived 2026-01-29) — config UI, similar page pattern
- `e1-s8-dashboard-ui` (archived 2026-01-29) — dashboard UI patterns

### Implementation Patterns
- Flask blueprint for route organization
- Page routes render templates; data fetched via API endpoints in JavaScript
- Modals for edit/create forms (centered, backdrop, form validation)
- SSE for real-time updates (existing `headerSSEClient`)
- Tailwind CSS utility classes with `prose` for markdown
- IIFE pattern for JavaScript modules
- Error handling with flash/toast messages

## Q&A History
- No clarifications needed — PRD is clear and complete

## Dependencies
- No new packages/gems required
- No new external services
- Database migration required (add slug column with backfill)
- Existing API endpoints cover all data needs

## Testing Strategy
- Route tests for `GET /projects/<slug>` (valid slug, invalid slug, 404)
- Slug generation tests (basic, collision, special characters, Unicode)
- Slug regeneration on name update
- Targeted test run: `pytest tests/routes/test_project_show.py tests/routes/test_projects.py`

## OpenSpec References
- proposal.md: openspec/changes/e5-s2-project-show-core/proposal.md
- tasks.md: openspec/changes/e5-s2-project-show-core/tasks.md
- spec.md: openspec/changes/e5-s2-project-show-core/specs/project-show-core/spec.md
