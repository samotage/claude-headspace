# Proposal Summary: Persona Detail Page & Skill Editor

## Architecture Decisions

1. **Inline editor, not modal** -- The skill editor is built directly into the detail page (not a modal like the waypoint editor). This matches the project_show.html pattern where waypoint editing is inline. The waypoint modal (`_waypoint_editor.html`) is a cross-project tool; the skill editor is page-specific.

2. **Follow waypoint editor UX pattern** -- Edit/Preview tabs, monospace textarea, prose-styled preview, Save/Cancel buttons, unsaved-changes indicator. Reuse the same CSS classes and interaction patterns.

3. **Client-side markdown rendering** -- Use the existing `marked.js` + DOMPurify pipeline (already loaded in base.html) for preview and view mode rendering. No server-side markdown rendering needed.

4. **Extend existing persona_assets service** -- Add `write_skill_file()` and `get_experience_mtime()` to the stateless service. No new service classes needed.

5. **Extend existing personas blueprint** -- Add all new endpoints to `routes/personas.py` rather than creating a separate blueprint. Keeps persona routes consolidated.

6. **No model changes** -- All required data is already available: Persona model has slug, name, role, status, description, created_at; Agent model has persona_id FK, session_uuid, last_seen_at; Agent has project relationship for project name.

## Implementation Approach

### Backend (Service Layer)

Add two functions to `persona_assets.py`:
- `write_skill_file(slug, content, project_root=None)` -- writes content to `{persona_dir}/skill.md`, creates directory if needed, returns the path
- `get_experience_mtime(slug, project_root=None)` -- returns ISO 8601 last-modified timestamp of experience.md or None

### Backend (Routes)

Add to `routes/personas.py`:
1. **Page route**: `GET /personas/<slug>` -- queries Persona by slug (with role eager-loaded), returns 404 if not found, renders `persona_detail.html` with persona object
2. **Skill read**: `GET /api/personas/<slug>/skill` -- calls `read_skill_file()`, returns `{content, exists}`
3. **Skill write**: `PUT /api/personas/<slug>/skill` -- validates persona exists in DB, validates request body has content field, calls `write_skill_file()`, returns `{saved: true}`
4. **Experience read**: `GET /api/personas/<slug>/experience` -- calls `read_experience_file()` and `get_experience_mtime()`, returns `{content, exists, last_modified}`
5. **Asset status**: `GET /api/personas/<slug>/assets` -- calls `check_assets()`, returns dataclass fields as JSON
6. **Linked agents**: `GET /api/personas/<slug>/agents` -- queries persona with eager-loaded agents + agent.project, returns array of agent detail objects

### Frontend (Template)

Create `templates/persona_detail.html` extending `base.html`:
- Back link: `< Back to Personas` linking to `/personas`
- Header section: persona name (h1), role badge, status badge (active=green, archived=amber)
- Metadata bar: slug (monospace), description, created date
- Skill section: `#skill-view` (rendered markdown), `#skill-editor` (hidden by default, textarea + tabs + buttons)
- Experience section: `#experience-content` (rendered markdown), `#experience-mtime` (timestamp)
- Linked agents section: `#agents-list` (table/list)
- Include `_toast.html` partial

### Frontend (JavaScript)

Create `static/js/persona_detail.js`:
- `PersonaDetail` object with init, loadSkill, editSkill, previewSkill, saveSkill, cancelEdit, loadExperience, loadLinkedAgents
- State tracking: `{ originalContent, isDirty, mode: 'view'|'edit'|'preview' }`
- Markdown rendering via `marked.parse()` + `DOMPurify.sanitize()`
- Toast notifications via existing `window.Toast` utility

### Frontend (List Page Update)

Modify `static/js/personas.js` `_renderTable()`:
- Change name column from plain text to `<a href="/personas/{slug}" class="text-cyan hover:underline">{name}</a>`

## Files to Modify

### Service Layer
- `src/claude_headspace/services/persona_assets.py` -- add `write_skill_file()`, `get_experience_mtime()`

### Routes
- `src/claude_headspace/routes/personas.py` -- add detail page route + 5 API endpoints

### Templates
- **NEW** `templates/persona_detail.html` -- persona detail page

### Static/JavaScript
- **NEW** `static/js/persona_detail.js` -- detail page client-side logic
- `static/js/personas.js` -- name column becomes link

### Tests
- `tests/services/test_persona_assets.py` -- add tests for write_skill_file, get_experience_mtime
- `tests/routes/test_personas.py` -- add tests for detail page route + 5 API endpoints

## Acceptance Criteria

1. Persona names in list are clickable links to `/personas/<slug>`
2. Detail page displays all persona metadata
3. Skill editor supports view/edit/preview modes with save/cancel
4. Unsaved changes indicator works
5. Empty states shown for missing skill, experience, and agents
6. Experience log is read-only with last-modified timestamp
7. Linked agents show name/ID, project, state, last seen
8. Toast notifications for save success/failure
9. Back navigation works
10. All targeted tests pass

## Constraints and Gotchas

1. **persona_assets is stateless** -- All functions take `slug` and optional `project_root`. No database dependency. The route layer handles DB validation (persona exists) before calling asset functions.
2. **Persona slug resolution** -- The Persona model uses `_set_persona_slug` after_insert event to generate `{role}-{name}-{id}` slugs. Detail page URL uses this slug.
3. **Agent.persona_id FK** -- Agent model already has `persona_id` with `ondelete="CASCADE"`. The relationship `persona.agents` is already defined and used in the list API.
4. **marked.js availability** -- Check that `marked` and `DOMPurify` are loaded in `base.html`. If they are only loaded conditionally, ensure they are available on the detail page.
5. **PERSONA_DATA_ROOT config** -- The `_resolve_personas_dir()` function checks `current_app.config["PERSONA_DATA_ROOT"]` in Flask context. Tests should use `project_root` parameter to avoid filesystem side effects.
6. **File encoding** -- All file reads/writes use `encoding="utf-8"` consistently.

## Git Change History

### Related OpenSpec Changes (archived)
- `e8-s1-role-persona-models` (2026-02-20) -- created Persona and Role database models
- `e8-s5-persona-filesystem-assets` (2026-02-21) -- created persona_assets.py with read_skill_file, read_experience_file, check_assets
- `e8-s6-persona-registration` (2026-02-21) -- registration service that seeds skill.md and experience.md
- `e8-s7-persona-aware-agent-creation` (2026-02-21) -- Agent.persona_id FK and relationship
- `e8-s8-session-correlator-persona` (2026-02-21) -- persona resolution during session correlation
- `e8-s10-card-persona-identity` (2026-02-21) -- persona display on dashboard cards
- `e8-s11-agent-info-persona-display` (2026-02-21) -- persona in agent info panel
- `e8-s15-persona-list-crud` (2026-02-23) -- persona list page, CRUD operations, nav tab

### Recent Commits
- `6d5b1590` (2026-02-23) -- feat(e8-s15-persona-list-crud): persona list CRUD implementation
- `284dbdab` (2026-02-23) -- docs: add persona UI PRDs (E8-S15, S16, S17)

### Patterns Detected
- Route structure: page route + API endpoints in same blueprint (see personas.py, projects.py)
- Template pattern: extends base.html, includes _header.html, uses page-content container
- JavaScript pattern: IIFE module with global namespace object (PersonasPage, ProjectShow)
- Testing pattern: route tests use `client` fixture, service tests use `tmp_path` or `project_root` parameter

## Q&A History

No clarifications needed -- PRD is unambiguous with clear requirements, well-established patterns to follow, and existing backend infrastructure (persona_assets.py, Persona model, Agent.persona relationship) already in place.

## Dependencies

- **No new Python packages** -- all needed libraries are already installed
- **No new npm packages** -- marked.js and DOMPurify already available
- **No database migrations** -- all models and relationships already exist
- **No config changes** -- PERSONA_DATA_ROOT already configured

## Testing Strategy

### Unit Tests (tests/services/test_persona_assets.py)
- `test_write_skill_file_creates_new` -- writes to non-existent file, verifies content
- `test_write_skill_file_overwrites_existing` -- overwrites existing file
- `test_write_skill_file_creates_directory` -- creates persona directory if missing
- `test_get_experience_mtime_exists` -- returns ISO timestamp when file exists
- `test_get_experience_mtime_missing` -- returns None when file missing

### Route Tests (tests/routes/test_personas.py)
- `test_persona_detail_page_200` -- valid slug returns 200
- `test_persona_detail_page_404` -- invalid slug returns 404
- `test_skill_read_success` -- returns content and exists=true
- `test_skill_read_not_found` -- returns exists=false for missing file
- `test_skill_read_persona_not_found` -- returns 404 for missing persona
- `test_skill_write_success` -- writes content, returns saved=true
- `test_skill_write_no_body` -- returns 400
- `test_skill_write_persona_not_found` -- returns 404
- `test_experience_read_success` -- returns content, exists, last_modified
- `test_experience_read_empty` -- returns exists=false for missing file
- `test_asset_status` -- reports correct file existence
- `test_linked_agents_with_agents` -- returns agent details
- `test_linked_agents_empty` -- returns empty array

## OpenSpec References

- **Proposal**: `openspec/changes/e8-s16-persona-detail-skill-editor/proposal.md`
- **Tasks**: `openspec/changes/e8-s16-persona-detail-skill-editor/tasks.md`
- **Spec**: `openspec/changes/e8-s16-persona-detail-skill-editor/specs/persona-detail-skill-editor/spec.md`
