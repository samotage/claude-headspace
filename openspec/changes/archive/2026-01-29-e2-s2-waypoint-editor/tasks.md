# Tasks: e2-s2-waypoint-editor

## Phase 1: Setup

- [x] Review Project model and path storage
- [x] Review E2-S1 Config UI patterns (form layout, save feedback)
- [x] Review existing dashboard template structure
- [x] Plan waypoint service architecture

## Phase 2: Implementation

### Waypoint Service (FR4-FR6, FR11-FR14, NFR3)
- [x] Create src/claude_headspace/services/waypoint_editor.py
- [x] Implement load_waypoint(project_path) function
- [x] Return waypoint content or default template if missing
- [x] Include file modification time for conflict detection
- [x] Implement save_waypoint(project_path, content, expected_mtime) function
- [x] Archive existing waypoint before save
- [x] Handle date counter for multiple daily archives (e.g., `_2.md`)
- [x] Create directory structure if missing (`docs/brain_reboot/archive/`)
- [x] Atomic write using temp file then rename
- [x] Implement conflict detection via mtime comparison

### API Endpoints (FR4, FR11, FR15-19)
- [x] Create src/claude_headspace/routes/waypoint.py blueprint
- [x] Implement GET /api/projects/<id>/waypoint endpoint
- [x] Return content, exists flag, mtime, path
- [x] Return template content with template=true if missing
- [x] Implement POST /api/projects/<id>/waypoint endpoint
- [x] Accept content and expected_mtime
- [x] Return 409 conflict if mtime mismatch
- [x] Return 403 with path on permission denied
- [x] Register waypoint_bp in app.py

### Waypoint Editor UI (FR1-FR3, FR7-FR10, FR20-21)
- [x] Create templates/partials/_waypoint_editor.html modal
- [x] Project selector dropdown from database
- [x] Markdown textarea for editing
- [x] Preview mode with rendered markdown
- [x] Toggle between edit and preview
- [x] Unsaved changes indicator
- [x] Save and Cancel buttons
- [x] File path display in footer
- [x] Last modified timestamp display

### Conflict Resolution (FR15-FR16)
- [x] Conflict detection dialog
- [x] Reload option (discard changes, load current)
- [x] Overwrite option (save anyway)
- [x] Show external modification timestamp

### Dashboard Integration (FR21)
- [x] Modify templates/partials/_project_group.html
- [x] Wire [Edit] button to open waypoint editor
- [x] Pass project ID to editor
- [x] Include editor modal in dashboard.html

### Error Handling & Feedback (FR17-FR20, NFR5)
- [x] Permission error with specific path
- [x] Project path inaccessible error
- [x] Actionable error messages pattern
- [x] Success toast on save
- [x] Error toast on failure

## Phase 3: Testing

- [x] Test GET waypoint returns content
- [x] Test GET waypoint returns template for missing file
- [x] Test POST waypoint saves correctly
- [x] Test POST waypoint archives before save
- [x] Test archive counter for multiple daily saves
- [x] Test directory creation when missing
- [x] Test atomic write mechanism
- [x] Test conflict detection (mtime mismatch)
- [x] Test permission denied handling
- [x] Test project path validation
- [x] Test markdown preview rendering

## Phase 4: Final Verification

- [x] All tests passing
- [ ] Waypoint loads within 500ms
- [ ] Save completes within 2 seconds
- [ ] No console errors
- [ ] Manual test: edit waypoint, save, verify archived
