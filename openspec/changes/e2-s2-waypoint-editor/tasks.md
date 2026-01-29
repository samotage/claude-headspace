# Tasks: e2-s2-waypoint-editor

## Phase 1: Setup

- [ ] Review Project model and path storage
- [ ] Review E2-S1 Config UI patterns (form layout, save feedback)
- [ ] Review existing dashboard template structure
- [ ] Plan waypoint service architecture

## Phase 2: Implementation

### Waypoint Service (FR4-FR6, FR11-FR14, NFR3)
- [ ] Create src/claude_headspace/services/waypoint_editor.py
- [ ] Implement load_waypoint(project_path) function
- [ ] Return waypoint content or default template if missing
- [ ] Include file modification time for conflict detection
- [ ] Implement save_waypoint(project_path, content, expected_mtime) function
- [ ] Archive existing waypoint before save
- [ ] Handle date counter for multiple daily archives (e.g., `_2.md`)
- [ ] Create directory structure if missing (`docs/brain_reboot/archive/`)
- [ ] Atomic write using temp file then rename
- [ ] Implement conflict detection via mtime comparison

### API Endpoints (FR4, FR11, FR15-19)
- [ ] Create src/claude_headspace/routes/waypoint.py blueprint
- [ ] Implement GET /api/projects/<id>/waypoint endpoint
- [ ] Return content, exists flag, mtime, path
- [ ] Return template content with template=true if missing
- [ ] Implement POST /api/projects/<id>/waypoint endpoint
- [ ] Accept content and expected_mtime
- [ ] Return 409 conflict if mtime mismatch
- [ ] Return 403 with path on permission denied
- [ ] Register waypoint_bp in app.py

### Waypoint Editor UI (FR1-FR3, FR7-FR10, FR20-21)
- [ ] Create templates/partials/_waypoint_editor.html modal
- [ ] Project selector dropdown from database
- [ ] Markdown textarea for editing
- [ ] Preview mode with rendered markdown
- [ ] Toggle between edit and preview
- [ ] Unsaved changes indicator
- [ ] Save and Cancel buttons
- [ ] File path display in footer
- [ ] Last modified timestamp display

### Conflict Resolution (FR15-FR16)
- [ ] Conflict detection dialog
- [ ] Reload option (discard changes, load current)
- [ ] Overwrite option (save anyway)
- [ ] Show external modification timestamp

### Dashboard Integration (FR21)
- [ ] Modify templates/partials/_project_group.html
- [ ] Wire [Edit] button to open waypoint editor
- [ ] Pass project ID to editor
- [ ] Include editor modal in dashboard.html

### Error Handling & Feedback (FR17-FR20, NFR5)
- [ ] Permission error with specific path
- [ ] Project path inaccessible error
- [ ] Actionable error messages pattern
- [ ] Success toast on save
- [ ] Error toast on failure

## Phase 3: Testing

- [ ] Test GET waypoint returns content
- [ ] Test GET waypoint returns template for missing file
- [ ] Test POST waypoint saves correctly
- [ ] Test POST waypoint archives before save
- [ ] Test archive counter for multiple daily saves
- [ ] Test directory creation when missing
- [ ] Test atomic write mechanism
- [ ] Test conflict detection (mtime mismatch)
- [ ] Test permission denied handling
- [ ] Test project path validation
- [ ] Test markdown preview rendering

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Waypoint loads within 500ms
- [ ] Save completes within 2 seconds
- [ ] No console errors
- [ ] Manual test: edit waypoint, save, verify archived
