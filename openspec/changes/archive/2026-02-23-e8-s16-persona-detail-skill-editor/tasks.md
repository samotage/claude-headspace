## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend

- [x] 2.1 Add `write_skill_file(slug, content, project_root)` to `persona_assets.py` -- writes content to `data/personas/{slug}/skill.md`, creates directory if needed
- [x] 2.2 Add `get_experience_mtime(slug, project_root)` to `persona_assets.py` -- returns last-modified ISO timestamp of experience.md (or None)
- [x] 2.3 Add detail page route: `GET /personas/<slug>` renders `persona_detail.html` with persona data from DB
- [x] 2.4 Add skill read endpoint: `GET /api/personas/<slug>/skill` returns `{content, exists}`
- [x] 2.5 Add skill write endpoint: `PUT /api/personas/<slug>/skill` accepts `{content}`, writes to filesystem, returns `{saved: true}`
- [x] 2.6 Add experience read endpoint: `GET /api/personas/<slug>/experience` returns `{content, exists, last_modified}`
- [x] 2.7 Add asset status endpoint: `GET /api/personas/<slug>/assets` returns `{skill_exists, experience_exists, directory_exists}`
- [x] 2.8 Add linked agents endpoint: `GET /api/personas/<slug>/agents` returns agent list with project name, state, last_seen

### Frontend - Template

- [x] 2.9 Create `templates/persona_detail.html` extending `base.html`:
  - Back link to persona list
  - Header with name, role badge, status badge
  - Metadata bar: slug, description, created date
  - Skill section with view/edit/preview modes
  - Experience section (read-only)
  - Linked agents section

### Frontend - JavaScript

- [x] 2.10 Create `static/js/persona_detail.js` with:
  - `PersonaDetail.init()` -- load skill, experience, and agents on page load
  - `PersonaDetail.loadSkill()` -- fetch skill content, render markdown in view mode
  - `PersonaDetail.editSkill()` -- switch to edit mode, populate textarea
  - `PersonaDetail.previewSkill()` -- render textarea content as markdown preview
  - `PersonaDetail.saveSkill()` -- PUT skill content, switch back to view mode, show toast
  - `PersonaDetail.cancelEdit()` -- discard changes, return to view mode
  - `PersonaDetail.loadExperience()` -- fetch experience content, render markdown
  - `PersonaDetail.loadLinkedAgents()` -- fetch agents, render table
  - Unsaved-changes tracking with visual indicator

### Frontend - List Page Update

- [x] 2.11 Modify `static/js/personas.js` `_renderTable()` -- persona names become `<a>` links to `/personas/{slug}`

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for `write_skill_file()` in `tests/services/test_persona_assets.py` (write new file, overwrite existing, creates directory)
- [x] 3.2 Unit tests for `get_experience_mtime()` in `tests/services/test_persona_assets.py` (file exists, file missing)
- [x] 3.3 Route tests for detail page route (200 for valid slug, 404 for invalid)
- [x] 3.4 Route tests for skill read endpoint (content returned, 404 for missing persona)
- [x] 3.5 Route tests for skill write endpoint (saves content, 404 for missing persona, 400 for empty body)
- [x] 3.6 Route tests for experience read endpoint (content returned, empty state for missing file)
- [x] 3.7 Route tests for asset status endpoint (reports correct existence)
- [x] 3.8 Route tests for linked agents endpoint (returns agents with detail, empty list)

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
