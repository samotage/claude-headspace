# Proposal Summary: e2-s3-help-system

## Architecture Decisions
- Client-side full-text search (lunr.js-style simple search, small doc corpus)
- Plain markdown files in docs/help/ for easy maintenance
- Modal overlay pattern matching existing waypoint editor
- Flask blueprint for help API endpoints
- No build step required - docs load at runtime

## Implementation Approach
- Create help API blueprint for serving markdown content
- Create modal component following _waypoint_editor.html patterns
- Add keyboard listener in help.js for `?` shortcut
- Build simple client-side search index from topic content
- Render markdown to HTML client-side

## Files to Modify

**Routes:**
- `src/claude_headspace/routes/help.py` - Help API endpoints (new)
- `src/claude_headspace/app.py` - Register help_bp

**Static:**
- `static/js/help.js` - Modal and search logic (new)

**Templates:**
- `templates/partials/_help_modal.html` - Help modal (new)
- `templates/base.html` - Include modal and JS
- `templates/partials/_header.html` - Add help button

**Documentation:**
- `docs/help/index.md` (new)
- `docs/help/getting-started.md` (new)
- `docs/help/dashboard.md` (new)
- `docs/help/objective.md` (new)
- `docs/help/configuration.md` (new)
- `docs/help/waypoints.md` (new)
- `docs/help/troubleshooting.md` (new)

**Tests:**
- `tests/routes/test_help.py` (new)

## Acceptance Criteria
- Press `?` key opens help modal (except in text inputs)
- Help button in header opens modal
- Modal has search, TOC sidebar, and content area
- Search matches topic titles and content within 200ms
- TOC navigation loads topic content
- Markdown renders correctly (headings, code, links, lists)
- Modal closes on Escape, backdrop click, or X button
- GET /api/help/topics returns topic list
- GET /api/help/topics/<slug> returns topic content
- Modal opens within 100ms
- Focus trapping in modal
- ARIA labels and roles

## Constraints and Gotchas
- **Keyboard shortcut conflict:** Must skip when in text inputs
- **Focus management:** Must trap focus and restore on close
- **Search index:** Built client-side for simplicity, load time ~500ms
- **Markdown subset:** Keep docs simple, avoid edge cases
- **Cross-browser:** Must work in Safari, Chrome, Firefox

## Git Change History

### Related Files
**Routes:**
- `src/claude_headspace/routes/waypoint.py` - Similar blueprint pattern

**Templates:**
- `templates/partials/_waypoint_editor.html` - Modal pattern to follow
- `templates/base.html` - Where to include modal
- `templates/partials/_header.html` - Where to add button

**Static:**
- `static/js/` - Existing JS patterns

### OpenSpec History
- e2-s2-waypoint-editor (2026-01-29): Modal editor pattern, keyboard shortcuts
- e2-s1-config-ui (2026-01-29): Settings modal pattern

### Implementation Patterns
1. Create API blueprint for content
2. Create modal template component
3. Create JS file for interactions
4. Add button to header
5. Include modal in base template
6. Add comprehensive tests

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required** - uses existing Flask, pathlib
- **E1 complete** - Dashboard with header
- **E2-S2 complete** - Modal pattern established

## Testing Strategy
- Test GET /api/help/topics returns list
- Test GET /api/help/topics/<slug> returns content
- Test GET /api/help/topics/<invalid> returns 404
- Test markdown rendering
- Test search functionality
- Test modal keyboard shortcuts
- Test focus trap

## OpenSpec References
- proposal.md: openspec/changes/e2-s3-help-system/proposal.md
- tasks.md: openspec/changes/e2-s3-help-system/tasks.md
- spec.md: openspec/changes/e2-s3-help-system/specs/help/spec.md
