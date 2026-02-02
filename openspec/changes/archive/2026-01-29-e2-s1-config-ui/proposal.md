# Proposal: e2-s1-config-ui

## Summary

Add a Config UI tab to the dashboard providing a web-based form interface for editing all configuration sections directly from the browser, eliminating the need to manually edit config.yaml files.

## Motivation

Currently users must locate, open, and manually edit config.yaml in a text editor to change settings. This requires YAML syntax knowledge and risks formatting errors. A web form with validation provides a safer, more user-friendly experience.

## Impact

### Files to Create
- `src/claude_headspace/routes/config.py` - Config API endpoints (GET/POST /api/config)
- `src/claude_headspace/services/config_editor.py` - Config validation and persistence service
- `templates/config.html` - Config tab form template
- `tests/routes/test_config.py` - Config API endpoint tests
- `tests/services/test_config_editor.py` - Config editor service tests

### Files to Modify
- `src/claude_headspace/app.py` - Register config blueprint
- `templates/base.html` - Add Config tab to navigation

### Database Changes
None - reads/writes config.yaml directly.

## Definition of Done

- [ ] Config tab accessible from main navigation bar
- [ ] All 7 config sections display as grouped form fieldsets
- [ ] Form pre-populates with current config values on load
- [ ] Field descriptions/hints display below each field
- [ ] String fields render as text inputs
- [ ] Numeric fields render as number inputs with min/max
- [ ] Boolean fields render as toggle switches
- [ ] Password field masked with reveal toggle
- [ ] Server validates all fields before saving
- [ ] Validation errors display inline next to invalid field
- [ ] Success toast on save: "Configuration saved"
- [ ] Error toast on failure with specific error
- [ ] Refresh button visible after save
- [ ] GET /api/config returns current config as JSON
- [ ] POST /api/config validates and persists to config.yaml
- [ ] Atomic file write (temp file then rename)
- [ ] Password values never logged
- [ ] Form loads within 500ms
- [ ] All tests passing

## Risks

- **PyYAML loses comments:** Accepted - documented limitation
- **Config corruption:** Mitigated via atomic write
- **Invalid config breaks app:** Mitigated via server-side validation

## Alternatives Considered

1. **Raw YAML editor:** Rejected - error-prone, poor UX
2. **Auto-reload on save:** Rejected - unpredictable behavior
3. **Client-side validation only:** Rejected - server must be authoritative
