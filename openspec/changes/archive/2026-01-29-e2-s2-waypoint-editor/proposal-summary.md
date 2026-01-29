# Proposal Summary: e2-s2-waypoint-editor

## Architecture Decisions
- Plain markdown textarea with preview (not WYSIWYG) for simplicity
- Archive on every save for predictability and data safety
- mtime-based conflict detection (simpler than file locking)
- Modal editor (quick edits from dashboard)
- Atomic writes using temp file then rename

## Implementation Approach
- Create waypoint service for file operations (load, save, archive)
- Create API blueprint with GET/POST endpoints
- Create modal component for editor UI
- Wire existing [Edit] button to open modal
- Follow E2-S1 Config UI patterns for form layout and feedback

## Files to Modify

**Routes:**
- `src/claude_headspace/routes/waypoint.py` - Waypoint API endpoints (new)
- `src/claude_headspace/app.py` - Register waypoint_bp

**Services:**
- `src/claude_headspace/services/waypoint_editor.py` - Load, save, archive logic (new)

**Templates:**
- `templates/partials/_waypoint_editor.html` - Editor modal (new)
- `templates/partials/_project_group.html` - Wire [Edit] button
- `templates/dashboard.html` - Include editor modal

**Tests:**
- `tests/routes/test_waypoint.py` (new)
- `tests/services/test_waypoint_editor.py` (new)

## Acceptance Criteria
- Project selector dropdown with all monitored projects
- Waypoint loads from `<project.path>/docs/brain_reboot/waypoint.md`
- Default template for missing waypoints
- Edit mode (textarea) and preview mode (rendered)
- Toggle between modes
- Unsaved changes indicator
- Archive existing waypoint before save
- Date counter for multiple daily archives
- Directory structure created if missing
- Conflict detection via mtime comparison
- Reload/Overwrite conflict resolution
- Permission error with specific path
- Success/error toasts
- GET /api/projects/<id>/waypoint returns content
- POST /api/projects/<id>/waypoint saves with archive
- [Edit] button opens editor for that project

## Constraints and Gotchas
- **Project paths external:** Waypoints live in monitored project repos, not this app
- **File permissions:** Projects may have different owners/permissions
- **mtime precision:** Some filesystems have limited mtime precision
- **Archive counter:** Must handle race condition if multiple saves within same second
- **Large files:** Should warn if waypoint >100KB
- **Path validation:** Project path may become inaccessible (moved, network drive)

## Git Change History

### Related Files
**Routes:**
- `src/claude_headspace/routes/` - Existing route patterns

**Services:**
- `src/claude_headspace/services/config_editor.py` - Similar file operation patterns

**Templates:**
- `templates/partials/_project_group.html` - Has existing [Edit] button
- `templates/dashboard.html` - Dashboard structure

**Tests:**
- `tests/routes/test_config.py` - Route test patterns
- `tests/services/test_config_editor.py` - Service test patterns

### OpenSpec History
- e2-s1-config-ui (2026-01-29): Config editor with atomic save, validation, toast feedback

### Implementation Patterns
1. Create service module for file operations
2. Create Flask blueprint for API routes
3. Register blueprint in app.py
4. Create modal template component
5. Wire button to modal
6. Add comprehensive tests

## Q&A History
- No clarifications needed - PRD is comprehensive

## Dependencies
- **No new pip packages required** - uses existing Flask, pathlib
- **E1 complete** - Project model provides paths
- **E2-S1 complete** - Config UI provides editing patterns

## Testing Strategy
- Test GET waypoint returns content (exists)
- Test GET waypoint returns template (missing)
- Test POST waypoint saves correctly
- Test POST waypoint archives before save
- Test archive counter for multiple daily saves
- Test directory creation when missing
- Test atomic write mechanism
- Test conflict detection (mtime mismatch)
- Test permission denied handling
- Test project path validation
- Test markdown preview rendering

## OpenSpec References
- proposal.md: openspec/changes/e2-s2-waypoint-editor/proposal.md
- tasks.md: openspec/changes/e2-s2-waypoint-editor/tasks.md
- spec.md: openspec/changes/e2-s2-waypoint-editor/specs/waypoint/spec.md
