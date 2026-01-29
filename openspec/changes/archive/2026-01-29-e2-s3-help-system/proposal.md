# Proposal: e2-s3-help-system

## Summary

Add a searchable help/documentation system accessible via `?` keyboard shortcut, providing in-app documentation with full-text search and markdown rendering.

## Motivation

Claude Headspace is growing with configuration UI, waypoint editing, and future intelligence features. Users need a centralized place to learn how features work without reading source code or external documentation.

## Impact

### Files to Create
- `src/claude_headspace/routes/help.py` - Help content API endpoints
- `templates/partials/_help_modal.html` - Help modal component
- `static/js/help.js` - Help modal and search logic
- `docs/help/index.md` - Table of contents and overview
- `docs/help/getting-started.md` - Quick start guide
- `docs/help/dashboard.md` - Dashboard overview
- `docs/help/objective.md` - Objective setting guide
- `docs/help/configuration.md` - config.yaml options
- `docs/help/waypoints.md` - Waypoint editing guide
- `docs/help/troubleshooting.md` - Common issues
- `tests/routes/test_help.py` - Help API tests

### Files to Modify
- `src/claude_headspace/app.py` - Register help blueprint
- `templates/base.html` - Include help modal and keyboard listener
- `templates/partials/_header.html` - Add help button

### Database Changes
None - reads markdown files from docs/help/ directory.

## Definition of Done

- [ ] Press `?` key opens help modal (except in text inputs)
- [ ] Help button in header opens help modal
- [ ] Modal displays with search, TOC, and content area
- [ ] Search matches topic titles and content
- [ ] TOC navigation loads topic content
- [ ] Markdown renders correctly (headings, code, links, lists)
- [ ] Modal closes on Escape, backdrop click, or X button
- [ ] GET /api/help/topics returns topic list
- [ ] GET /api/help/topics/<slug> returns topic content
- [ ] 7 documentation topics created
- [ ] Modal opens within 100ms
- [ ] Search results within 200ms
- [ ] Focus trapping in modal
- [ ] ARIA labels and roles
- [ ] All tests passing

## Risks

- **Search performance:** Mitigated by client-side search with small doc corpus
- **Markdown rendering edge cases:** Mitigated by using simple subset of markdown
- **Accessibility compliance:** Mitigated by following existing modal patterns

## Alternatives Considered

1. **External docs site:** Rejected - context switching disrupts workflow
2. **AI-powered Q&A:** Rejected - out of scope, added complexity
3. **Context-sensitive tooltips:** Rejected - high maintenance, out of scope
