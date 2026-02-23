## Why

Sprint 15 delivered persona list and CRUD operations, but there is no way to view a persona's full profile, edit its skill file, review its accumulated experience, or see which agents are using it. The skill file (`skill.md`) is the primary mechanism for shaping agent behaviour -- it gets injected into sessions via the tmux bridge -- yet it can only be edited by hand in the filesystem. This sprint adds the persona detail page with an inline skill editor, experience log viewer, and linked agents display, completing end-to-end persona management from the browser.

## What Changes

- New page route: `/personas/<slug>` renders `persona_detail.html` template with full persona profile
- New template: `templates/persona_detail.html` with metadata header, skill editor section, experience log section, and linked agents section
- Skill editor: follows waypoint editor pattern -- Edit/Preview tabs, monospace textarea, prose-styled preview, Save/Cancel buttons, unsaved-changes indicator
- Experience log viewer: read-only rendered markdown with last-modified timestamp
- Linked agents section: table of agents currently using this persona (name/ID, project, state, last seen)
- New JavaScript module: `static/js/persona_detail.js` for skill editor logic, markdown preview, experience loading, linked agents loading
- Extended persona_assets service: add `write_skill_file()` function and `get_experience_mtime()` function
- New API endpoints in `routes/personas.py`:
  - `GET /api/personas/<slug>/skill` -- read raw skill.md content
  - `PUT /api/personas/<slug>/skill` -- write skill.md content
  - `GET /api/personas/<slug>/experience` -- read experience.md content with last_modified
  - `GET /api/personas/<slug>/assets` -- asset existence check (skill.md, experience.md)
  - `GET /api/personas/<slug>/agents` -- linked agents with status detail
- Modified persona list table: persona names become clickable links to detail page
- No model changes required
- No migration required

## Impact

- Affected specs: persona-list-crud (modified: name column becomes clickable), persona-filesystem-assets (extended: write_skill_file, get_experience_mtime)
- Affected code:
  - MODIFIED: `src/claude_headspace/routes/personas.py` -- add detail page route + 5 asset/agent API endpoints
  - MODIFIED: `src/claude_headspace/services/persona_assets.py` -- add write_skill_file(), get_experience_mtime()
  - MODIFIED: `static/js/personas.js` -- persona name column becomes link to detail page
  - NEW: `templates/persona_detail.html` -- persona detail page template
  - NEW: `static/js/persona_detail.js` -- detail page JavaScript (skill editor, experience viewer, linked agents)
- Affected tests:
  - MODIFIED: `tests/routes/test_personas.py` -- add tests for new endpoints and page route
  - MODIFIED: `tests/services/test_persona_assets.py` -- add tests for write_skill_file, get_experience_mtime
  - NEW: tests for detail page rendering and API endpoints

## Definition of Done

- [ ] Persona names in list are clickable links to `/personas/<slug>`
- [ ] Detail page displays persona metadata: name, role, slug, status, created date, description
- [ ] Skill section shows rendered markdown by default (view mode)
- [ ] Edit button switches to edit mode with monospace textarea
- [ ] Preview tab renders current textarea content as markdown without saving
- [ ] Save button persists content to skill.md via API
- [ ] Cancel button discards edits and returns to view mode
- [ ] Unsaved changes indicator shown when content is modified
- [ ] Empty state shown when skill.md does not exist, with option to create
- [ ] Experience section shows rendered markdown (read-only) with last-modified timestamp
- [ ] Experience empty state shown when experience.md does not exist or is empty
- [ ] Linked agents section lists agents with name/ID, project, state, last seen
- [ ] Linked agents empty state when no agents are linked
- [ ] Toast notifications for save success/failure
- [ ] Back link navigates to persona list
- [ ] All tests passing
