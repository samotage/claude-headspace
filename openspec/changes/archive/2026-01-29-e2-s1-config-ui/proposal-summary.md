# Proposal Summary: e2-s1-config-ui

## Architecture Decisions
- Form-based editor chosen over raw YAML for usability and error prevention
- Server-side validation is authoritative (client hints optional)
- Manual refresh button chosen over auto-reload for predictability
- Atomic file write (temp file then rename) to prevent corruption
- YAML comments may be lost on save (PyYAML limitation accepted)

## Implementation Approach
- Create config API blueprint with GET/POST endpoints
- Create config editor service for validation and persistence
- Create config.html template with grouped fieldsets
- Follow existing navigation and form styling patterns
- Password field masking with reveal toggle
- Success/error toast notifications

## Files to Modify

**Routes:**
- `src/claude_headspace/routes/config.py` - Config API endpoints (new)
- `src/claude_headspace/app.py` - Register config_bp

**Services:**
- `src/claude_headspace/services/config_editor.py` - Validation and persistence (new)

**Templates:**
- `templates/config.html` - Config form page (new)
- `templates/base.html` - Add Config tab to navigation

**Tests:**
- `tests/routes/test_config.py` (new)
- `tests/services/test_config_editor.py` (new)

## Acceptance Criteria
- Config tab accessible from navigation
- All 7 config sections as grouped form fieldsets
- Form pre-populated with current values
- Field descriptions/hints displayed
- Correct field types (text, number, toggle, password)
- Server validates before save
- Inline validation errors
- Success/error toast messages
- Refresh button after save
- GET /api/config returns JSON
- POST /api/config validates and persists
- Atomic file write
- Password values never logged
- Form loads within 500ms
- All tests passing

## Constraints and Gotchas
- **PyYAML limitation:** Comments in config.yaml will be lost on save
- **Atomic write:** Use temp file then rename for safety
- **Password security:** Never log password values in errors
- **Env vars read-only:** Show file values only, not env overrides
- **Manual refresh:** User must click refresh after save to apply changes
- **Single user:** No multi-user conflict resolution needed

## Git Change History

### Related Files
**Config:**
- `_bmad/_config/` - BMAD configuration files (reference only)
- `config.yaml` - Main config file to edit

**UI Patterns:**
- `templates/base.html` - Navigation pattern to follow
- `templates/dashboard.html` - Tab styling to follow

**Route Patterns:**
- `src/claude_headspace/routes/hooks.py` - Blueprint pattern
- `src/claude_headspace/routes/focus.py` - API route pattern

### OpenSpec History
- e1-s8-dashboard-ui (2026-01-29): Dashboard UI with tabs (reference for navigation)

### Implementation Patterns
1. Create service module for business logic
2. Create Flask blueprint for API routes
3. Register blueprint in app.py
4. Create template following existing styling
5. Add comprehensive tests

## Q&A History
- No clarifications needed - PRD is comprehensive and consistent

## Dependencies
- **No new pip packages required** - uses existing Flask and PyYAML
- **Sprint 8 (Dashboard UI)** - Completed, provides navigation patterns
- **Existing config.py** - Provides config schema and defaults

## Testing Strategy
- Test GET /api/config returns full config
- Test POST /api/config with valid data saves correctly
- Test POST /api/config with invalid data returns errors
- Test validation for each field type (string, number, boolean)
- Test atomic write mechanism
- Test password masking in responses
- Test form pre-population
- Test inline validation errors
- Test toast notifications
- Test refresh button visibility

## OpenSpec References
- proposal.md: openspec/changes/e2-s1-config-ui/proposal.md
- tasks.md: openspec/changes/e2-s1-config-ui/tasks.md
- spec.md: openspec/changes/e2-s1-config-ui/specs/config/spec.md
