# Proposal: e2-s2-waypoint-editor

## Summary

Add a Waypoint Editor to the dashboard enabling users to view and edit project waypoints directly from the web UI, with markdown preview, automatic archiving, and conflict detection.

## Motivation

Waypoints (`docs/brain_reboot/waypoint.md`) are critical brain_reboot artifacts that define project priorities. Currently, editing requires navigating to each project directory and manually editing files. This friction leads to stale waypoints.

## Impact

### Files to Create
- `src/claude_headspace/routes/waypoint.py` - Waypoint API endpoints (GET/POST)
- `src/claude_headspace/services/waypoint_editor.py` - Waypoint loading, saving, archiving service
- `templates/partials/_waypoint_editor.html` - Waypoint editor modal component
- `tests/routes/test_waypoint.py` - Waypoint API endpoint tests
- `tests/services/test_waypoint_editor.py` - Waypoint editor service tests

### Files to Modify
- `src/claude_headspace/app.py` - Register waypoint blueprint
- `templates/partials/_project_group.html` - Wire [Edit] button to open editor
- `templates/dashboard.html` - Include waypoint editor modal

### Database Changes
None - reads/writes to project filesystem paths.

## Definition of Done

- [ ] Project selector dropdown lists all monitored projects
- [ ] Selecting a project loads its waypoint content
- [ ] Missing waypoints display default template
- [ ] Edit mode shows markdown textarea
- [ ] Preview mode renders markdown content
- [ ] Toggle between edit and preview modes
- [ ] Unsaved changes indicator displayed
- [ ] Save archives existing waypoint with date stamp
- [ ] Archive counter for multiple saves per day (e.g., `_2.md`)
- [ ] Directory structure created if missing
- [ ] Conflict detection on external file modification
- [ ] Conflict resolution dialog (Reload/Overwrite)
- [ ] Permission error with actionable message
- [ ] Success toast on save
- [ ] [Edit] button opens editor for that project
- [ ] GET /api/projects/<id>/waypoint returns content
- [ ] POST /api/projects/<id>/waypoint saves with archive
- [ ] Atomic archive write (temp file then rename)
- [ ] All tests passing

## Risks

- **File permission errors:** Mitigated via read-only indicator and clear error messages
- **Project path inaccessible:** Validate path exists, graceful errors
- **Large files:** Warn if >100KB

## Alternatives Considered

1. **Rich WYSIWYG editor:** Rejected - complex, buggy, users know markdown
2. **No archive:** Rejected - data loss risk
3. **Lock-based conflict detection:** Rejected - mtime comparison simpler
