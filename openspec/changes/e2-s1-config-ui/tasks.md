# Tasks: e2-s1-config-ui

## Phase 1: Setup

- [ ] Review existing navigation and tab patterns (base.html, dashboard.html)
- [ ] Review existing config.py for configuration schema
- [ ] Review existing route patterns (hooks.py, focus.py)
- [ ] Plan service architecture

## Phase 2: Implementation

### API Endpoints (FR21-FR24)
- [ ] Create src/claude_headspace/routes/config.py blueprint
- [ ] Implement GET /api/config endpoint
- [ ] Return current config as JSON (exclude env var overrides)
- [ ] Implement POST /api/config endpoint
- [ ] Accept JSON payload and validate all fields
- [ ] Return validation errors as structured JSON on failure
- [ ] Register config_bp in app.py

### Config Editor Service (FR11, NFR1-2)
- [ ] Create src/claude_headspace/services/config_editor.py
- [ ] Implement config schema definition with field types and constraints
- [ ] Implement validation for each config section
- [ ] Implement atomic file write (temp file then rename)
- [ ] Ensure password values never logged in error messages
- [ ] Add validation for type, required fields, and value ranges

### Navigation & Access (FR1-FR2)
- [ ] Add Config tab to navigation in base.html
- [ ] Follow existing navigation styling pattern
- [ ] Implement active state indicator

### Config Tab Template (FR3-FR6)
- [ ] Create templates/config.html
- [ ] Display all 7 config sections as grouped form fieldsets
- [ ] Add clear headings for each section
- [ ] Pre-populate form with current config values
- [ ] Add field descriptions/hints below each field

### Field Types (FR7-FR10)
- [ ] Render string fields as text inputs
- [ ] Render numeric fields as number inputs with min/max constraints
- [ ] Render boolean fields as toggle switches
- [ ] Render password fields as masked inputs with reveal toggle

### Form Validation (FR12-FR13)
- [ ] Display validation errors inline next to invalid field
- [ ] Prevent form submission while validation errors exist
- [ ] Style invalid fields with red border and error text

### Save & Feedback (FR14-FR17)
- [ ] Implement Save button submitting to POST /api/config
- [ ] Display loading indicator during save
- [ ] Show success toast: "Configuration saved"
- [ ] Show error toast on failure with specific error

### Refresh Mechanism (FR18-FR20)
- [ ] Display Refresh button after successful save
- [ ] Indicate which settings require server restart
- [ ] Implement refresh/restart behavior

### Accessibility (NFR4-5)
- [ ] Add proper labels and ARIA attributes
- [ ] Ensure keyboard navigation works
- [ ] Test responsive layout at 768px viewport

## Phase 3: Testing

- [ ] Test GET /api/config returns full config
- [ ] Test POST /api/config with valid data saves correctly
- [ ] Test POST /api/config with invalid data returns errors
- [ ] Test validation for each field type
- [ ] Test atomic write (temp file rename)
- [ ] Test password masking in responses
- [ ] Test form pre-population
- [ ] Test inline validation errors display
- [ ] Test success/error toast display
- [ ] Test refresh button visibility after save

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Form loads within 500ms
- [ ] Save operation completes within 1 second
- [ ] No console errors
- [ ] Manual test: edit server.port, save, verify in config.yaml
